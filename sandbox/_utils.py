"""Internal utilities and type definitions for the sandbox package."""

import json
from typing import Any, TypedDict


class DependencyInfo(TypedDict, total=False):
    version: str
    extras: list[str]


Dependencies = dict[str, str | DependencyInfo]


class Result(TypedDict, total=False):
    """Dictionary representing the result of a sandbox execution."""

    stdout: str
    stderr: str
    result: Any
    error: str | None


def encode_inputs(inputs: dict[str, Any] | None) -> str:
    """Safely encodes input dictionary to a JSON string for script embedding."""
    if inputs is None:
        return "{}"
    try:
        return json.dumps(inputs, ensure_ascii=False)
    except TypeError as e:
        raise ValueError(f"Inputs dictionary is not JSON serializable: {e}") from e


def decode_result_from_stdout(stdout: str) -> Any:  # noqa: ANN401
    """Attempts to decode a JSON object representing the result from stdout."""
    try:
        return json.loads(stdout.strip())
    except json.JSONDecodeError as e:
        # Limit output length in error message
        output_preview = stdout[:1000] + "..." if len(stdout) > 1000 else stdout
        raise ValueError(
            f"Failed to decode JSON result from stdout: {e.msg}. Output preview: {output_preview}"
        ) from e
