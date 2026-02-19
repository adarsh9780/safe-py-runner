from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RunnerPolicy:
    """Execution policy for untrusted Python code."""

    timeout_seconds: int = 5
    memory_limit_mb: int = 256
    max_output_kb: int = 128
    blocked_imports: list[str] = field(default_factory=list)
    blocked_builtins: list[str] = field(default_factory=list)
    extra_globals: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RunnerResult:
    ok: bool
    result: Any = None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    resource_exceeded: bool = False
    error: str | None = None
    exit_code: int = 0
