from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Mapping

from .config import (
    CleanupSummary,
    ContainerInfo,
    DockerPoolSettings,
    ImageInfo,
    LOCAL_RUNTIME_IMAGE,
    MANAGED_LABELS_BASE,
    MANAGED_LABEL_VALUE,
    DEFAULT_DOCKER_IMAGE,
    default_pool_settings,
    env_hash,
    validate_pinned_packages,
)
from .docker_pool import GLOBAL_DOCKER_POOL
from .types import ExecutionOutcome, ExecutionRequest


def docker_is_available(*, docker_env: Mapping[str, str], docker_context: str | None) -> tuple[bool, str | None]:
    """Check Docker CLI and daemon accessibility for the selected target.

    Example:
        ```python
        ok, reason = docker_is_available(docker_env=os.environ, docker_context=None)
        ```
    """
    if shutil.which("docker") is None:
        return False, "Docker CLI was not found. Install Docker and ensure it is on PATH."
    cmd = ["docker"]
    if docker_context:
        cmd.extend(["--context", docker_context])
    cmd.append("info")
    probe = subprocess.run(cmd, capture_output=True, text=True, check=False, env=dict(docker_env))
    if probe.returncode != 0:
        return False, "Docker is installed but the daemon is not running or not accessible."
    return True, None


def _repo_root() -> Path:
    """Return repository root path used for local Docker builds.

    Example:
        ```python
        root = _repo_root()
        ```
    """
    return Path(__file__).resolve().parents[3]


class DockerEngine:
    """Execute code in Docker with pooled containers and managed controls.

    Example:
        ```python
        engine = DockerEngine(container_registry="safe-py-runner-runtime:local")
        ```
    """

    def __init__(
        self,
        *,
        packages: list[str] | None = None,
        container_registry: str | None = None,
        name: str | None = None,
        pool_size: int | None = None,
        max_runs: int | None = None,
        ttl_seconds: int | None = None,
        acquire_timeout_seconds: int | None = None,
        docker_host: str | None = None,
        docker_context: str | None = None,
        ssh_host: str | None = None,
        ssh_user: str | None = None,
        ssh_port: int | None = None,
        ssh_key_path: str | None = None,
    ) -> None:
        """Initialize Docker execution settings and connection strategy.

        Example:
            ```python
            engine = DockerEngine(ssh_host="server", ssh_user="ubuntu", ssh_port=22)
            ```
        """
        self._packages = validate_pinned_packages(packages)
        self._container_registry = container_registry
        self._name = name
        self._pool_size = pool_size
        self._max_runs = max_runs
        self._ttl_seconds = ttl_seconds
        self._acquire_timeout_seconds = acquire_timeout_seconds
        self._docker_host = docker_host
        self._docker_context = docker_context
        self._ssh_host = ssh_host
        self._ssh_user = ssh_user
        self._ssh_port = ssh_port
        self._ssh_key_path = ssh_key_path
        self._cached_image: str | None = None
        self._validate_connection_options()

    def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        """Execute one request inside a pooled Docker container.

        Example:
            ```python
            outcome = engine.execute(ExecutionRequest(payload={"code": "result = 1"}, timeout_seconds=5))
            ```
        """
        available, reason = docker_is_available(
            docker_env=self._docker_env(),
            docker_context=self._docker_context,
        )
        if not available:
            return ExecutionOutcome("", "", 125, False, reason)

        image = self._resolve_image()
        memory_limit_mb = int(request.payload.get("policy", {}).get("memory_limit_mb", 256))
        timeout_seconds = int(request.timeout_seconds)
        settings = self._pool_settings(timeout_seconds)
        env_key = self._environment_key()
        labels = {**MANAGED_LABELS_BASE, "safe_py_runner.env_hash": env_key}

        lease = None
        mark_bad = False
        try:
            lease = GLOBAL_DOCKER_POOL.acquire(
                image=image,
                settings=settings,
                memory_limit_mb=memory_limit_mb,
                labels=labels,
                docker_env=self._docker_env(),
                docker_context=self._docker_context,
            )
            prep = self._run_docker(
                [
                    "exec",
                    lease.container_name,
                    "sh",
                    "-lc",
                    "rm -rf /tmp/* /tmp/.[!.]* /tmp/..?* 2>/dev/null || true; mkdir -p /tmp/safe_py_runner",
                ]
            )
            if prep.returncode != 0:
                mark_bad = True
                return ExecutionOutcome(
                    "",
                    prep.stderr,
                    prep.returncode,
                    False,
                    "Failed to prepare docker workspace",
                )
            workdir = f"/tmp/safe_py_runner/run_{int(time.time() * 1000)}"
            prep_dir = self._run_docker(["exec", lease.container_name, "mkdir", "-p", workdir])
            if prep_dir.returncode != 0:
                mark_bad = True
                return ExecutionOutcome(
                    "",
                    prep_dir.stderr,
                    prep_dir.returncode,
                    False,
                    "Failed to create docker run workspace",
                )

            cmd = [
                "docker",
            ]
            if self._docker_context:
                cmd.extend(["--context", self._docker_context])
            cmd.extend(
                [
                "exec",
                "-i",
                "-w",
                workdir,
                lease.container_name,
                "python",
                "-m",
                "safe_py_runner.worker",
                ]
            )
            try:
                completed = subprocess.run(
                    cmd,
                    input=json.dumps(request.payload),
                    capture_output=True,
                    text=True,
                    timeout=max(1, timeout_seconds),
                    check=False,
                    env=self._docker_env(),
                )
            except subprocess.TimeoutExpired:
                mark_bad = True
                return ExecutionOutcome(
                    "",
                    "",
                    124,
                    True,
                    f"Execution timed out after {timeout_seconds}s",
                )
            return ExecutionOutcome(
                completed.stdout,
                completed.stderr,
                completed.returncode,
                False,
            )
        except (RuntimeError, TimeoutError) as exc:
            return ExecutionOutcome("", "", 125, False, str(exc))
        finally:
            if lease is not None:
                GLOBAL_DOCKER_POOL.release(
                    image=image,
                    container_name=lease.container_name,
                    mark_bad=mark_bad,
                    docker_env=self._docker_env(),
                    docker_context=self._docker_context,
                )

    def list_containers(self, all_states: bool = False) -> list[ContainerInfo]:
        """List managed containers visible to this engine target.

        Example:
            ```python
            containers = engine.list_containers(all_states=True)
            ```
        """
        fmt = "{{.ID}}|{{.Names}}|{{.Image}}|{{.State}}|{{.Status}}"
        cmd = ["ps", "--filter", f"label=safe_py_runner.managed={MANAGED_LABEL_VALUE}", "--format", fmt]
        if all_states:
            cmd.insert(1, "-a")
        out = self._run_docker(cmd)
        if out.returncode != 0:
            raise RuntimeError(f"Failed to list containers: {out.stderr.strip()}")
        items: list[ContainerInfo] = []
        for line in out.stdout.splitlines():
            if not line.strip():
                continue
            c_id, name, image, state, status = line.split("|", 4)
            items.append(ContainerInfo(c_id, name, image, state, status))
        return items

    def list_images(self) -> list[ImageInfo]:
        """List managed images visible to this engine target.

        Example:
            ```python
            images = engine.list_images()
            ```
        """
        fmt = "{{.ID}}|{{.Repository}}|{{.Tag}}|{{.CreatedSince}}|{{.Size}}"
        out = self._run_docker(
            ["image", "ls", "--filter", "label=safe_py_runner.managed=true", "--format", fmt]
        )
        if out.returncode != 0:
            raise RuntimeError(f"Failed to list images: {out.stderr.strip()}")
        images: list[ImageInfo] = []
        for line in out.stdout.splitlines():
            if not line.strip():
                continue
            i_id, repo, tag, created, size = line.split("|", 4)
            images.append(ImageInfo(i_id, repo, tag, created, size))
        return images

    def stop_container(self, container_id: str, timeout_seconds: int = 10) -> None:
        """Gracefully stop a managed container.

        Example:
            ```python
            engine.stop_container("abc123", timeout_seconds=5)
            ```
        """
        self._ensure_managed_container(container_id)
        stopped = self._run_docker(["stop", "-t", str(timeout_seconds), container_id])
        if stopped.returncode != 0:
            raise RuntimeError(f"Failed to stop container: {stopped.stderr.strip()}")

    def kill_container(self, container_id: str) -> None:
        """Force-kill a managed container.

        Example:
            ```python
            engine.kill_container("abc123")
            ```
        """
        self._ensure_managed_container(container_id)
        killed = self._run_docker(["kill", container_id])
        if killed.returncode != 0:
            raise RuntimeError(f"Failed to kill container: {killed.stderr.strip()}")

    def cleanup_stale(self) -> CleanupSummary:
        """Delete stopped managed containers and removable managed images.

        Example:
            ```python
            summary = engine.cleanup_stale()
            ```
        """
        removed_containers = 0
        for container in self.list_containers(all_states=True):
            if container.state != "running":
                removed = self._run_docker(["rm", "-f", container.id])
                if removed.returncode == 0:
                    removed_containers += 1

        removed_images = 0
        for image in self.list_images():
            ref = f"{image.repository}:{image.tag}"
            removed = self._run_docker(["image", "rm", ref])
            if removed.returncode == 0:
                removed_images += 1
        return CleanupSummary(removed_containers=removed_containers, removed_images=removed_images)

    def _ensure_managed_container(self, container_id: str) -> None:
        """Ensure a container is labeled as safe-py-runner managed.

        Example:
            ```python
            engine._ensure_managed_container("abc123")
            ```
        """
        check = self._run_docker(
            [
                "inspect",
                "-f",
                "{{ index .Config.Labels \"safe_py_runner.managed\" }}",
                container_id,
            ]
        )
        if check.returncode != 0:
            raise ValueError(
                f"Container '{container_id}' is not managed by safe-py-runner and cannot be modified"
            )
        if check.stdout.strip() != MANAGED_LABEL_VALUE:
            raise ValueError(
                f"Container '{container_id}' is not managed by safe-py-runner and cannot be modified"
            )

    def _pool_settings(self, timeout_seconds: int) -> DockerPoolSettings:
        """Resolve effective pool settings for this run.

        Example:
            ```python
            settings = engine._pool_settings(timeout_seconds=5)
            ```
        """
        defaults = default_pool_settings(timeout_seconds)
        return DockerPoolSettings(
            pool_size=self._pool_size or defaults.pool_size,
            max_runs=self._max_runs or defaults.max_runs,
            ttl_seconds=self._ttl_seconds or defaults.ttl_seconds,
            acquire_timeout=self._acquire_timeout_seconds or defaults.acquire_timeout,
        )

    def _environment_key(self) -> str:
        """Compute deterministic environment key for package-image caching.

        Example:
            ```python
            key = engine._environment_key()
            ```
        """
        return env_hash(
            python_version="3.11",
            packages=self._packages,
            namespace=self._name,
        )

    def _resolve_image(self) -> str:
        """Resolve runtime image using explicit, package, GHCR, then local fallback.

        Example:
            ```python
            image = engine._resolve_image()
            ```
        """
        if self._cached_image is not None:
            return self._cached_image
        if self._container_registry:
            self._cached_image = self._container_registry
            self._ensure_image_available(self._cached_image)
            return self._cached_image
        if self._packages:
            tag = f"safe-py-runner-env:{self._environment_key()}"
            self._ensure_package_image(tag)
            self._cached_image = tag
            return tag

        if self._ensure_image_available(DEFAULT_DOCKER_IMAGE):
            self._cached_image = DEFAULT_DOCKER_IMAGE
            return self._cached_image

        self._build_local_runtime_image(LOCAL_RUNTIME_IMAGE)
        self._cached_image = LOCAL_RUNTIME_IMAGE
        return self._cached_image

    def _ensure_image_available(self, image: str) -> bool:
        """Ensure an image exists locally, pulling when needed.

        Example:
            ```python
            ok = engine._ensure_image_available("python:3.11-slim")
            ```
        """
        inspected = self._run_docker(["image", "inspect", image])
        if inspected.returncode == 0:
            return True
        pulled = self._run_docker(["pull", image])
        return pulled.returncode == 0

    def _build_local_runtime_image(self, tag: str) -> None:
        """Build local runtime image from repository Dockerfile.

        Example:
            ```python
            engine._build_local_runtime_image("safe-py-runner-runtime:local")
            ```
        """
        root = _repo_root()
        built = self._run_docker(
            ["build", "-t", tag, "-f", str(root / "docker" / "runtime" / "Dockerfile"), str(root)]
        )
        if built.returncode != 0:
            raise RuntimeError(f"Failed to build local runtime image: {built.stderr.strip()}")

    def _ensure_package_image(self, tag: str) -> None:
        """Build or reuse a package-specific image identified by tag.

        Example:
            ```python
            engine._ensure_package_image("safe-py-runner-env:abcd1234")
            ```
        """
        if self._run_docker(["image", "inspect", tag]).returncode == 0:
            return
        root = _repo_root()
        base_image = DEFAULT_DOCKER_IMAGE if self._ensure_image_available(DEFAULT_DOCKER_IMAGE) else LOCAL_RUNTIME_IMAGE
        if base_image == LOCAL_RUNTIME_IMAGE:
            self._build_local_runtime_image(LOCAL_RUNTIME_IMAGE)
        with tempfile.TemporaryDirectory(prefix="safe-py-runner-docker-build-") as tmp:
            dockerfile = Path(tmp) / "Dockerfile"
            labels = "\n".join(
                [f'LABEL {k}="{v}"' for k, v in {**MANAGED_LABELS_BASE, "safe_py_runner.env_hash": self._environment_key()}.items()]
            )
            packages = " ".join(self._packages)
            dockerfile.write_text(
                (
                    f"FROM {base_image}\n"
                    f"{labels}\n"
                    f"RUN python -m pip install {packages}\n"
                ),
                encoding="utf-8",
            )
            built = self._run_docker(["build", "-t", tag, "-f", str(dockerfile), str(root)])
            if built.returncode != 0:
                raise RuntimeError(f"Failed to build package image: {built.stderr.strip()}")

    def _run_docker(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        """Run a Docker CLI command against the configured target.

        Example:
            ```python
            completed = engine._run_docker(["ps"])
            ```
        """
        cmd = ["docker"]
        if self._docker_context:
            cmd.extend(["--context", self._docker_context])
        cmd.extend(args)
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            env=self._docker_env(),
        )

    def _docker_env(self) -> dict[str, str]:
        """Build environment variables for Docker CLI targeting.

        Example:
            ```python
            env = engine._docker_env()
            ```
        """
        env = dict(os.environ)
        docker_host = self._docker_host
        if self._ssh_host:
            user = f"{self._ssh_user}@" if self._ssh_user else ""
            docker_host = f"ssh://{user}{self._ssh_host}"
        if docker_host:
            env["DOCKER_HOST"] = docker_host
        if self._ssh_host:
            parts = ["ssh"]
            if self._ssh_port:
                parts.extend(["-p", str(self._ssh_port)])
            if self._ssh_key_path:
                parts.extend(["-i", self._ssh_key_path])
            env["DOCKER_SSH_COMMAND"] = " ".join(parts)
        return env

    def _validate_connection_options(self) -> None:
        """Validate mutually exclusive Docker connection settings.

        Example:
            ```python
            engine._validate_connection_options()
            ```
        """
        if self._docker_context and (self._docker_host or self._ssh_host):
            raise ValueError("Use either docker_context or docker_host/ssh settings, not both")
        if self._ssh_user and not self._ssh_host:
            raise ValueError("ssh_user requires ssh_host")
        if self._ssh_port and not self._ssh_host:
            raise ValueError("ssh_port requires ssh_host")
        if self._ssh_key_path and not self._ssh_host:
            raise ValueError("ssh_key_path requires ssh_host")
