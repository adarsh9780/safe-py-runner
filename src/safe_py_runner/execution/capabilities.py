from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BackendCapabilities:
    """Capability flags advertised by a backend.

    Example:
        ```python
        caps = BackendCapabilities(True, True, True, True)
        ```
    """

    supports_import_blocking: bool
    supports_builtin_blocking: bool
    supports_memory_limit: bool
    supports_timeout: bool


def capabilities_for_backend(backend: str) -> BackendCapabilities:
    """Return capability flags for a backend name.

    Example:
        ```python
        caps = capabilities_for_backend("docker")
        ```
    """
    if backend in {"local", "localengine"}:
        return BackendCapabilities(True, True, True, True)
    if backend in {"docker", "dockerengine"}:
        return BackendCapabilities(True, True, True, True)
    return BackendCapabilities(False, False, False, False)


def preflight_validate_backend_capabilities(backend: str) -> None:
    """Run preflight capability checks for a backend.

    Example:
        ```python
        preflight_validate_backend_capabilities("local")
        ```
    """
    # Reserved hook for future E2B/Piston strict capability checks.
    _ = capabilities_for_backend(backend)
