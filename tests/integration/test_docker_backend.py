import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from safe_py_runner import DockerEngine, RunnerPolicy, run_code


def _docker_ready() -> bool:
    if shutil.which("docker") is None:
        return False
    return os.getenv("RUN_DOCKER_TESTS") == "1"


pytestmark = pytest.mark.skipif(not _docker_ready(), reason="Docker integration tests disabled")


@pytest.fixture(scope="module")
def docker_test_image() -> str:
    root = Path(__file__).resolve().parents[2]
    tag = "safe-py-runner-test:local"
    build = subprocess.run(
        [
            "docker",
            "build",
            "-t",
            tag,
            "-f",
            str(root / "docker" / "runtime" / "Dockerfile"),
            str(root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if build.returncode != 0:
        pytest.skip(f"Could not build docker test image: {build.stderr}")
    return tag


def test_docker_basic_exec(docker_test_image: str) -> None:
    engine = DockerEngine(container_registry=docker_test_image)
    result = run_code("result = 3 * 7", engine=engine)
    assert result.ok is True
    assert result.result == 21


def test_docker_import_blocking_parity(docker_test_image: str) -> None:
    policy = RunnerPolicy(blocked_imports=["os"])
    engine = DockerEngine(container_registry=docker_test_image)
    result = run_code("import os", policy=policy, engine=engine)
    assert result.ok is False
    assert "blocked by policy" in (result.error or "")


def test_docker_builtin_blocking_parity(docker_test_image: str) -> None:
    policy = RunnerPolicy(blocked_builtins=["eval"])
    engine = DockerEngine(container_registry=docker_test_image)
    result = run_code("result = eval('1+1')", policy=policy, engine=engine)
    assert result.ok is False


def test_docker_timeout_parity(docker_test_image: str) -> None:
    engine = DockerEngine(container_registry=docker_test_image, acquire_timeout_seconds=1)
    result = run_code("while True:\n    pass", engine=engine, policy=RunnerPolicy(timeout_seconds=1))
    assert result.ok is False
    assert result.timed_out or "timed out" in (result.error or "").lower()


def test_docker_memory_limit_behavior(docker_test_image: str) -> None:
    policy = RunnerPolicy(memory_limit_mb=64)
    engine = DockerEngine(container_registry=docker_test_image)
    result = run_code("x = [i for i in range(50_000_000)]", policy=policy, engine=engine)
    assert result.ok is False


def test_docker_pool_reuse_and_rotation_by_runs(docker_test_image: str) -> None:
    engine = DockerEngine(container_registry=docker_test_image, max_runs=1)
    first = run_code("result = 1", engine=engine)
    second = run_code("result = 2", engine=engine)
    assert first.ok and second.ok


def test_docker_pool_rotation_by_ttl(docker_test_image: str) -> None:
    engine = DockerEngine(container_registry=docker_test_image, ttl_seconds=1)
    first = run_code("result = 10", engine=engine)
    time.sleep(1.2)
    second = run_code("result = 11", engine=engine)
    assert first.ok and second.ok


def test_docker_workspace_reset_between_runs(docker_test_image: str) -> None:
    engine = DockerEngine(container_registry=docker_test_image)
    first = run_code(
        "from pathlib import Path\nPath('/tmp/safe_py_runner_marker').write_text('x')\nresult=1",
        engine=engine,
    )
    second = run_code(
        "from pathlib import Path\nresult = Path('/tmp/safe_py_runner_marker').exists()",
        engine=engine,
    )
    assert first.ok is True
    assert second.ok is True
    assert second.result is False


def test_docker_management_api(docker_test_image: str) -> None:
    engine = DockerEngine(container_registry=docker_test_image)
    run_code("result = 42", engine=engine)
    containers = engine.list_containers(all_states=True)
    assert len(containers) >= 1
    assert all("safe-py-runner" in container.name for container in containers)
    assert isinstance(engine.list_images(), list)


def test_docker_packages_build_cached_image() -> None:
    engine = DockerEngine(packages=["packaging==24.1"], name="itest")
    first = run_code("import packaging\nresult = packaging.__version__", engine=engine)
    second = run_code("import packaging\nresult = packaging.__version__", engine=engine)
    assert first.ok and second.ok
    assert first.result == "24.1"
    assert len(engine.list_images()) >= 1


def test_docker_stop_kill_non_managed_rejected() -> None:
    engine = DockerEngine()
    with pytest.raises(ValueError):
        engine.stop_container("definitely-not-managed")
    with pytest.raises(ValueError):
        engine.kill_container("definitely-not-managed")


def test_docker_unavailable_hard_fail(monkeypatch: pytest.MonkeyPatch, docker_test_image: str) -> None:
    monkeypatch.setenv("PATH", "")
    engine = DockerEngine(container_registry=docker_test_image)
    result = run_code("result = 1", engine=engine)
    assert result.ok is False
    assert "Docker" in (result.error or "")
