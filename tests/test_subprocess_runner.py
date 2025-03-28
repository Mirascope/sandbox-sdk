"""Tests for the SubprocessSandboxRunner."""

import shutil
import sys
import time
from unittest.mock import patch

import pytest

from sandbox.runners.subprocess import SubprocessSandboxRunner

SIMPLE_SCRIPT = "print('Hello from subprocess!')"
JSON_OUTPUT_SCRIPT = (
    'import json; print(json.dumps({"result": 42, "details": "computed"}))'
)
FAILING_SCRIPT = "raise ValueError('Intentional fail')"
INFINITE_LOOP_SCRIPT = "while True: pass"
SLEEP_SCRIPT = "import time; time.sleep(2); print('Done sleeping')"


@pytest.fixture
def runner() -> SubprocessSandboxRunner:
    """Provides a default SubprocessSandboxRunner instance."""
    try:
        return SubprocessSandboxRunner()
    except FileNotFoundError:
        pytest.skip("uv command not found, skipping subprocess tests.")


def test_subprocess_runner_simple_script(runner: SubprocessSandboxRunner):
    """Test running a simple script."""
    result = runner.execute_script(SIMPLE_SCRIPT)
    assert "stdout" in result
    assert "stderr" in result
    assert "error" in result
    assert "Hello from subprocess!" in result["stdout"]
    assert result["stderr"] == ""
    assert result["error"] is None


def test_subprocess_runner_json_output(runner: SubprocessSandboxRunner):
    """Test script outputting JSON."""
    result = runner.execute_script(JSON_OUTPUT_SCRIPT)
    assert "stdout" in result
    assert "stderr" in result
    assert "error" in result
    assert '"result": 42' in result["stdout"]
    assert result["error"] is None


def test_subprocess_runner_failing_script(runner: SubprocessSandboxRunner):
    """Test running a script that raises an exception."""
    result = runner.execute_script(FAILING_SCRIPT)
    assert "stdout" in result
    assert "stderr" in result
    assert result["stdout"] == ""
    assert "ValueError: Intentional fail" in result["stderr"]
    assert "error" in result
    assert result["error"] is not None
    assert "exit code 1" in result["error"]


def test_subprocess_runner_timeout_expires(runner: SubprocessSandboxRunner):
    """Test script execution timeout."""
    # Create runner with short timeout
    timeout_runner = SubprocessSandboxRunner(timeout=0.5)
    start_time = time.monotonic()
    result = timeout_runner.execute_script(SLEEP_SCRIPT)  # This script takes 2s
    end_time = time.monotonic()

    assert "error" in result
    assert result["error"] is not None
    assert "timed out" in result["error"]
    assert "stderr" in result and "TimeoutExpired" in result["stderr"]
    # Check if it actually timed out reasonably close to the limit
    assert end_time - start_time < 1.5  # Should be around 0.5s + overhead


def test_subprocess_runner_timeout_sufficient(runner: SubprocessSandboxRunner):
    """Test script execution completing within timeout."""
    # Runner default timeout is 60s, script takes 2s
    start_time = time.monotonic()
    result = runner.execute_script(SLEEP_SCRIPT)
    end_time = time.monotonic()

    assert "error" in result and result["error"] is None
    assert "Done sleeping" in result["stdout"]  # pyright: ignore [reportTypedDictNotRequiredAccess]
    assert end_time - start_time >= 2.0  # Ensure it actually slept


@pytest.mark.skipif(
    sys.platform == "win32", reason="uv dependency resolution might differ"
)
def test_subprocess_runner_with_deps():
    """Test script with dependencies (requires network)."""
    # Need to instantiate runner inside test if uv might be missing
    try:
        runner = SubprocessSandboxRunner()
    except FileNotFoundError:
        pytest.skip("uv command not found.")

    script_with_header = """
# /// script
# dependencies = ["requests"]
# ///
import requests
import json
try:
    response = requests.get('https://example.com', timeout=10)
    print(json.dumps({"result": response.status_code}))
except Exception as e:
    print(json.dumps({"error": str(e)}))
"""
    result = runner.execute_script(script_with_header)
    assert result["error"] is None, f"Execution failed: {result['stderr']}"  # pyright: ignore [reportTypedDictNotRequiredAccess]
    assert '"result": 200' in result["stdout"] or '"error":' in result["stdout"]  # pyright: ignore [reportTypedDictNotRequiredAccess]


def test_subprocess_runner_uv_not_found():
    """Test runner init when uv command is not found."""
    original_which = shutil.which
    try:
        shutil.which = lambda cmd: None
        with pytest.raises(FileNotFoundError, match="uv"):
            SubprocessSandboxRunner()
    finally:
        shutil.which = original_which  # Restore original


def test_subprocess_env_filtering():
    """Test that only allowed env vars are passed."""
    # Mock subprocess.run to inspect the 'env' argument
    with patch("subprocess.run") as mock_subp_run:
        mock_subp_run.return_value.returncode = 0
        mock_subp_run.return_value.stdout = ""
        mock_subp_run.return_value.stderr = ""

        # 1. Use default allowed list
        runner_default = SubprocessSandboxRunner(
            environment={"SECRET": "123", "USER": "test", "LC_ALL": "C"}
        )
        runner_default.execute_script("print('hello')")

        call_args, call_kwargs = mock_subp_run.call_args
        passed_env_default = call_kwargs.get("env", {})
        assert "USER" in passed_env_default
        assert "LC_ALL" in passed_env_default
        assert "SECRET" not in passed_env_default
        assert "PATH" in passed_env_default  # Should be added by default

        # 2. Use custom allowed list
        runner_custom = SubprocessSandboxRunner(
            environment={"SECRET": "123", "USER": "test", "CUSTOM": "abc"},
            allowed_env_vars={"CUSTOM", "PATH"},  # Allow only CUSTOM and PATH
        )
        runner_custom.execute_script("print('hello')")

        call_args_custom, call_kwargs_custom = mock_subp_run.call_args
        passed_env_custom = call_kwargs_custom.get("env", {})
        assert "CUSTOM" in passed_env_custom
        assert "PATH" in passed_env_custom  # PATH should still be added if allowed
        assert "USER" not in passed_env_custom
        assert "SECRET" not in passed_env_custom
