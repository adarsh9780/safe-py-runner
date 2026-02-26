import pytest

from safe_py_runner import LocalEngine, run_code


def test_engine_required() -> None:
    with pytest.raises(TypeError):
        run_code("result = 2 + 2")  # type: ignore[call-arg]


def test_local_engine_executes() -> None:
    engine = LocalEngine(venv_dir="/tmp/safe_py_runner_test_backend_routing")
    result = run_code("result = 2 + 2", engine=engine)
    assert result.ok is True
    assert result.result == 4
