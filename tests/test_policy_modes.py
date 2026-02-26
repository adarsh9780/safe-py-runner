from pathlib import Path

import pytest

from safe_py_runner import RunnerPolicy, LocalEngine, run_code as raw_run_code

ENGINE = LocalEngine(venv_dir="/tmp/safe_py_runner_test_venv", venv_manager="uv")

def run_code(*args, **kwargs):
    kwargs.setdefault("engine", ENGINE)
    return raw_run_code(*args, **kwargs)


def test_policy_file_path_blocks_imports_and_builtins(tmp_path: Path) -> None:
    policy_file = tmp_path / "policy.toml"
    policy_file.write_text(
        (
            "[policy]\n"
            "mode = \"restrict\"\n"
            "blocked_imports = [\"math\"]\n"
            "blocked_builtins = [\"len\"]\n"
            "blocked_globals = [\"x\"]\n"
        ),
        encoding="utf-8",
    )

    import_result = run_code("import math", policy_file=str(policy_file))
    assert import_result.ok is False
    assert "blocked by policy" in (import_result.error or "")

    builtin_result = run_code("result = len([1, 2, 3])", policy_file=str(policy_file))
    assert builtin_result.ok is False
    assert "name 'len' is not defined" in (builtin_result.error or "")

    globals_result = run_code(
        "result = x if 'x' in globals() else 'missing'",
        input_data={"x": 7},
        policy_file=str(policy_file),
    )
    assert globals_result.ok is True
    assert globals_result.result == "missing"


def test_allow_mode_allows_only_selected_symbols() -> None:
    policy = RunnerPolicy(
        mode="allow",
        allowed_imports=["math"],
        allowed_builtins=["len", "sum", "range"],
        allowed_globals=["x", "helper"],
        extra_globals={"helper": 9, "blocked_helper": 99},
    )

    allowed = run_code("import math\nresult = math.sqrt(x) + helper", input_data={"x": 16}, policy=policy)
    assert allowed.ok is True
    assert allowed.result == 13.0

    blocked_import = run_code("import os", policy=policy)
    assert blocked_import.ok is False
    assert "not allowed by policy" in (blocked_import.error or "")

    blocked_builtin = run_code("result = abs(-1)", policy=policy)
    assert blocked_builtin.ok is False
    assert "name 'abs' is not defined" in (blocked_builtin.error or "")

    blocked_global = run_code("result = blocked_helper", policy=policy)
    assert blocked_global.ok is False
    assert "name 'blocked_helper' is not defined" in (blocked_global.error or "")


def test_run_code_rejects_policy_and_policy_file_together(tmp_path: Path) -> None:
    policy_file = tmp_path / "policy.toml"
    policy_file.write_text("[policy]\nmode = \"restrict\"\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Provide either 'policy' or 'policy_file'"):
        run_code("result = 1", policy=RunnerPolicy(), policy_file=str(policy_file))
