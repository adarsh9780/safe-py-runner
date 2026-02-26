from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass

DEFAULT_DOCKER_IMAGE = "ghcr.io/adarsh9780/safe-py-runner-runtime:py311"
LOCAL_RUNTIME_IMAGE = "safe-py-runner-runtime:local"
MANAGED_LABEL_VALUE = "true"
MANAGED_LABELS_BASE = {
    "safe_py_runner.managed": MANAGED_LABEL_VALUE,
    "safe_py_runner.engine": "docker",
    "safe_py_runner.project": "safe-py-runner",
}
_PINNED_PACKAGE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+==[^=\s]+$")


@dataclass(frozen=True, slots=True)
class DockerPoolSettings:
    """Runtime limits for the Docker container pool.

    Example:
        ```python
        settings = DockerPoolSettings(pool_size=4, max_runs=25, ttl_seconds=600, acquire_timeout=7)
        ```
    """

    pool_size: int
    max_runs: int
    ttl_seconds: int
    acquire_timeout: int


@dataclass(frozen=True, slots=True)
class ContainerInfo:
    """Snapshot of a managed container returned by DockerEngine.

    Example:
        ```python
        info = ContainerInfo("abc", "safe-py-runner-1", "img:tag", "running", "Up 2m")
        ```
    """

    id: str
    name: str
    image: str
    state: str
    status: str


@dataclass(frozen=True, slots=True)
class ImageInfo:
    """Snapshot of a managed image returned by DockerEngine.

    Example:
        ```python
        image = ImageInfo("sha256:1", "safe-py-runner-env", "v1", "1 hour ago", "215MB")
        ```
    """

    id: str
    repository: str
    tag: str
    created_since: str
    size: str


@dataclass(frozen=True, slots=True)
class CleanupSummary:
    """Result summary from Docker cleanup operations.

    Example:
        ```python
        summary = CleanupSummary(removed_containers=2, removed_images=1)
        ```
    """

    removed_containers: int
    removed_images: int


def default_pool_settings(timeout_seconds: int) -> DockerPoolSettings:
    """Return default Docker pool settings derived from a run timeout.

    Example:
        ```python
        defaults = default_pool_settings(timeout_seconds=5)
        ```
    """
    size = min(os.cpu_count() or 1, 4)
    return DockerPoolSettings(
        pool_size=size,
        max_runs=25,
        ttl_seconds=600,
        acquire_timeout=max(1, int(timeout_seconds)) + 2,
    )


def validate_pinned_packages(packages: list[str] | None) -> list[str]:
    """Validate and normalize pinned package specs.

    Example:
        ```python
        pkgs = validate_pinned_packages(["pandas==2.2.2", "numpy==1.26.4"])
        ```
    """
    if not packages:
        return []
    normalized = sorted({pkg.strip() for pkg in packages if pkg.strip()})
    for pkg in normalized:
        if not _PINNED_PACKAGE_PATTERN.match(pkg):
            raise ValueError(
                "Package specs must be pinned as 'name==version'. "
                f"Invalid package: {pkg}"
            )
    return normalized


def env_hash(
    *,
    python_version: str,
    packages: list[str],
    namespace: str | None,
) -> str:
    """Create a deterministic environment hash for image caching.

    Example:
        ```python
        key = env_hash(python_version="3.11", packages=["pandas==2.2.2"], namespace="demo")
        ```
    """
    material = f"{python_version}|{namespace or ''}|{'|'.join(packages)}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
