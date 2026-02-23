from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .policy import RunnerPolicy, RunnerResult


def _worker_path() -> Path:
    return Path(__file__).with_name("worker.py")


def run_code(
    code: str,
    input_data: dict[str, Any] | None = None,
    policy: RunnerPolicy | None = None,
    policy_file: str | None = None,
    python_executable: str | None = None,
) -> RunnerResult:
    """Execute code in a separate subprocess with guardrails."""
    if policy is not None and policy_file is not None:
        raise ValueError("Provide either 'policy' or 'policy_file', not both")

    if policy is None and policy_file is not None:
        policy = RunnerPolicy.from_file(policy_file)
    elif policy is None:
        policy = RunnerPolicy()
    elif policy.config_path is not None:
        policy = RunnerPolicy.from_file(policy.config_path)

    payload = {
        "code": code,
        "input_data": input_data or {},
        "policy": {
            "mode": policy.mode,
            "timeout_seconds": policy.timeout_seconds,
            "memory_limit_mb": policy.memory_limit_mb,
            "max_output_kb": policy.max_output_kb,
            "allowed_imports": policy.allowed_imports,
            "blocked_imports": policy.blocked_imports,
            "allowed_builtins": policy.allowed_builtins,
            "blocked_builtins": policy.blocked_builtins,
            "allowed_globals": policy.allowed_globals,
            "blocked_globals": policy.blocked_globals,
            "extra_globals": policy.extra_globals,
        },
    }

    py_bin = python_executable or sys.executable
    cmd = [py_bin, str(_worker_path())]

    try:
        completed = subprocess.run(
            cmd,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=max(1, int(policy.timeout_seconds)),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return RunnerResult(
            ok=False,
            timed_out=True,
            error=f"Execution timed out after {policy.timeout_seconds}s",
            exit_code=124,
        )

    raw = completed.stdout.strip() or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return RunnerResult(
            ok=False,
            error="Runner returned invalid JSON",
            stderr=completed.stderr,
            exit_code=completed.returncode,
        )

    return RunnerResult(
        ok=bool(parsed.get("ok")),
        result=parsed.get("result"),
        stdout=str(parsed.get("stdout", "")),
        stderr=str(parsed.get("stderr", "")) or completed.stderr,
        timed_out=bool(parsed.get("timed_out", False)),
        resource_exceeded=bool(parsed.get("resource_exceeded", False)),
        error=parsed.get("error"),
        exit_code=completed.returncode,
    )
