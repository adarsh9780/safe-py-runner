from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ExecutionRequest:
    """Normalized request sent to an execution engine.

    Example:
        ```python
        req = ExecutionRequest(payload={"code": "result = 1 + 1"}, timeout_seconds=5)
        ```
    """

    payload: dict[str, Any]
    timeout_seconds: int


@dataclass(slots=True)
class ExecutionOutcome:
    """Normalized response returned by an execution engine.

    Example:
        ```python
        out = ExecutionOutcome(stdout="{}", stderr="", returncode=0, timed_out=False)
        ```
    """

    stdout: str
    stderr: str
    returncode: int
    timed_out: bool
    error: str | None = None
