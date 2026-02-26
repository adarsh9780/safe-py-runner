from __future__ import annotations

import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Mapping

from .config import DockerPoolSettings


@dataclass(slots=True)
class ContainerLease:
    """Leased pooled container metadata.

    Example:
        ```python
        lease = ContainerLease("safe-py-runner-a1", 0.0, 0.0, 0)
        ```
    """

    container_name: str
    created_at: float
    last_used_at: float
    run_count: int


@dataclass(slots=True)
class _ContainerEntry:
    """Internal pool entry tracking lease state.

    Example:
        ```python
        entry = _ContainerEntry(lease=lease, in_use=False)
        ```
    """

    lease: ContainerLease
    in_use: bool


def should_rotate(lease: ContainerLease, settings: DockerPoolSettings, now: float) -> bool:
    """Decide whether a pooled container should be rotated.

    Example:
        ```python
        rotate = should_rotate(lease, settings, now=time.time())
        ```
    """
    if lease.run_count >= settings.max_runs:
        return True
    return (now - lease.created_at) >= settings.ttl_seconds


class DockerPool:
    """Manage a warm pool of reusable Docker containers.

    Example:
        ```python
        pool = DockerPool()
        ```
    """

    def __init__(self) -> None:
        """Initialize an empty thread-safe pool.

        Example:
            ```python
            pool = DockerPool()
            ```
        """
        self._lock = threading.Lock()
        self._by_image: dict[str, list[_ContainerEntry]] = {}

    def acquire(
        self,
        *,
        image: str,
        settings: DockerPoolSettings,
        memory_limit_mb: int,
        labels: dict[str, str],
        docker_env: Mapping[str, str],
        docker_context: str | None,
    ) -> ContainerLease:
        """Acquire a running container lease for an image.

        Example:
            ```python
            lease = pool.acquire(image="safe-py-runner-runtime:local", settings=settings, memory_limit_mb=256, labels={}, docker_env=os.environ, docker_context=None)
            ```
        """
        deadline = time.time() + settings.acquire_timeout
        while True:
            with self._lock:
                entries = self._by_image.setdefault(image, [])
                self._rotate_locked(
                    entries,
                    settings,
                    docker_env=docker_env,
                    docker_context=docker_context,
                )

                for entry in entries:
                    if entry.in_use:
                        continue
                    if not self._is_running(
                        entry.lease.container_name,
                        docker_env=docker_env,
                        docker_context=docker_context,
                    ):
                        self._remove_entry_locked(
                            entries,
                            entry,
                            docker_env=docker_env,
                            docker_context=docker_context,
                        )
                        continue
                    entry.in_use = True
                    return entry.lease

                if len(entries) < settings.pool_size:
                    lease = self._create_container(
                        image=image,
                        memory_limit_mb=memory_limit_mb,
                        labels=labels,
                        docker_env=docker_env,
                        docker_context=docker_context,
                    )
                    entries.append(_ContainerEntry(lease=lease, in_use=True))
                    return lease

            if time.time() >= deadline:
                raise TimeoutError(
                    f"Timed out acquiring Docker container from pool after {settings.acquire_timeout}s"
                )
            time.sleep(0.05)

    def release(
        self,
        *,
        image: str,
        container_name: str,
        mark_bad: bool = False,
        docker_env: Mapping[str, str] | None = None,
        docker_context: str | None = None,
    ) -> None:
        """Release a lease back to the pool and update rotation counters.

        Example:
            ```python
            pool.release(image="img:tag", container_name="safe-py-runner-a1")
            ```
        """
        env = docker_env or {}
        with self._lock:
            entries = self._by_image.get(image, [])
            for entry in list(entries):
                if entry.lease.container_name != container_name:
                    continue
                entry.in_use = False
                entry.lease.last_used_at = time.time()
                entry.lease.run_count += 1
                if mark_bad:
                    self._remove_entry_locked(
                        entries,
                        entry,
                        docker_env=env,
                        docker_context=docker_context,
                    )
                return

    def _rotate_locked(
        self,
        entries: list[_ContainerEntry],
        settings: DockerPoolSettings,
        *,
        docker_env: Mapping[str, str],
        docker_context: str | None,
    ) -> None:
        """Rotate stale pooled containers that exceed run or TTL limits.

        Example:
            ```python
            pool._rotate_locked(entries, settings, docker_env=os.environ, docker_context=None)
            ```
        """
        now = time.time()
        for entry in list(entries):
            if entry.in_use:
                continue
            if should_rotate(entry.lease, settings, now):
                self._remove_entry_locked(
                    entries,
                    entry,
                    docker_env=docker_env,
                    docker_context=docker_context,
                )

    def _remove_entry_locked(
        self,
        entries: list[_ContainerEntry],
        entry: _ContainerEntry,
        *,
        docker_env: Mapping[str, str],
        docker_context: str | None,
    ) -> None:
        """Remove a pooled entry and delete its backing container.

        Example:
            ```python
            pool._remove_entry_locked(entries, entry, docker_env=os.environ, docker_context=None)
            ```
        """
        self._stop_and_remove(
            entry.lease.container_name,
            docker_env=docker_env,
            docker_context=docker_context,
        )
        entries.remove(entry)

    def _create_container(
        self,
        *,
        image: str,
        memory_limit_mb: int,
        labels: dict[str, str],
        docker_env: Mapping[str, str],
        docker_context: str | None,
    ) -> ContainerLease:
        """Start a hardened runtime container and return its lease metadata.

        Example:
            ```python
            lease = pool._create_container(image="img:tag", memory_limit_mb=256, labels={}, docker_env=os.environ, docker_context=None)
            ```
        """
        name = f"safe-py-runner-{uuid.uuid4().hex[:12]}"
        mem_mb = max(128, int(memory_limit_mb))
        cmd = [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            name,
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "256",
            "--memory",
            f"{mem_mb}m",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=128m",
        ]
        for key, value in labels.items():
            cmd.extend(["--label", f"{key}={value}"])
        cmd.extend([image, "sleep", "infinity"])
        completed = subprocess.run(
            self._docker_cmd(cmd, docker_context=docker_context),
            capture_output=True,
            text=True,
            check=False,
            env=dict(docker_env),
        )
        if completed.returncode != 0:
            raise RuntimeError(f"Failed to start Docker container: {completed.stderr.strip()}")
        now = time.time()
        return ContainerLease(container_name=name, created_at=now, last_used_at=now, run_count=0)

    def _is_running(
        self,
        container_name: str,
        *,
        docker_env: Mapping[str, str],
        docker_context: str | None,
    ) -> bool:
        """Check if a specific container is running.

        Example:
            ```python
            running = pool._is_running("safe-py-runner-a1", docker_env=os.environ, docker_context=None)
            ```
        """
        completed = subprocess.run(
            self._docker_cmd(
                ["inspect", "-f", "{{.State.Running}}", container_name],
                docker_context=docker_context,
            ),
            capture_output=True,
            text=True,
            check=False,
            env=dict(docker_env),
        )
        return completed.returncode == 0 and completed.stdout.strip() == "true"

    def _stop_and_remove(
        self,
        container_name: str,
        *,
        docker_env: Mapping[str, str],
        docker_context: str | None,
    ) -> None:
        """Force-remove a specific container.

        Example:
            ```python
            pool._stop_and_remove("safe-py-runner-a1", docker_env=os.environ, docker_context=None)
            ```
        """
        subprocess.run(
            self._docker_cmd(["rm", "-f", container_name], docker_context=docker_context),
            capture_output=True,
            text=True,
            check=False,
            env=dict(docker_env),
        )

    def _docker_cmd(self, args: list[str], *, docker_context: str | None) -> list[str]:
        """Build a Docker CLI command with optional context.

        Example:
            ```python
            cmd = pool._docker_cmd(["ps"], docker_context="remote")
            ```
        """
        cmd = ["docker"]
        if docker_context:
            cmd.extend(["--context", docker_context])
        cmd.extend(args)
        return cmd


GLOBAL_DOCKER_POOL = DockerPool()
