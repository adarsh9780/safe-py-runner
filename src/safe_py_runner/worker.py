from __future__ import annotations

import contextlib
import io
import json
import sys
import traceback
from typing import Any, Callable

_resource: Any
try:
    import resource as _resource_module  # POSIX only
    _resource = _resource_module
except Exception:  # pragma: no cover - platform specific
    _resource = None


def _inject_input_keys(
    exec_globals: dict[str, Any],
    input_data: Any,
    mode: str,
    allowed_globals: set[str],
    blocked_globals: set[str],
) -> None:
    """
    Convenience: expose input_data keys as top-level variables when safe.

    Example: input_data={"x": 9} enables user code `result = x ** 0.5`.
    """
    if not isinstance(input_data, dict):
        return
    reserved = {
        "__builtins__",
        "input_data",
        "result",
        "_print_",
        "_getattr_",
        "_write_",
        "_getiter_",
        "_getitem_",
        "_iter_unpack_sequence_",
        "_unpack_sequence_",
    }
    for key, value in input_data.items():
        key_str = str(key)
        if not key_str.isidentifier():
            continue
        if key_str in reserved or key_str.startswith("_"):
            continue
        if mode == "allow" and key_str not in allowed_globals:
            continue
        if mode == "restrict" and key_str in blocked_globals:
            continue
        if key_str not in exec_globals:
            exec_globals[key_str] = value


def _set_limits(memory_limit_mb: int) -> list[str]:
    errors: list[str] = []
    if _resource is None:
        errors.append("RLIMIT limits unavailable on this platform")
        return errors

    mem_bytes = int(memory_limit_mb) * 1024 * 1024

    try:
        _, current_hard = _resource.getrlimit(_resource.RLIMIT_AS)
        if current_hard in (-1, _resource.RLIM_INFINITY):
            target_hard = mem_bytes
        else:
            target_hard = min(mem_bytes, current_hard)
        target_soft = min(mem_bytes, target_hard)
        _resource.setrlimit(_resource.RLIMIT_AS, (target_soft, target_hard))
    except (ValueError, OSError) as exc:
        errors.append(f"RLIMIT_AS not applied: {exc}")

    return errors


def _safe_import_factory_mode(
    mode: str,
    allowed_imports: set[str],
    blocked_imports: set[str],
) -> Callable[..., Any]:
    def _safe_import(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: Any = (),
        level: int = 0,
    ) -> Any:
        if name == "importlib" or name.startswith("importlib."):
            raise ImportError("Import 'importlib' is blocked by policy")

        root = name.split(".")[0]
        if mode == "allow":
            if root not in allowed_imports:
                raise ImportError(f"Import '{name}' is not allowed by policy")
        elif root in blocked_imports:
            raise ImportError(f"Import '{name}' is blocked by policy")
        return __import__(name, globals, locals, fromlist, level)

    return _safe_import


def _build_safe_builtins(
    mode: str,
    allowed_builtins: set[str],
    blocked_builtins: set[str],
    safe_import: Any,
) -> dict[str, Any]:
    raw_builtins = __builtins__
    if isinstance(raw_builtins, dict):
        builtins_obj: dict[str, Any] = raw_builtins
    else:
        builtins_obj = vars(raw_builtins)

    safe = {}
    for name, value in builtins_obj.items():
        if mode == "allow":
            if name not in allowed_builtins:
                continue
        elif name in blocked_builtins:
            continue
        safe[name] = value

    safe["__import__"] = safe_import
    # Also block critical functions if not explicitly blocked but commonly dangerous
    # (Though policy usually handles this, specific overrides here add depth)
    return safe


def _normalize_system_exit(exit_code: Any) -> tuple[bool, int, str | None]:
    if exit_code in (None, 0):
        return True, 0, None
    if isinstance(exit_code, int):
        return False, exit_code, f"SystemExit: {exit_code}"
    return False, 1, f"SystemExit: {exit_code}"


def _filter_extra_globals(
    extra_globals: dict[str, Any],
    mode: str,
    allowed_globals: set[str],
    blocked_globals: set[str],
) -> dict[str, Any]:
    filtered: dict[str, Any] = {}
    for key, value in extra_globals.items():
        key_str = str(key)
        if mode == "allow" and key_str not in allowed_globals:
            continue
        if mode == "restrict" and key_str in blocked_globals:
            continue
        filtered[key_str] = value
    return filtered


def main() -> int:
    req = json.loads(sys.stdin.read() or "{}")
    code: str = req.get("code", "")
    input_data = req.get("input_data")
    policy = req.get("policy", {})

    memory_limit_mb = int(policy.get("memory_limit_mb", 256))
    max_output_kb = int(policy.get("max_output_kb", 128))
    mode = str(policy.get("mode", "restrict"))
    allowed_imports = set(policy.get("allowed_imports", []))
    blocked_imports = set(policy.get("blocked_imports", []))
    allowed_builtins = set(policy.get("allowed_builtins", []))
    blocked_builtins = set(policy.get("blocked_builtins", []))
    allowed_globals = set(policy.get("allowed_globals", []))
    blocked_globals = set(policy.get("blocked_globals", []))
    extra_globals = policy.get("extra_globals", {}) or {}

    try:
        if mode not in {"allow", "restrict"}:
            raise ValueError("mode must be 'allow' or 'restrict'")

        _set_limits(memory_limit_mb=memory_limit_mb)

        safe_import = _safe_import_factory_mode(mode, allowed_imports, blocked_imports)
        safe_builtins = _build_safe_builtins(
            mode, allowed_builtins, blocked_builtins, safe_import
        )

        # Pre-compile to catch SyntaxError before exec
        try:
            byte_code = compile(code, "<user_code>", "exec")
        except SyntaxError as e:
            # Format SyntaxError explicitly
            sys.stdout.write(
                json.dumps(
                    {
                        "ok": False,
                        "result": None,
                        "stdout": "",
                        "stderr": "",
                        "timed_out": False,
                        "resource_exceeded": False,
                        "error": f"SyntaxError: {e}",
                    }
                )
            )
            return 1

        exec_globals = {
            "__builtins__": safe_builtins,
            "input_data": input_data,
            "result": None,
        }
        exec_globals.update(
            _filter_extra_globals(extra_globals, mode, allowed_globals, blocked_globals)
        )
        _inject_input_keys(exec_globals, input_data, mode, allowed_globals, blocked_globals)

        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()

        system_exit: SystemExit | None = None
        try:
            with (
                contextlib.redirect_stdout(stdout_buffer),
                contextlib.redirect_stderr(stderr_buffer),
            ):
                exec(byte_code, exec_globals, exec_globals)
        except SystemExit as exc:
            # Preserve Python semantics: non-zero/str exits are failures.
            system_exit = exc
        except Exception as exc:
            # Capture runtime errors with traceback to give full context
            error_msg = f"{type(exc).__name__}: {exc}"

            # Also print stack into stderr for debugging if needed
            stderr_buffer.write(traceback.format_exc())

            # We set error to this message
            sys.stdout.write(
                json.dumps(
                    {
                        "ok": False,
                        "result": None,
                        "stdout": stdout_buffer.getvalue()[: max_output_kb * 1024],
                        "stderr": stderr_buffer.getvalue()[: max_output_kb * 1024],
                        "timed_out": False,
                        "resource_exceeded": False,
                        "error": error_msg,
                    },
                    default=str,
                )
            )
            return 1

        max_output_bytes = max_output_kb * 1024
        printed_text = str(exec_globals.get("printed", ""))
        ok = True
        worker_exit_code = 0
        error: str | None = None

        if system_exit is not None:
            ok, worker_exit_code, error = _normalize_system_exit(system_exit.code)
            if isinstance(system_exit.code, str):
                stderr_buffer.write(f"{system_exit.code}\n")

        stdout_text = (stdout_buffer.getvalue() + printed_text)[:max_output_bytes]
        stderr_text = stderr_buffer.getvalue()[:max_output_bytes]

        resp = {
            "ok": ok,
            "result": exec_globals.get("result"),
            "stdout": stdout_text,
            "stderr": stderr_text,
            "timed_out": False,
            "resource_exceeded": False,
            "error": error,
        }
        sys.stdout.write(json.dumps(resp, default=str))
        return worker_exit_code

    except MemoryError:
        sys.stdout.write(
            json.dumps(
                {
                    "ok": False,
                    "result": None,
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                    "resource_exceeded": True,
                    "error": "Memory limit exceeded",
                }
            )
        )
        return 2
    except Exception as e:
        # Fallback for unexpected runner errors (e.g. init failures)
        sys.stdout.write(
            json.dumps(
                {
                    "ok": False,
                    "result": None,
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                    "resource_exceeded": False,
                    "error": str(e),
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
