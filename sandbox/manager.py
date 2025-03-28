"""Provides the Sandbox context manager for easy sandbox usage."""

import base64
import inspect
import textwrap
import traceback
from types import TracebackType
from typing import Any, cast

from ._utils import Dependencies, Result, decode_result_from_stdout, encode_inputs
from .runners.base import SandboxRunner
from .runners.docker import (
    DEFAULT_ALLOWED_ENV_VARS_DOCKER as DOCKER_DEFAULT_ALLOWED_ENV,
)
from .runners.docker import (
    DockerSandboxRunner,
)
from .runners.subprocess import (
    DEFAULT_ALLOWED_ENV_VARS as SUBPROCESS_DEFAULT_ALLOWED_ENV,
)
from .runners.subprocess import (
    SubprocessSandboxRunner,
)

_RUNNER_CLASSES: dict[str, type[SandboxRunner]] = {
    "subprocess": SubprocessSandboxRunner,
    "docker": DockerSandboxRunner,
}


class Sandbox:
    """
    Context manager for running Python code in isolated environments.

    Offers `run` for script execution (stdout/stderr capture) and `run_function`
    for structured function execution (JSON I/O). Includes options for timeout,
    network isolation, and environment variable filtering.
    """

    def __init__(
        self,
        deps: Dependencies | None = None,
        settings: dict[str, Any] | None = None,
        runner_type: str = "subprocess",
        environment: dict[str, str] | None = None,
        timeout: float | None = 60.0,
        allow_network: bool = False,
        allowed_env_vars: list[str] | None = None,
        runner_kwargs: dict[str, Any] | None = None,
    ) -> None:
        """Initializes the Sandbox."""
        self.dependencies = deps or {}
        self.settings = settings or {}

        if runner_type not in _RUNNER_CLASSES:
            raise ValueError(
                f"Unknown runner_type '{runner_type}'. Use: {list(_RUNNER_CLASSES.keys())}"
            )

        runner_cls = _RUNNER_CLASSES[runner_type]
        runner_kwargs = runner_kwargs or {}

        final_allowed_env_set: set[str]
        if allowed_env_vars is not None:
            final_allowed_env_set = set(allowed_env_vars)
        elif runner_type == "docker":
            final_allowed_env_set = DOCKER_DEFAULT_ALLOWED_ENV
        else:
            final_allowed_env_set = SUBPROCESS_DEFAULT_ALLOWED_ENV

        runner_init_args: dict[str, Any] = {
            "environment": environment,
            "timeout": timeout,
            "allowed_env_vars": final_allowed_env_set,
            **runner_kwargs,
        }

        if runner_type == "docker" and "allow_network" not in runner_init_args:
            docker_cls = cast(type[DockerSandboxRunner], runner_cls)
            sig = inspect.signature(docker_cls.__init__)
            if "allow_network" in sig.parameters:
                runner_init_args["allow_network"] = allow_network

        try:
            self.runner: SandboxRunner = runner_cls(**runner_init_args)
        except (ImportError, FileNotFoundError) as e:
            raise type(e)(f"Failed to init runner '{runner_type}': {e}") from e
        except Exception as e:
            raise RuntimeError(
                f"Failed to initialize runner '{runner_type}': {e}"
            ) from e

    def _format_dependencies(self) -> str:
        """Formats dependencies for the uv script header."""
        dep_lines = []
        for key, value in self.dependencies.items():
            if isinstance(value, str):
                if value == "*":
                    dep_lines.append(f'"{key}"')
                else:
                    dep_lines.append(f'"{key}{value}"')
            elif isinstance(value, dict):
                version = value.get("version", "")
                extras = value.get("extras", [])
                specifier = f"{key}"
                if extras:
                    specifier += f"[{','.join(extras)}]"
                if version:
                    specifier += f"=={version}"
                dep_lines.append(f'"{specifier}"')
            else:
                dep_lines.append(f'"{key}"')
        return ",\n#    ".join(dep_lines)

    def _generate_script(self, code: str) -> str:
        """Generates a simple script for `run`."""
        dependencies_str = self._format_dependencies()
        script_template = textwrap.dedent("""
            # /// script
            # requires-python = ">=3.10"
            # dependencies = [
            #    {dependencies_str}
            # ]
            # ///
            {user_code}
            """)
        return script_template.format(dependencies_str=dependencies_str, user_code=code)

    def _generate_function_script(
        self,
        code: str,
        func_name: str,
        inputs: dict[str, Any] | None,
        is_async: bool,
    ) -> str:
        """Generates a wrapper script for `run_function`."""
        dependencies_str = self._format_dependencies()
        encoded_input_json = encode_inputs(inputs)
        b64_encoded_inputs = base64.b64encode(
            encoded_input_json.encode("utf-8")
        ).decode("ascii")

        import_lines = [
            "import json",
            "import sys",
            "import base64",
            "import traceback",
        ]
        if is_async:
            import_lines.append("import asyncio")
        imports_code = "\n".join(import_lines)

        call_str = f"{func_name}(**inputs_dict)"
        exec_logic_placeholder = f"asyncio.run({call_str})" if is_async else call_str

        script_template = textwrap.dedent("""\
            # /// script
            # requires-python = ">=3.10"
            # dependencies = [
            #    {dependencies_str}
            # ]
            # ///

            {imports_code}

            {user_function_code}

            if __name__ == "__main__":
                output_result = None
                error_details = None
                final_output_dict = {{}}

                try:
                    inputs_dict = json.loads(base64.b64decode('{b64_encoded_inputs}').decode('utf-8'))
                    output_result = {exec_logic_placeholder}
                except Exception as e:
                     error_details = f"Error during execution: {{e}}\\n{{traceback.format_exc()}}"
                     print(error_details, file=sys.stderr)
                     final_output_dict["error"] = error_details

                if error_details is None:
                     try:
                         json.dumps(output_result, ensure_ascii=False)
                         final_output_dict["result"] = output_result
                     except TypeError as serialization_error:
                         err_msg = f"Function result not JSON serializable: {{serialization_error}}"
                         final_output_dict["error"] = err_msg
                         print(err_msg, file=sys.stderr)

                try:
                     print(json.dumps(final_output_dict, ensure_ascii=False))
                except Exception as final_dump_error:
                     err_fallback = {{"error": f"Fatal: Could not dump final output: {{final_dump_error}}"}}
                     print(json.dumps(err_fallback))
                     print(err_fallback["error"], file=sys.stderr)
            """)

        return script_template.format(
            dependencies_str=dependencies_str,
            imports_code=imports_code,
            user_function_code=code,
            b64_encoded_inputs=b64_encoded_inputs,
            exec_logic_placeholder=exec_logic_placeholder,
        )

    def run(self, code: str) -> Result:
        """Runs a code block and captures stdout/stderr."""
        try:
            script_content = self._generate_script(code)
            return self.runner.execute_script(script_content)
        except Exception as e:
            err_str = f"Error in sandbox.run setup: {e}\n{traceback.format_exc()}"
            return Result(stdout="", stderr=err_str, error=err_str)

    def run_function(
        self,
        code: str,
        func_name: str = "main",
        inputs: dict[str, Any] | None = None,
        is_async: bool = False,
    ) -> Result:
        """Runs a specific function with JSON I/O."""
        try:
            script_content = self._generate_function_script(
                code=code,
                func_name=func_name,
                inputs=inputs,
                is_async=is_async,
            )
            exec_result = self.runner.execute_script(script_content)

            if exec_result.get("error"):
                return exec_result

            if exec_result.get("stdout"):
                try:
                    parsed_output = decode_result_from_stdout(
                        exec_result.get("stdout", "")
                    )
                    if isinstance(parsed_output, dict):
                        if "result" in parsed_output:
                            exec_result["result"] = parsed_output["result"]
                        if "error" in parsed_output:
                            script_error = parsed_output["error"]
                            combined_error = f"Script Error: {script_error}"
                            runner_stderr = exec_result.get("stderr", "")
                            if runner_stderr and script_error not in runner_stderr:
                                combined_error += (
                                    f"\n--- Runner Stderr ---\n{runner_stderr}"
                                )
                            exec_result["error"] = combined_error
                            if script_error not in runner_stderr:
                                exec_result["stderr"] = (
                                    f"{runner_stderr}\n{script_error}".strip()
                                )
                        elif "result" not in parsed_output:
                            exec_result["error"] = (
                                "Script JSON output missing 'result' or 'error'."
                            )
                    else:
                        exec_result["error"] = (
                            "Script JSON output was not a dictionary."
                        )
                except ValueError as parse_error:
                    exec_result["error"] = (
                        f"Failed to parse JSON from stdout: {parse_error}"
                    )
            elif exec_result.get("stderr"):
                exec_result["error"] = (
                    f"Execution failed (no stdout). Stderr: {exec_result.get('stderr', '')[:1000]}"
                )

            return exec_result

        except ValueError as e:
            return Result(stdout="", stderr=str(e), error=str(e))
        except Exception as e:
            err_str = (
                f"Error in sandbox.run_function setup: {e}\n{traceback.format_exc()}"
            )
            return Result(stdout="", stderr=err_str, error=err_str)

    def __enter__(self) -> "Sandbox":
        """Enter the runtime context."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit the runtime context; performs cleanup."""
        self.runner.cleanup()
