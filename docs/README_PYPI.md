# safe-py-runner

A lightweight, secure-by-default Python code runner designed for LLM agents.

[GitHub Repository](https://github.com/adarsh9780/safe-py-runner)

## Why This Package

When building agents that execute generated Python code, you often choose between:

1. Running code directly in your process (`exec`) - risky.
2. Full container sandboxing - heavier and slower.
3. External sandbox APIs - added cost and latency.

`safe-py-runner` provides a practical middle path:

- subprocess isolation
- timeout enforcement
- memory limits (POSIX; macOS enforcement can be weaker than Linux)
- secure-by-default import/builtin restrictions
- JSON-safe input/output handling

It supports two policy modes:
- `restrict` (default): block selected symbols.
- `allow`: allow only selected symbols.

## Installation

```bash
pip install safe-py-runner
```

## Quick Start

```python
from safe_py_runner import RunnerPolicy, run_code

policy = RunnerPolicy(
    timeout_seconds=5,
    memory_limit_mb=128,
    blocked_imports=["os", "subprocess", "socket"],
)

result = run_code(
    code="import math\nresult = math.sqrt(input_data['x'])",
    input_data={"x": 81},
    policy=policy,
)

# Or load policy from a TOML config file
result = run_code(code="result = 1 + 1", policy_file="/absolute/path/to/policy.toml")

if result.ok:
    print(result.result)  # 9.0
else:
    print(result.error)
```

## Security Note

This is not an OS-level sandbox.  
For untrusted hostile code, use container/VM isolation in addition to this package.

Memory-limit caveat: `RLIMIT_AS` is platform-dependent. On macOS, address-space limits may not behave as strictly as Linux.

## More Information

- Full documentation and contributor workflow: [README.md](https://github.com/adarsh9780/safe-py-runner/blob/master/README.md)
- Security policy: [SECURITY.md](https://github.com/adarsh9780/safe-py-runner/blob/master/SECURITY.md)
- Issue tracker: [GitHub Issues](https://github.com/adarsh9780/safe-py-runner/issues)
