from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .config import validate_pinned_packages
from .types import ExecutionOutcome, ExecutionRequest


def _worker_path() -> Path:
    """Return the absolute path to the worker module file.

    Example:
        ```python
        path = _worker_path()
        ```
    """
    return Path(__file__).resolve().parents[1] / "worker.py"


class LocalEngine:
    """Execute code locally using a managed virtual environment.

    Example:
        ```python
        engine = LocalEngine(venv_dir="/tmp/my_env", venv_manager="uv")
        ```
    """

    def __init__(
        self,
        *,
        venv_dir: str,
        venv_manager: str = "uv",
        packages: list[str] | None = None,
    ) -> None:
        """Initialize a local engine and prepare its environment.

        Example:
            ```python
            engine = LocalEngine(venv_dir="/tmp/my_env", packages=["packaging==24.1"])
            ```
        """
        cleaned = venv_dir.strip()
        if not cleaned:
            raise ValueError("LocalEngine requires a non-empty 'venv_dir'")
        self._venv_dir = Path(cleaned).expanduser()
        self._venv_manager = venv_manager
        self._packages = validate_pinned_packages(packages)
        self._prepare_environment()

    def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        """Execute one request in the local venv worker process.

        Example:
            ```python
            outcome = engine.execute(ExecutionRequest(payload={"code": "result = 1"}, timeout_seconds=5))
            ```
        """
        cmd = [str(self._python_path()), str(_worker_path())]
        try:
            completed = subprocess.run(
                cmd,
                input=json.dumps(request.payload),
                capture_output=True,
                text=True,
                timeout=max(1, int(request.timeout_seconds)),
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ExecutionOutcome(
                stdout="",
                stderr="",
                returncode=124,
                timed_out=True,
                error=f"Execution timed out after {request.timeout_seconds}s",
            )
        return ExecutionOutcome(
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
            timed_out=False,
        )

    def _prepare_environment(self) -> None:
        """Create/reuse venv and install pinned packages when needed.

        Example:
            ```python
            engine._prepare_environment()
            ```
        """
        self._venv_dir.mkdir(parents=True, exist_ok=True)
        py_path = self._python_path()
        if not py_path.exists():
            if self._venv_manager == "uv":
                created = subprocess.run(
                    ["uv", "venv", str(self._venv_dir)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if created.returncode != 0:
                    raise RuntimeError(f"Failed to create venv with uv: {created.stderr.strip()}")
            elif self._venv_manager == "python":
                created = subprocess.run(
                    [sys.executable, "-m", "venv", str(self._venv_dir)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if created.returncode != 0:
                    raise RuntimeError(f"Failed to create venv with python: {created.stderr.strip()}")
            else:
                raise ValueError("venv_manager must be either 'uv' or 'python'")
        if self._packages:
            marker = self._venv_dir / ".safe_py_runner_packages.txt"
            desired = "\n".join(self._packages) + "\n"
            if not marker.exists() or marker.read_text(encoding="utf-8") != desired:
                installed = subprocess.run(
                    [str(self._python_path()), "-m", "pip", "install", *self._packages],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if installed.returncode != 0:
                    raise RuntimeError(f"Failed to install local packages: {installed.stderr.strip()}")
                marker.write_text(desired, encoding="utf-8")

    def _python_path(self) -> Path:
        """Return the Python executable path inside the managed venv.

        Example:
            ```python
            py = engine._python_path()
            ```
        """
        return self._venv_dir / "bin" / "python"
