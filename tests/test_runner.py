from safe_py_runner import RunnerPolicy, LocalEngine, run_code as raw_run_code

ENGINE = LocalEngine(venv_dir="/tmp/safe_py_runner_test_venv", venv_manager="uv")

def run_code(*args, **kwargs):
    kwargs.setdefault("engine", ENGINE)
    return raw_run_code(*args, **kwargs)


def test_run_code_success_math_import() -> None:
    policy = RunnerPolicy(
        timeout_seconds=2,
        memory_limit_mb=128,
        blocked_imports=["os"],
        blocked_builtins=["eval", "exec"],
    )

    result = run_code(
        code="import math\nresult = math.sqrt(int(input_data['x']))\nprint('done')",
        input_data={"x": 81},
        policy=policy,
    )

    assert result.ok is True
    assert result.result == 9.0


def test_import_blocked() -> None:
    policy = RunnerPolicy(
        timeout_seconds=2,
        memory_limit_mb=128,
        blocked_imports=["os"],
    )

    result = run_code(
        code="import os\nresult = 1",
        policy=policy,
    )

    assert result.ok is False
    assert "blocked by policy" in (result.error or "")


def test_builtin_blocked() -> None:
    policy = RunnerPolicy(
        timeout_seconds=2,
        memory_limit_mb=128,
        blocked_imports=["os"],
        blocked_builtins=["eval"],
    )

    result = run_code(
        code="result = eval('1+1')",
        policy=policy,
    )

    assert result.ok is False
