"""The `sandbox` package."""

from contextlib import suppress

from .runner import SandboxRunner
from .subprocess import SubprocessSandboxRunner

with suppress(ImportError):
    from .docker import DockerSandboxRunner as DockerSandboxRunner


__all__ = [
    "DockerSandboxRunner",
    "SubprocessSandboxRunner",
    "SandboxRunner",
    "DockerSandboxRunner",
]
import importlib.metadata
__version__ = importlib.metadata.version("sandbox")

__all__ = ["__version__"]