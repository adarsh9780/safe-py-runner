from safe_py_runner import RunnerPolicy, run_code


def test_blocked_import_direct() -> None:
    """Verify that directly importing a blocked module fails."""
    policy = RunnerPolicy(blocked_imports=["os"])
    result = run_code("import os", policy=policy)
    assert not result.ok
    assert "blocked by policy" in (result.error or "")


def test_blocked_import_alias() -> None:
    """Verify that aliasing a blocked module still fails."""
    policy = RunnerPolicy(blocked_imports=["os"])
    result = run_code("import os as my_os", policy=policy)
    assert not result.ok
    assert "blocked by policy" in (result.error or "")


def test_blocked_import_from() -> None:
    """Verify that 'from x import y' on a blocked module fails."""
    policy = RunnerPolicy(blocked_imports=["os"])
    result = run_code("from os import path", policy=policy)
    assert not result.ok
    assert "blocked by policy" in (result.error or "")


def test_blocked_builtin_eval() -> None:
    """Verify that using eval is blocked."""
    policy = RunnerPolicy(blocked_builtins=["eval"])
    result = run_code("x = eval('1 + 1')", policy=policy)
    assert not result.ok
    # Error message might vary depending on if it's NameError or custom
    # blocked builtins are usually removed from globals, so it raises NameError
    assert "name 'eval' is not defined" in (result.error or "") or "blocked" in (
        result.error or ""
    )


def test_blocked_builtin_exec() -> None:
    """Verify that using exec is blocked."""
    policy = RunnerPolicy(blocked_builtins=["exec"])
    result = run_code("exec('x = 1')", policy=policy)
    assert not result.ok
    assert "name 'exec' is not defined" in (result.error or "")


def test_blocked_builtin_open() -> None:
    """Verify that using open is blocked."""
    policy = RunnerPolicy(blocked_builtins=["open"])
    result = run_code("f = open('test.txt', 'w')", policy=policy)
    assert not result.ok
    assert "name 'open' is not defined" in (result.error or "")


def test_sys_exit_code() -> None:
    """Verify that sys.exit() is handled gracefully."""
    # sys.exit(0) -> Success
    result = run_code("import sys\nsys.exit(0)")
    assert result.ok is True
    assert result.exit_code == 0

    # sys.exit(1) -> Failure (controlled)
    result_err = run_code("import sys\nsys.exit(1)")
    assert result_err.ok is False
    assert result_err.exit_code == 1
    assert "SystemExit: 1" in (result_err.error or "")


def test_sys_exit_string_message() -> None:
    result = run_code("import sys\nsys.exit('stop now')")
    assert result.ok is False
    assert result.exit_code == 1
    assert "SystemExit: stop now" in (result.error or "")
    assert "stop now" in result.stderr


def test_importlib_bypass_attempt() -> None:
    """
    Attempt to bypass import block using importlib.
    This should fail IF importlib itself is blocked or if the hook catches it.
    safe-py-runner's hook works on __import__, which importlib uses internally.
    """
    policy = RunnerPolicy(blocked_imports=["os"])
    code = """
import importlib
os = importlib.import_module("os")
"""
    result = run_code(code, policy=policy)
    assert not result.ok
    assert "blocked by policy" in (result.error or "")


def test_dunder_import_bypass_attempt() -> None:
    """Attempt to bypass using __import__."""
    policy = RunnerPolicy(blocked_imports=["os"])
    code = """
os = __import__("os")
"""
    result = run_code(code, policy=policy)
    assert not result.ok
    assert "blocked by policy" in (result.error or "")


def test_secure_defaults_block_os_import() -> None:
    result = run_code("import os")
    assert result.ok is False
    assert "blocked by policy" in (result.error or "")


def test_secure_defaults_block_eval_builtin() -> None:
    result = run_code("result = eval('1+1')")
    assert result.ok is False
    assert "name 'eval' is not defined" in (result.error or "")
