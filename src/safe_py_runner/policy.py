from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _default_policy_path() -> Path:
    """Return bundled default policy TOML path.

    Example:
        ```python
        path = _default_policy_path()
        ```
    """
    return Path(__file__).with_name("default_policy.toml")


def _read_policy_toml(path: Path) -> dict[str, Any]:
    """Read policy TOML and return normalized policy dictionary.

    Example:
        ```python
        raw = _read_policy_toml(Path("/tmp/policy.toml"))
        ```
    """
    if not path.exists():
        return {
            "mode": "restrict",
            "timeout_seconds": 5,
            "memory_limit_mb": 256,
            "max_output_kb": 128,
            "blocked_imports": ["os", "subprocess", "socket", "ctypes", "importlib"],
            "blocked_builtins": ["eval", "exec", "open", "compile", "breakpoint"],
            "allowed_imports": [],
            "allowed_builtins": [],
            "allowed_globals": [],
            "blocked_globals": [],
        }
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    policy_obj = raw.get("policy", raw)
    if not isinstance(policy_obj, dict):
        raise ValueError("Policy config must be a TOML table")
    return policy_obj


def _list_of_str(value: Any, field_name: str) -> list[str]:
    """Validate and normalize a list-of-strings policy field.

    Example:
        ```python
        blocked = _list_of_str(["os", "subprocess"], "blocked_imports")
        ```
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"'{field_name}' must be a list of strings")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"'{field_name}' must contain only strings")
        out.append(item)
    return out


_DEFAULT_POLICY_RAW = _read_policy_toml(_default_policy_path())
DEFAULT_MODE = str(_DEFAULT_POLICY_RAW.get("mode", "restrict"))
DEFAULT_TIMEOUT_SECONDS = int(_DEFAULT_POLICY_RAW.get("timeout_seconds", 5))
DEFAULT_MEMORY_LIMIT_MB = int(_DEFAULT_POLICY_RAW.get("memory_limit_mb", 256))
DEFAULT_MAX_OUTPUT_KB = int(_DEFAULT_POLICY_RAW.get("max_output_kb", 128))
DEFAULT_BLOCKED_IMPORTS = _list_of_str(
    _DEFAULT_POLICY_RAW.get("blocked_imports", []), "blocked_imports"
)
DEFAULT_BLOCKED_BUILTINS = _list_of_str(
    _DEFAULT_POLICY_RAW.get("blocked_builtins", []), "blocked_builtins"
)
DEFAULT_ALLOWED_IMPORTS = _list_of_str(
    _DEFAULT_POLICY_RAW.get("allowed_imports", []), "allowed_imports"
)
DEFAULT_ALLOWED_BUILTINS = _list_of_str(
    _DEFAULT_POLICY_RAW.get("allowed_builtins", []), "allowed_builtins"
)
DEFAULT_ALLOWED_GLOBALS = _list_of_str(
    _DEFAULT_POLICY_RAW.get("allowed_globals", []), "allowed_globals"
)
DEFAULT_BLOCKED_GLOBALS = _list_of_str(
    _DEFAULT_POLICY_RAW.get("blocked_globals", []), "blocked_globals"
)


@dataclass(slots=True)
class RunnerPolicy:
    """Execution policy for untrusted Python code.

    Example:
        ```python
        policy = RunnerPolicy(timeout_seconds=5, blocked_imports=["os"])
        ```
    """

    mode: str = DEFAULT_MODE
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    memory_limit_mb: int = DEFAULT_MEMORY_LIMIT_MB
    max_output_kb: int = DEFAULT_MAX_OUTPUT_KB
    allowed_imports: list[str] = field(default_factory=lambda: DEFAULT_ALLOWED_IMPORTS.copy())
    blocked_imports: list[str] = field(default_factory=lambda: DEFAULT_BLOCKED_IMPORTS.copy())
    allowed_builtins: list[str] = field(default_factory=lambda: DEFAULT_ALLOWED_BUILTINS.copy())
    blocked_builtins: list[str] = field(default_factory=lambda: DEFAULT_BLOCKED_BUILTINS.copy())
    allowed_globals: list[str] = field(default_factory=lambda: DEFAULT_ALLOWED_GLOBALS.copy())
    blocked_globals: list[str] = field(default_factory=lambda: DEFAULT_BLOCKED_GLOBALS.copy())
    extra_globals: dict[str, Any] = field(default_factory=dict)
    config_path: str | None = None

    def __post_init__(self) -> None:
        """Validate mode after dataclass initialization.

        Example:
            ```python
            RunnerPolicy(mode="restrict")
            ```
        """
        if self.mode not in {"allow", "restrict"}:
            raise ValueError("mode must be 'allow' or 'restrict'")

    @classmethod
    def from_file(cls, config_path: str) -> "RunnerPolicy":
        """Create a policy instance from a TOML file.

        Example:
            ```python
            policy = RunnerPolicy.from_file("/tmp/policy.toml")
            ```
        """
        raw = _read_policy_toml(Path(config_path))
        extra_globals_raw = raw.get("extra_globals", {})
        if not isinstance(extra_globals_raw, dict):
            raise ValueError("'extra_globals' must be a TOML table")
        return cls(
            mode=str(raw.get("mode", DEFAULT_MODE)),
            timeout_seconds=int(raw.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)),
            memory_limit_mb=int(raw.get("memory_limit_mb", DEFAULT_MEMORY_LIMIT_MB)),
            max_output_kb=int(raw.get("max_output_kb", DEFAULT_MAX_OUTPUT_KB)),
            allowed_imports=_list_of_str(raw.get("allowed_imports", []), "allowed_imports"),
            blocked_imports=_list_of_str(raw.get("blocked_imports", []), "blocked_imports"),
            allowed_builtins=_list_of_str(
                raw.get("allowed_builtins", []), "allowed_builtins"
            ),
            blocked_builtins=_list_of_str(
                raw.get("blocked_builtins", []), "blocked_builtins"
            ),
            allowed_globals=_list_of_str(raw.get("allowed_globals", []), "allowed_globals"),
            blocked_globals=_list_of_str(raw.get("blocked_globals", []), "blocked_globals"),
            extra_globals=extra_globals_raw,
            config_path=config_path,
        )


@dataclass(slots=True)
class RunnerResult:
    """Normalized execution result returned by `run_code`.

    Example:
        ```python
        result = RunnerResult(ok=True, result=42)
        ```
    """

    ok: bool
    result: Any = None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    resource_exceeded: bool = False
    error: str | None = None
    exit_code: int = 0
