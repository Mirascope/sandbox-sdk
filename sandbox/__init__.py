"""Sandbox SDK

A utility library for running Python code in isolated environments.
"""

import importlib.metadata

from .manager import Sandbox
from .runners import (
    DockerSandboxRunner,
    SandboxRunner,
    SubprocessSandboxRunner,
)

try:
    __version__ = importlib.metadata.version("sandbox-sdk")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0-dev"


__all__ = [
    "DockerSandboxRunner",
    "Sandbox",
    "SandboxRunner",
    "SubprocessSandboxRunner",
    "__version__",
]
