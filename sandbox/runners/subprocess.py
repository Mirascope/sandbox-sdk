import contextlib
import os
import resource
import shutil
import subprocess
import tempfile
from pathlib import Path

from .._utils import Result
from .base import SandboxRunner

DEFAULT_ALLOWED_ENV_VARS = {
    "PATH",
    "HOME",
    "USER",
    "TMPDIR",
    "TEMP",
    "TMP",
    "LANG",
    "LC_ALL",
}


class SubprocessSandboxRunner(SandboxRunner):
    def __init__(
        self,
        environment: dict[str, str] | None = None,
        timeout: float | None = 60.0,
        allowed_env_vars: set[str] | None = None,
        cpu_time_limit: int | None = None,
        memory_limit: int | None = None,
    ) -> None:
        """
        Initializes the SubprocessSandboxRunner.

        Args:
            environment: Raw environment variables to potentially pass.
            timeout: Execution time limit in seconds.
            allowed_env_vars: Set of environment variable names allowed to be passed.
                              If None, uses DEFAULT_ALLOWED_ENV_VARS.
        """
        self.uv_path = shutil.which("uv")
        if not self.uv_path:
            raise FileNotFoundError(
                "The 'uv' command was not found in the system PATH."
            )

        if allowed_env_vars is None:
            allowed_env_vars = DEFAULT_ALLOWED_ENV_VARS

        filtered_env = {}
        if environment:
            for key, value in environment.items():
                if key in allowed_env_vars:
                    filtered_env[key] = value

        if "PATH" in allowed_env_vars and "PATH" not in filtered_env:
            filtered_env["PATH"] = os.environ.get("PATH", "")
        if "HOME" in allowed_env_vars and "HOME" not in filtered_env:
            filtered_env["HOME"] = os.environ.get("HOME", "")
        if "USER" in allowed_env_vars and "USER" not in filtered_env:
            filtered_env["USER"] = os.environ.get("USER", "")
        for temp_var in ["TMPDIR", "TEMP", "TMP"]:
            if (
                temp_var in allowed_env_vars
                and temp_var not in filtered_env
                and os.environ.get(temp_var)
            ):
                filtered_env[temp_var] = os.environ[temp_var]

        super().__init__(environment=filtered_env, timeout=timeout)
        self.cpu_time_limit = cpu_time_limit
        self.memory_limit = memory_limit

    def _pre_exec_fn(self) -> None:
        if self.cpu_time_limit:
            resource.setrlimit(
                resource.RLIMIT_CPU, (self.cpu_time_limit, self.cpu_time_limit)
            )
        if self.memory_limit:
            resource.setrlimit(
                resource.RLIMIT_AS, (self.memory_limit, self.memory_limit)
            )

    def execute_script(self, script_content: str) -> Result:
        """Executes the script content using `uv run` with timeout."""
        tmp_path: Path | None = None
        result: Result = {"stdout": "", "stderr": "", "error": None}
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as tmp_file:
                tmp_file.write(script_content)
                tmp_path = Path(tmp_file.name)

            command = [self.uv_path, "run", "--no-project", str(tmp_path)]

            try:
                process = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    env=self.environment,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.timeout,
                    preexec_fn=self._pre_exec_fn,
                )

                result["stdout"] = process.stdout
                result["stderr"] = process.stderr

                if process.returncode != 0:
                    result["error"] = (
                        f"Subprocess failed (exit code {process.returncode}). "
                        f"Stderr: {process.stderr.strip()}"
                    )

            except subprocess.TimeoutExpired:
                result["error"] = f"Subprocess timed out after {self.timeout} seconds."
                result["stderr"] = (
                    result.get("stderr", "") + "\n[Runner Error] TimeoutExpired"
                )
            except FileNotFoundError:
                raise FileNotFoundError("'uv' command path invalid.") from None
            except Exception as e:
                result["error"] = f"Subprocess runner unexpected error: {e}"
                result["stderr"] = result.get("stderr", "") + f"\n[Runner Error] {e}"
        finally:
            if tmp_path and tmp_path.exists():
                with contextlib.suppress(OSError):
                    tmp_path.unlink()
        return result
