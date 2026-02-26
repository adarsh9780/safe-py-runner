import sys
import pytest
from safe_py_runner import RunnerPolicy, LocalEngine, run_code as raw_run_code

ENGINE = LocalEngine(venv_dir="/tmp/safe_py_runner_test_venv", venv_manager="uv")

def run_code(*args, **kwargs):
    kwargs.setdefault("engine", ENGINE)
    return raw_run_code(*args, **kwargs)


def test_timeout_enforcement() -> None:
    """Verify that code taking longer than timeout is killed."""
    policy = RunnerPolicy(timeout_seconds=1)
    # Sleep covers wall-clock time
    result = run_code("import time\ntime.sleep(2)", policy=policy)

    # It should timeout
    assert not result.ok
    assert result.timed_out
    assert (
        result.exit_code == 124
    )  # Standard timeout exit code (SIGTERM/9 + 128 usually, or specific)
    # The runner implementation returns 124 explicitly on subprocess.TimeoutExpired


def test_memory_limit_enforcement() -> None:
    """
    Verify that memory limit is enforced.
    Note: RLIMIT_AS includes virtual memory, so typical overheads apply.
    256MB is usually generous, let's try to allocate 500MB.
    """
    # Only meaningful on platforms supporting resource.RLIMIT_AS
    if sys.platform == "win32":
        pytest.skip("RLIMIT not supported on Windows")
    if sys.platform == "darwin":
        pytest.skip("RLIMIT_AS (Address Space) is often ignored/ineffective on macOS")

    policy = RunnerPolicy(memory_limit_mb=50)  # Strict limit 50MB

    # Try to allocate huge list
    # 50MB limit.
    # Create a list of integers. Each int is 28 bytes.
    # 100 million ints ~ 2.8GB
    code = """
x = [i for i in range(100_000_000)]
print(len(x))
"""
    result = run_code(code, policy=policy)

    assert not result.ok
    # Can report resource_exceeded or just a generic error/signal depending on how it dies
    # worker.py tries to catch MemoryError, but OS might kill it first with SIGKILL/SIGSEGV
    assert result.resource_exceeded or (result.exit_code != 0)

    if result.resource_exceeded:
        assert "Memory limit exceeded" in (result.error or "")


def test_infinite_loop_timeout() -> None:
    """Verify infinite loop is caught by timeout."""
    policy = RunnerPolicy(timeout_seconds=1)
    code = """
while True:
    pass
"""
    result = run_code(code, policy=policy)
    assert result.timed_out
    assert not result.ok


def test_large_output_limit() -> None:
    """Verify that stdout capture is truncated or handled if too large."""
    # The policy defines max_output_kb
    policy = RunnerPolicy(max_output_kb=10)  # 10KB

    # Print 20KB
    code = """
print("a" * (20 * 1024))
"""
    result = run_code(code, policy=policy)

    # It should succeed but truncate? Or just succeed?
    # worker.py implementation:
    # stdout_text = (stdout_buffer.getvalue() + printed_text)[:max_output_bytes]
    # It truncates.
    assert result.ok
    assert len(result.stdout) <= (10 * 1024)
    assert len(result.stdout) >= (9 * 1024)  # Should be full up to limit
