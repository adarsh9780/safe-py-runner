from __future__ import annotations

import json
from typing import Any

from .execution.capabilities import preflight_validate_backend_capabilities
from .execution.engine import ExecutionEngine
from .execution.types import ExecutionRequest
from .policy import RunnerPolicy, RunnerResult


def _resolve_policy(policy: RunnerPolicy | None, policy_file: str | None) -> RunnerPolicy:
    """Resolve the effective policy object for a run.

    Example:
        ```python
        policy = _resolve_policy(None, "/tmp/policy.toml")
        ```
    """
    if policy is not None and policy_file is not None:
        raise ValueError("Provide either 'policy' or 'policy_file', not both")
    if policy is None and policy_file is not None:
        return RunnerPolicy.from_file(policy_file)
    if policy is None:
        return RunnerPolicy()
    if policy.config_path is not None:
        return RunnerPolicy.from_file(policy.config_path)
    return policy


def _build_payload(code: str, input_data: dict[str, Any] | None, policy: RunnerPolicy) -> dict[str, Any]:
    """Build the worker payload from code, input, and policy.

    Example:
        ```python
        payload = _build_payload("result = 1 + 1", {"x": 2}, RunnerPolicy())
        ```
    """
    return {
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


def run_code(
    code: str,
    engine: ExecutionEngine,
    input_data: dict[str, Any] | None = None,
    policy: RunnerPolicy | None = None,
    policy_file: str | None = None,
) -> RunnerResult:
    """Execute Python code using the provided execution engine and policy guardrails.

    Example:
        ```python
        from safe_py_runner import LocalEngine, run_code
        engine = LocalEngine(venv_dir="/tmp/my_env")
        result = run_code("result = 2 + 2", engine=engine)
        ```
    """
    resolved_policy = _resolve_policy(policy, policy_file)
    preflight_validate_backend_capabilities(type(engine).__name__.lower())
    payload = _build_payload(code, input_data, resolved_policy)
    outcome = engine.execute(
        ExecutionRequest(
            payload=payload,
            timeout_seconds=max(1, int(resolved_policy.timeout_seconds)),
        )
    )

    if outcome.timed_out:
        return RunnerResult(
            ok=False,
            timed_out=True,
            error=outcome.error or f"Execution timed out after {resolved_policy.timeout_seconds}s",
            exit_code=124,
        )

    if outcome.error and not outcome.stdout.strip():
        return RunnerResult(
            ok=False,
            error=outcome.error,
            stderr=outcome.stderr,
            exit_code=outcome.returncode,
        )

    raw = outcome.stdout.strip() or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return RunnerResult(
            ok=False,
            error="Runner returned invalid JSON",
            stderr=outcome.stderr,
            exit_code=outcome.returncode,
        )

    return RunnerResult(
        ok=bool(parsed.get("ok")),
        result=parsed.get("result"),
        stdout=str(parsed.get("stdout", "")),
        stderr=str(parsed.get("stderr", "")) or outcome.stderr,
        timed_out=bool(parsed.get("timed_out", False)),
        resource_exceeded=bool(parsed.get("resource_exceeded", False)),
        error=parsed.get("error") or outcome.error,
        exit_code=outcome.returncode,
    )
