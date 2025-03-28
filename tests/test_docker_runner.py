"""Tests for the DockerSandboxRunner."""

import json
import sys

import pytest

try:
    import docker  # Import docker itself to check availability

    from sandbox.runners.docker import (
        DockerException,
        DockerSandboxRunner,
        ImageNotFound,
    )

    _DOCKER_INSTALLED = True
except ImportError:
    _DOCKER_INSTALLED = False

    class DockerSandboxRunner: ...

    class DockerException(Exception): ...

    class ImageNotFound(DockerException): ...


pytestmark = pytest.mark.skipif(
    not _DOCKER_INSTALLED, reason="Docker library not installed"
)

SIMPLE_SCRIPT = "print('Hello from Docker!')"
JSON_OUTPUT_SCRIPT = (
    'import json; print(json.dumps({"result": 123, "container": True}))'
)
FAILING_SCRIPT = "raise RuntimeError('Failure inside container')"
DEPS_SCRIPT_CODE = """
import numpy as np
import json
print(json.dumps({"result": np.array([1, 2, 3]).tolist()}))
"""
NETWORK_TEST_SCRIPT = """
import socket, json
try:
    socket.gethostbyname('example.com')
    print(json.dumps({"network": True}))
except socket.gaierror:
    print(json.dumps({"network": False}))
except Exception as e:
    print(json.dumps({"error": str(e)}))
"""


@pytest.fixture(scope="module")  # Scope module to avoid repeated pinging
def docker_available() -> bool:
    """Fixture to check if Docker daemon is running."""
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


@pytest.fixture
def runner(docker_available: bool) -> type[DockerSandboxRunner]:
    """Provides a DockerSandboxRunner class, skipping if daemon unavailable."""
    if not docker_available:
        pytest.skip("Docker daemon not running or inaccessible, skipping Docker tests.")
    return DockerSandboxRunner  # Return the class itself for instantiation in tests


def test_docker_runner_simple_script(runner: type[DockerSandboxRunner]):
    """Test running a simple script."""
    docker_runner = runner()
    result = docker_runner.execute_script(SIMPLE_SCRIPT)
    assert result["error"] is None, (
        f"Docker execution failed: {result.get('stderr', '')}"
    )
    assert "Hello from Docker!" in result["stdout"]


def test_docker_runner_json_output(runner: type[DockerSandboxRunner]):
    """Test running a script outputting JSON."""
    docker_runner = runner()
    result = docker_runner.execute_script(JSON_OUTPUT_SCRIPT)
    assert result["error"] is None, (
        f"Docker execution failed: {result.get('stderr', '')}"
    )
    assert '"result": 123' in result["stdout"]
    assert '"container": true' in result["stdout"]


def test_docker_runner_failing_script(runner: type[DockerSandboxRunner]):
    """Test running a script that fails inside the container."""
    docker_runner = runner()
    result = docker_runner.execute_script(FAILING_SCRIPT)
    assert result["stdout"] == ""
    assert result["error"] is not None
    assert "exit code" in result["error"]
    assert "RuntimeError: Failure inside container" in result["stderr"]


@pytest.mark.skipif(sys.platform == "win32", reason="Docker handling might differ")
def test_docker_runner_with_deps(runner: type[DockerSandboxRunner]):
    """Test running script with dependencies in Docker (needs network)."""
    docker_runner = runner(allow_network=True)  # Enable network for this test
    script_with_header = f"""
# /// script
# dependencies = ["numpy"]
# ///
{DEPS_SCRIPT_CODE}
"""
    result = docker_runner.execute_script(script_with_header)
    assert result["error"] is None, (
        f"Docker execution failed: {result.get('stderr', '')}"
    )
    assert '"result": [1, 2, 3]' in result["stdout"]


def test_docker_runner_invalid_image(
    runner: type[DockerSandboxRunner],
):  # runner fixture checks availability
    """Test using a non-existent Docker image."""
    invalid_image_name = "nonexistent-registry/nonexistent-image:latest-fail"
    with pytest.raises(RuntimeError, match="image/container error"):
        docker_runner = runner(image=invalid_image_name)
        docker_runner.execute_script(SIMPLE_SCRIPT)


def test_docker_runner_network_disabled_by_default(runner: type[DockerSandboxRunner]):
    """Test that network is disabled by default."""
    docker_runner = runner()  # Default allow_network=False
    result = docker_runner.execute_script(NETWORK_TEST_SCRIPT)
    assert result["error"] is None, f"Network test script failed: {result['stderr']}"
    assert '"network": false' in result["stdout"]


def test_docker_runner_network_enabled(runner: type[DockerSandboxRunner]):
    """Test network access when explicitly enabled."""
    docker_runner = runner(allow_network=True)
    result = docker_runner.execute_script(NETWORK_TEST_SCRIPT)
    assert result["error"] is None, f"Network test script failed: {result['stderr']}"
    assert '"network": true' in result["stdout"] or '"error":' in result["stdout"]


def test_docker_env_filtering(runner: type[DockerSandboxRunner]):
    """Test that only allowed env vars are passed."""
    docker_runner = runner(
        environment={"SECRET": "abc", "LANG": "C.UTF-8", "MYVAR": "test"},
        allowed_env_vars={"LANG"},  # Only allow LANG
    )
    env_script = """
import os, json
print(json.dumps({
    "SECRET": os.environ.get("SECRET"),
    "LANG": os.environ.get("LANG"),
    "MYVAR": os.environ.get("MYVAR"),
    "PATH": os.environ.get("PATH")
}))
"""
    result = docker_runner.execute_script(env_script)
    assert result["error"] is None, f"Env test script failed: {result['stderr']}"

    try:
        env_output = json.loads(result["stdout"].strip())
        assert env_output["SECRET"] is None
        assert env_output["MYVAR"] is None
        assert env_output["LANG"] == "C.UTF-8"
        assert env_output["PATH"] is not None
    except json.JSONDecodeError:
        pytest.fail(f"Could not parse JSON output for env test: {result['stdout']}")
