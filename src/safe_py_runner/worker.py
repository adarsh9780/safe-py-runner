from __future__ import annotations

import contextlib
import io
import json
import sys
import traceback
from typing import Any

try:
    import resource  # POSIX only
except Exception:  # pragma: no cover - platform specific
    resource = None


def _inject_input_keys(exec_globals: dict[str, Any], input_data: Any) -> None:
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
        if key_str not in exec_globals:
            exec_globals[key_str] = value


def _set_limits(memory_limit_mb: int) -> list[str]:
    errors: list[str] = []
    if resource is None:
        errors.append("RLIMIT limits unavailable on this platform")
        return errors

    mem_bytes = int(memory_limit_mb) * 1024 * 1024

    try:
        _, current_hard = resource.getrlimit(resource.RLIMIT_AS)
        if current_hard in (-1, resource.RLIM_INFINITY):
            target_hard = mem_bytes
        else:
            target_hard = min(mem_bytes, current_hard)
        target_soft = min(mem_bytes, target_hard)
        resource.setrlimit(resource.RLIMIT_AS, (target_soft, target_hard))
    except (ValueError, OSError) as exc:
        errors.append(f"RLIMIT_AS not applied: {exc}")

    return errors


def _safe_import_factory_mode(
    blocked_imports: set[str],
):
    def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        # Prevent bypassing blocklist via importlib
        if name == "importlib" or name.startswith("importlib."):
            raise ImportError("Import 'importlib' is blocked by policy")

        root = name.split(".")[0]
        if root in blocked_imports:
            raise ImportError(f"Import '{name}' is blocked by policy")
        return __import__(name, globals, locals, fromlist, level)

    return _safe_import


def _build_safe_builtins(
    blocked_builtins: set[str],
    safe_import,
) -> dict[str, Any]:
    builtins_obj = __builtins__
    if not isinstance(builtins_obj, dict):
        builtins_obj = builtins_obj.__dict__

    safe = {}
    for name, value in builtins_obj.items():
        if name in blocked_builtins:
            continue
        safe[name] = value

    safe["__import__"] = safe_import
    # Also block critical functions if not explicitly blocked but commonly dangerous
    # (Though policy usually handles this, specific overrides here add depth)
    return safe


def main() -> int:
    req = json.loads(sys.stdin.read() or "{}")
    code: str = req.get("code", "")
    input_data = req.get("input_data")
    policy = req.get("policy", {})

    timeout_seconds = int(policy.get("timeout_seconds", 5))
    memory_limit_mb = int(policy.get("memory_limit_mb", 256))
    max_output_kb = int(policy.get("max_output_kb", 128))
    blocked_imports = set(policy.get("blocked_imports", []))
    blocked_builtins = set(policy.get("blocked_builtins", []))
    extra_globals = policy.get("extra_globals", {}) or {}

    try:
        _set_limits(memory_limit_mb=memory_limit_mb)

        safe_import = _safe_import_factory_mode(blocked_imports)
        safe_builtins = _build_safe_builtins(blocked_builtins, safe_import)

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
        exec_globals.update(extra_globals)
        _inject_input_keys(exec_globals, input_data)

        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()

        try:
            with (
                contextlib.redirect_stdout(stdout_buffer),
                contextlib.redirect_stderr(stderr_buffer),
            ):
                exec(byte_code, exec_globals, exec_globals)
        except SystemExit as e:
            # Handle sys.exit() calls gracefully
            # We treat this as a "success" execution but captured output
            # If code was 0, it's ok=True. If non-zero, ok=False?
            # Standard python behavior: exit(0) is success.
            # But we want to return JSON.
            # So we catch it, and continue to JSON serialization.
            # Note: sys.exit("error") sets code to "error"
            pass
        except Exception:
            # Capture runtime errors with traceback to give full context
            exc_type, exc_value, exc_traceback = sys.exc_info()
            # We only want the last part of the traceback usually, or simply the message with type
            # traceback.format_exc() gives the full stack.
            # We'll return detailed error message.
            error_msg = f"{exc_type.__name__}: {str(exc_value)}"

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
        stdout_text = (stdout_buffer.getvalue() + printed_text)[:max_output_bytes]
        stderr_text = stderr_buffer.getvalue()[:max_output_bytes]

        resp = {
            "ok": True,
            "result": exec_globals.get("result"),
            "stdout": stdout_text,
            "stderr": stderr_text,
            "timed_out": False,
            "resource_exceeded": False,
            "error": None,
        }
        sys.stdout.write(json.dumps(resp, default=str))
        return 0

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
