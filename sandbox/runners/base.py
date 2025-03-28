"""Base class for sandbox runners."""

from abc import ABC, abstractmethod

from .._utils import Result


class SandboxRunner(ABC):
    """Abstract base class for executing code in a sandboxed environment."""

    def __init__(
        self,
        environment: dict[str, str] | None = None,
        timeout: float | None = 60.0,
    ) -> None:
        """Initializes the SandboxRunner."""
        self.environment: dict[str, str] = {
            str(k): str(v) for k, v in (environment or {}).items()
        }
        self.timeout: float | None = timeout

    @abstractmethod
    def execute_script(self, script_content: str) -> Result:
        """
        Executes the given Python script content in the sandboxed environment.

        Args:
            script_content: A string containing the complete Python script to execute.

        Returns:
            A Result dictionary containing at least 'stdout' and 'stderr'.
        """
        raise NotImplementedError  # Ensure subclasses implement this

    def cleanup(self) -> None:
        """Performs any necessary cleanup for the runner."""
        return None
