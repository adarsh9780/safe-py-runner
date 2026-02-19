from safe_py_runner import RunnerPolicy, run_code


def test_run_code_success_math_import():
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


def test_import_blocked():
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


def test_builtin_blocked():
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
