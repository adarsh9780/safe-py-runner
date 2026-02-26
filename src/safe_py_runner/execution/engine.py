from __future__ import annotations

from typing import Protocol

from .types import ExecutionOutcome, ExecutionRequest


class ExecutionEngine(Protocol):
    def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        """Execute one request and return normalized execution outcome.

        Example:
            ```python
            outcome = engine.execute(ExecutionRequest(payload={"code": "result = 1"}, timeout_seconds=5))
            ```
        """
        ...
