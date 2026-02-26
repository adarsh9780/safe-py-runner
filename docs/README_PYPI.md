# safe-py-runner

A lightweight Python code runner with guardrails for LLM agent workflows.

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
- import/builtin policy restrictions
- JSON-safe input/output handling

## Where It Fits

| Option | Isolation Strength | Operational Cost | Typical Use |
| --- | --- | --- | --- |
| `eval` / `exec` in main process | Low | Low | Local scripts, trusted experiments |
| `safe-py-runner` | Medium | Low to medium | Internal tools, agent prototypes, controlled workloads |
| Docker / VM / E2B-style sandbox | High | Medium to high | Production multi-tenant or hostile untrusted code |

Production guidance:
- For hostile public-user code, use Docker/VM/external sandboxing as the primary boundary.
- `safe-py-runner` can be used as an extra inner guardrail layer.

It supports two policy modes:
- `restrict` (default): block selected symbols.
- `allow`: allow only selected symbols.

## Backends

The API now uses explicit engine objects through `run_code(..., engine=...)`.

- `LocalEngine`: host subprocess execution in managed venv.
- `DockerEngine`: managed Docker container execution.

If DockerEngine is used but Docker is unavailable, execution fails with a clear error.
DockerEngine can also target remote daemons with `docker_context` or SSH options.

Docker installation:
- Docker Desktop (macOS/Windows): https://www.docker.com/products/docker-desktop/
- Docker Engine docs (Linux): https://docs.docker.com/engine/install/

For production workloads, prefer DockerEngine over LocalEngine.

## Installation

```bash
pip install safe-py-runner
```

## Quick Start

```python
from safe_py_runner import LocalEngine, RunnerPolicy, run_code

policy = RunnerPolicy(
    timeout_seconds=5,
    memory_limit_mb=128,
    blocked_imports=["os", "subprocess", "socket"],
)

engine = LocalEngine(venv_dir="/tmp/safe_py_runner_pypi_demo")

result = run_code(
    code="import math\nresult = math.sqrt(input_data['x'])",
    input_data={"x": 81},
    policy=policy,
    engine=engine,
)

# Or load policy from a TOML config file
result = run_code(
    code="result = 1 + 1",
    policy_file="/absolute/path/to/policy.toml",
    engine=engine,
)

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
