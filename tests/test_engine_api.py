import pytest

from safe_py_runner import DockerEngine, LocalEngine


def test_local_engine_requires_venv_dir() -> None:
    with pytest.raises(ValueError, match="venv_dir"):
        LocalEngine(venv_dir="")


def test_local_engine_rejects_unpinned_packages() -> None:
    with pytest.raises(ValueError, match="pinned"):
        LocalEngine(venv_dir="/tmp/safe_py_runner_unpinned_local", packages=["pandas"])


def test_docker_engine_rejects_unpinned_packages() -> None:
    with pytest.raises(ValueError, match="pinned"):
        DockerEngine(packages=["pandas"])
