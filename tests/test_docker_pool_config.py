import os
import time

from safe_py_runner.execution.config import DockerPoolSettings, default_pool_settings
from safe_py_runner.execution.docker_pool import ContainerLease, should_rotate


def test_pool_default_size_is_cpu_with_cap() -> None:
    settings = default_pool_settings(timeout_seconds=5)
    assert settings.pool_size == min(os.cpu_count() or 1, 4)


def test_default_acquire_timeout_uses_policy_timeout() -> None:
    settings = default_pool_settings(timeout_seconds=8)
    assert settings.acquire_timeout == 10


def test_rotation_by_runs_threshold() -> None:
    now = time.time()
    lease = ContainerLease(container_name="c0", created_at=now, last_used_at=now, run_count=25)
    settings = DockerPoolSettings(pool_size=1, max_runs=25, ttl_seconds=600, acquire_timeout=7)
    assert should_rotate(lease, settings, now=time.time()) is True


def test_rotation_by_ttl_threshold() -> None:
    now = time.time()
    lease = ContainerLease(container_name="c0", created_at=now - 601, last_used_at=now, run_count=1)
    settings = DockerPoolSettings(pool_size=1, max_runs=25, ttl_seconds=600, acquire_timeout=7)
    assert should_rotate(lease, settings, now=now) is True
