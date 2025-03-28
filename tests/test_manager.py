"""Tests for the Sandbox context manager."""

import json
from unittest.mock import MagicMock, patch

import pytest

from sandbox import Sandbox
from sandbox._utils import Result
from sandbox.runners.base import SandboxRunner
from sandbox.runners.docker import DockerSandboxRunner

# Import runner classes needed for isinstance checks and default env vars
from sandbox.runners.subprocess import SubprocessSandboxRunner

# Test Data
SIMPLE_CODE = "print('Hello from Sandbox run')"
FUNC_CODE_SYNC = "def process(a, b=2): return a + b"
FUNC_CODE_ASYNC = (
    "import asyncio\nasync def process_async(x): await asyncio.sleep(0.01); return x*x"
)
CODE_WITH_DEP = "import cowsay; cowsay.cow('Moo!')"
CODE_FOR_FUNC_DEP = "import numpy as np\ndef calc(data): arr = np.array(data); return (arr.mean(), arr.std())"
SLEEP_CODE = "import time; time.sleep(1.5); print('Slept')"


# Fixtures
@pytest.fixture
def mock_runner_instance() -> MagicMock:
    runner = MagicMock(spec=SandboxRunner)
    runner.execute_script.return_value = Result(stdout="", stderr="", error=None)
    return runner


@pytest.fixture
def mocked_sandbox_factory(mock_runner_instance: MagicMock):
    """Factory fixture to create Sandbox instances with mocked runners."""
    mock_runners_dict = {
        "subprocess": lambda **kwargs: mock_runner_instance,
        "docker": lambda **kwargs: mock_runner_instance,
    }
    with patch.dict("sandbox.manager._RUNNER_CLASSES", mock_runners_dict, clear=True):

        def _factory(*args, **kwargs):
            if "runner_type" not in kwargs:
                kwargs["runner_type"] = "subprocess"
            elif kwargs["runner_type"] not in mock_runners_dict:
                raise ValueError(f"runner_type '{kwargs['runner_type']}' not mocked")
            return Sandbox(*args, **kwargs)

        yield _factory, mock_runner_instance


def test_sandbox_run_basic(mocked_sandbox_factory):
    create_sandbox, mock_runner = mocked_sandbox_factory
    expected_stdout = "Output from script"
    mock_runner.execute_script.return_value = Result(
        stdout=expected_stdout, stderr="", error=None
    )
    with create_sandbox() as sandbox:
        result = sandbox.run(SIMPLE_CODE)
    assert result["stdout"] == expected_stdout
    assert result.get("error") is None
    mock_runner.execute_script.assert_called_once()
    call_args, _ = mock_runner.execute_script.call_args
    assert SIMPLE_CODE in call_args[0]


def test_sandbox_run_with_deps(mocked_sandbox_factory):
    create_sandbox, mock_runner = mocked_sandbox_factory
    deps = {"cowsay": "*"}
    mock_runner.execute_script.return_value = Result(
        stdout="moo", stderr="", error=None
    )
    with create_sandbox(deps=deps) as sandbox:
        sandbox.run(CODE_WITH_DEP)
    mock_runner.execute_script.assert_called_once()
    call_args, _ = mock_runner.execute_script.call_args
    generated_script = call_args[0]
    assert CODE_WITH_DEP in generated_script
    assert '"cowsay"' in generated_script  # Check for package name without "*"


def test_sandbox_run_runner_error(mocked_sandbox_factory):
    create_sandbox, mock_runner = mocked_sandbox_factory
    error_message = "Runner failed execution"
    stderr_content = "Detailed error log"
    mock_runner.execute_script.return_value = Result(
        stdout="", stderr=stderr_content, error=error_message
    )
    with create_sandbox() as sandbox:
        result = sandbox.run(SIMPLE_CODE)
    assert result["stdout"] == ""
    assert result["stderr"] == stderr_content
    assert result["error"] == error_message
    mock_runner.execute_script.assert_called_once()


def test_sandbox_run_function_sync(mocked_sandbox_factory):
    create_sandbox, mock_runner = mocked_sandbox_factory
    func_result = 5
    mock_runner.execute_script.return_value = Result(
        stdout=json.dumps({"result": func_result}), stderr="", error=None
    )
    inputs = {"a": 3, "b": 2}
    with create_sandbox() as sandbox:
        result = sandbox.run_function(
            FUNC_CODE_SYNC, func_name="process", inputs=inputs
        )
    assert result.get("result") == func_result
    assert result.get("error") is None
    mock_runner.execute_script.assert_called_once()


@pytest.mark.asyncio
async def test_sandbox_run_function_async(mocked_sandbox_factory):
    create_sandbox, mock_runner = mocked_sandbox_factory
    func_result = 16
    mock_runner.execute_script.return_value = Result(
        stdout=json.dumps({"result": func_result}), stderr="", error=None
    )
    inputs = {"x": 4}
    with create_sandbox() as sandbox:
        result = sandbox.run_function(
            FUNC_CODE_ASYNC, func_name="process_async", inputs=inputs, is_async=True
        )
    assert result.get("result") == func_result
    assert result.get("error") is None
    mock_runner.execute_script.assert_called_once()


def test_sandbox_run_function_with_deps(mocked_sandbox_factory):
    create_sandbox, mock_runner = mocked_sandbox_factory
    func_result = [2.0, 0.816496580927726]
    mock_runner.execute_script.return_value = Result(
        stdout=json.dumps({"result": func_result}), stderr="", error=None
    )
    deps = {"numpy": ">=1.20"}
    inputs = {"data": [1, 2, 3]}
    with create_sandbox(deps=deps) as sandbox:
        result = sandbox.run_function(
            CODE_FOR_FUNC_DEP, func_name="calc", inputs=inputs
        )
    assert result.get("result") == pytest.approx(func_result)
    assert result.get("error") is None
    mock_runner.execute_script.assert_called_once()


def test_sandbox_run_function_script_error(mocked_sandbox_factory):
    create_sandbox, mock_runner = mocked_sandbox_factory
    script_error_detail = "ValueError: Bad input"
    script_error_full = f"Error during execution: {script_error_detail}\\nTraceback..."
    runner_stderr = f"Error during execution: {script_error_detail}..."
    mock_runner.execute_script.return_value = Result(
        stdout=json.dumps({"error": script_error_full}),
        stderr=runner_stderr,
        error=None,
    )
    with create_sandbox() as sandbox:
        result = sandbox.run_function(
            "def main(): raise ValueError('Bad input')", func_name="main"
        )
    assert result.get("result") is None
    assert result.get("error") is not None
    assert (
        "Script Error: Error during execution: ValueError: Bad input" in result["error"]
    )
    assert f"--- Runner Stderr ---\n{runner_stderr}" in result["error"]


def test_sandbox_run_function_non_json_result(mocked_sandbox_factory):
    create_sandbox, mock_runner = mocked_sandbox_factory
    error_msg_in_json = "Function result not JSON serializable: TypeError('...')"
    stderr_from_script = "Function result not JSON serializable: TypeError(...)"
    mock_runner.execute_script.return_value = Result(
        stdout=json.dumps({"error": error_msg_in_json}),
        stderr=stderr_from_script,
        error=None,
    )
    code = "class NonSerializable: pass\ndef main(): return NonSerializable()"
    with create_sandbox() as sandbox:
        result = sandbox.run_function(code, func_name="main")
    assert result.get("result") is None
    assert result.get("error") is not None
    assert "Script Error: Function result not JSON serializable" in result["error"]


def test_sandbox_run_function_invalid_json_output(mocked_sandbox_factory):
    create_sandbox, mock_runner = mocked_sandbox_factory
    invalid_stdout = "This is not JSON { invalid"
    mock_runner.execute_script.return_value = Result(
        stdout=invalid_stdout, stderr="", error=None, result=None
    )
    with create_sandbox() as sandbox:
        result = sandbox.run_function(
            FUNC_CODE_SYNC, func_name="process", inputs={"a": 1}
        )
    assert result.get("result") is None
    assert result.get("error") is not None
    assert "Failed to parse JSON from stdout" in result["error"]


def test_sandbox_init_timeout():
    """Test timeout is stored in runner."""
    try:
        sandbox_sub = Sandbox(runner_type="subprocess", timeout=30.0)
        assert isinstance(sandbox_sub.runner, SubprocessSandboxRunner)
        assert sandbox_sub.runner.timeout == 30.0

        sandbox_doc = Sandbox(runner_type="docker", timeout=90.0)
        assert isinstance(sandbox_doc.runner, DockerSandboxRunner)
        assert sandbox_doc.runner.timeout == 90.0
    except (FileNotFoundError, ImportError, RuntimeError, NameError) as e:
        pytest.skip(f"Skipping init test due to runner setup issue: {e}")


def test_sandbox_init_network():
    """Test allow_network option for Docker."""
    try:
        sandbox_net_false = Sandbox(runner_type="docker")
        assert isinstance(sandbox_net_false.runner, DockerSandboxRunner)
        assert sandbox_net_false.runner.allow_network is False

        sandbox_net_true = Sandbox(runner_type="docker", allow_network=True)
        assert isinstance(sandbox_net_true.runner, DockerSandboxRunner)
        assert sandbox_net_true.runner.allow_network is True
    except (ImportError, RuntimeError, NameError) as e:
        pytest.skip(f"Skipping docker network test: {e}")


def test_sandbox_init_env_vars():
    """Test allowed_env_vars filtering is applied."""
    user_env = {
        "SECRET": "123",
        "USER": "test",
        "LANG": "C",
        "MY_VAR": "abc",
        "PATH": "/usr/bin",
    }
    try:
        sandbox_sub_def = Sandbox(runner_type="subprocess", environment=user_env)
        assert isinstance(sandbox_sub_def.runner, SubprocessSandboxRunner)
        assert "SECRET" not in sandbox_sub_def.runner.environment
        assert sandbox_sub_def.runner.environment.get("USER") == "test"
        assert "PATH" in sandbox_sub_def.runner.environment

        sandbox_doc_def = Sandbox(runner_type="docker", environment=user_env)
        assert isinstance(sandbox_doc_def.runner, DockerSandboxRunner)
        assert "SECRET" not in sandbox_doc_def.runner.environment
        assert "USER" not in sandbox_doc_def.runner.environment
        assert sandbox_doc_def.runner.environment.get("LANG") == "C"

        custom_list = ["MY_VAR", "LANG"]
        sandbox_sub_cust = Sandbox(
            runner_type="subprocess", environment=user_env, allowed_env_vars=custom_list
        )
        assert isinstance(sandbox_sub_cust.runner, SubprocessSandboxRunner)
        assert "SECRET" not in sandbox_sub_cust.runner.environment
        assert "USER" not in sandbox_sub_cust.runner.environment
        assert sandbox_sub_cust.runner.environment.get("LANG") == "C"
        assert sandbox_sub_cust.runner.environment.get("MY_VAR") == "abc"

    except (FileNotFoundError, ImportError, RuntimeError, NameError) as e:
        pytest.skip(f"Skipping env var test due to runner setup issue: {e}")


def test_sandbox_invalid_runner_type():
    """Test initialization with an invalid runner type."""
    with pytest.raises(ValueError, match="Unknown runner_type"):
        Sandbox(runner_type="invalid_runner")
