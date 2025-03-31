"""Sandbox runner that executes code inside a Docker container."""

import io
import tarfile
from contextlib import suppress
from typing import Any

import docker
from docker.errors import DockerException, ImageNotFound, NotFound
from docker.models.containers import Container

from .._utils import Result
from .base import SandboxRunner

_DEFAULT_IMAGE = "ghcr.io/astral-sh/uv:python3.10-alpine"
_CONTAINER_SCRIPT_PATH = "/sandbox_script.py"
DEFAULT_ALLOWED_ENV_VARS_DOCKER = {"LANG", "LC_ALL"}  # Minimal safe set for Docker


class DockerSandboxRunner(SandboxRunner):
    """Runs code in a Docker container using `uv run`."""

    def __init__(
        self,
        image: str = _DEFAULT_IMAGE,
        environment: dict[str, str] | None = None,
        timeout: float | None = None,
        allow_network: bool = False,
        allowed_env_vars: set[str] | None = None,
        docker_client_kwargs: dict[str, Any] | None = None,
        container_kwargs: dict[str, Any] | None = None,
    ) -> None:
        """
        Initializes the DockerSandboxRunner.

        Args:
            image: Docker image to use (must have `uv`).
            environment: Raw environment variables. Filtered by allowed_env_vars.
            timeout: NOTE: Direct execution timeout is not easily applied here.
                     Consider resource limits via container_kwargs.
            allow_network: If False, sets network_mode='none'.
            allowed_env_vars: Set of allowed environment variable names.
                              Defaults to a minimal safe set for Docker.
            docker_client_kwargs: Args for docker.from_env().
            container_kwargs: Args for client.containers.run().
        """

        if allowed_env_vars is None:
            allowed_env_vars = DEFAULT_ALLOWED_ENV_VARS_DOCKER

        filtered_env = {}
        if environment:
            for key, value in environment.items():
                if key in allowed_env_vars:
                    filtered_env[key] = value

        super().__init__(environment=filtered_env, timeout=timeout)
        self.image = image
        self.allow_network = allow_network
        self.docker_client_kwargs = docker_client_kwargs or {}
        self.container_kwargs = container_kwargs or {}

    @staticmethod
    def _create_tar_stream(content: str, name: str) -> io.BytesIO:
        """Creates a tar archive in memory."""
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as tar:
            encoded_content = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(encoded_content)
            tar.addfile(info, io.BytesIO(encoded_content))
        stream.seek(0)
        return stream

    def execute_script(self, script_content: str) -> Result:
        """Executes the script inside a Docker container."""
        result: Result = {"stdout": "", "stderr": "", "error": None}
        client = None
        container: Container | None = None
        try:
            client = docker.from_env(**self.docker_client_kwargs)
            client.ping()

            default_container_settings = {
                "image": self.image,
                "command": "tail -f /dev/null",
                "detach": True,
                "remove": True,
                "environment": self.environment,  # Use filtered env
                "security_opt": ["no-new-privileges"],
                "cap_drop": ["ALL"],
            }
            if not self.allow_network:
                default_container_settings["network_mode"] = "none"

            run_settings = {**default_container_settings, **self.container_kwargs}
            if (
                not self.allow_network
                and self.container_kwargs.get("network_mode") is None
            ):
                run_settings["network_mode"] = "none"
            elif (
                not self.allow_network
                and self.container_kwargs.get("network_mode") != "none"
            ):
                pass

            container = client.containers.run(**run_settings)  # type: ignore[misc]
            if not container:
                raise RuntimeError("Failed to create Docker container.")
            script_filename = _CONTAINER_SCRIPT_PATH.lstrip("/")
            tar_stream = self._create_tar_stream(script_content, script_filename)
            container.put_archive("/", tar_stream)

            exec_command = ["uv", "run", _CONTAINER_SCRIPT_PATH]
            exit_code, output_streams = container.exec_run(
                cmd=exec_command, stream=False, demux=True
            )

            stdout_bytes, stderr_bytes = output_streams
            result["stdout"] = (
                stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            )
            result["stderr"] = (
                stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            )

            if exit_code != 0:
                result["error"] = (
                    f"Docker execution failed (exit code {exit_code}). "
                    f"Stderr: {result['stderr'].strip()}"
                )

        except (ImageNotFound, NotFound) as e:
            result["error"] = f"Docker image/container error: {e}"
            raise RuntimeError(result["error"]) from e
        except DockerException as e:
            result["error"] = f"Docker operation failed: {e}"
            raise RuntimeError(result["error"]) from e
        except Exception as e:
            result["error"] = f"Docker runner unexpected error: {e}"
            result["stderr"] = result.get("stderr", "") + f"\n[Runner Error] {e}"
        finally:
            if container:
                with suppress(DockerException, Exception):
                    container.stop(timeout=5)

        return result
