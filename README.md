# safe-py-runner

A lightweight Python code runner with guardrails for LLM agent workflows.

[![PyPI version](https://badge.fury.io/py/safe-py-runner.svg)](https://badge.fury.io/py/safe-py-runner)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Recent updates are tracked in [CHANGELOG.md](CHANGELOG.md).
Detailed docs are available in [docs/README.md](docs/README.md).

`safe-py-runner` runs user code in a separate subprocess with timeout, memory, and policy guardrails.
It is safer than running `eval` or `exec` in your main process.
It is not a full security sandbox and should not be your only isolation boundary for hostile public code.

Honest scope:
- Good fit: LLM-generated scripts for your own team, internal tools, controlled workloads.
- Not good alone: anonymous public code execution. Pair this with Docker/VM/OS sandboxing first.

## Where It Fits

| Option | Isolation Strength | Operational Cost | Typical Use |
| --- | --- | --- | --- |
| `eval` / `exec` in main process | Low | Low | Local scripts, trusted experiments |
| `safe-py-runner` | Medium | Low to medium | Internal tools, agent prototypes, controlled workloads |
| Docker / VM / E2B-style sandbox | High | Medium to high | Production multi-tenant or hostile untrusted code |

Production guidance:
- For hostile public-user code, use Docker/VM/external sandboxing as the primary boundary.
- `safe-py-runner` can still be useful as an inner guardrail layer inside that setup.

## Bubblewrap Comparison

If you want a direct comparison with Linux `bubblewrap` (`bwrap`) for import controls, memory limits, and timeouts, see:
[docs/BUBBLEWRAP_COMPARISON.md](docs/BUBBLEWRAP_COMPARISON.md)

## Features

- Process isolation: user code runs in a separate subprocess.
- Timeouts: terminate scripts that run too long (default 5s).
- Memory limits: enforce RAM caps (default 256MB) on POSIX systems.
- Import and builtin policy controls: blocklist/allowlist behavior via policy modes.
- Input/output marshalling: pass JSON-safe input and collect `result`, `stdout`, and `stderr`.

## Installation

```bash
pip install safe-py-runner
```

## Backends

`run_code` now takes an explicit engine object:

- `LocalEngine`: subprocess worker in a managed virtual environment.
- `DockerEngine`: worker inside a managed Docker container pool.

Example:

```python
from safe_py_runner import DockerEngine, run_code

engine = DockerEngine(container_registry="safe-py-runner-runtime:local")
result = run_code("result = 2 + 2", engine=engine)
```

Important behavior:
- If Docker is unavailable, DockerEngine returns a clear error (no silent fallback).
- Docker pool defaults: `pool_size=min(cpu_count, 4)`, `max_runs=25`, `ttl_seconds=600`.
- DockerEngine exposes managed-only admin methods: `list_containers`, `list_images`, `stop_container`, `kill_container`, `cleanup_stale`.

See [docs/BACKENDS.md](docs/BACKENDS.md) for full details.
See [docs/EXAMPLES.md](docs/EXAMPLES.md) for end-to-end examples.

## CLI (Container Management)

You can manage safe-py-runner managed Docker resources directly:

```bash
python -m spr list containers
python -m spr list images
python -m spr container <id-or-name>
python -m spr stop container <id>
python -m spr kill container <id>
python -m spr cleanup
```

Remote Docker targeting from CLI is supported:

```bash
python -m spr --docker-context my-remote-context list containers
python -m spr --ssh-host server --ssh-user ubuntu --ssh-port 22 list containers
```

Note: CLI commands are managed-only. They do not operate on unrelated Docker resources.

## Quick Start

```python
from functools import partial
from safe_py_runner import LocalEngine, RunnerPolicy, run_code

# Define a policy (optional, defaults are already restrictive)
policy = RunnerPolicy(
    timeout_seconds=5,
    memory_limit_mb=128,
    blocked_imports=["os", "subprocess", "socket"],
)

# Create engine once (required)
engine = LocalEngine(venv_dir="/tmp/safe_py_runner_demo_venv", venv_manager="uv")

# Optional convenience: bind engine for repeated calls
run_with_engine = partial(run_code, engine=engine)

# Run code
result = run_code(
    code="import math\nresult = math.sqrt(input_data['x'])",
    input_data={"x": 81},
    policy=policy,
    engine=engine,
)

if result.ok:
    print(f"Result: {result.result}")  # 9.0
else:
    print(f"Error: {result.error}")
```

### Shared Setup for Remaining Examples
To keep later snippets short, assume this setup:

```python
from functools import partial
from safe_py_runner import LocalEngine, run_code as _run_code

engine = LocalEngine(venv_dir="/absolute/path/to/your/project/.venv", venv_manager="uv")
run_code = partial(_run_code, engine=engine)
```

Important:
- Pass the full path to the virtual environment folder itself (for example `/repo/.venv`), not just the parent project directory.
- If `uv` is not installed, use `venv_manager="python"` and the engine will create the venv using `python -m venv`.

## Advanced Configuration

### Policy Modes
`safe-py-runner` supports two policy modes:

- `restrict` (default): block only what you list in `blocked_*`.
- `allow`: allow only what you list in `allowed_*`.

Example:

```python
policy = RunnerPolicy(
    mode="allow",
    allowed_imports=["math"],
    allowed_builtins=["len", "range", "print"],
    allowed_globals=["x"],
)
```

### Restrict Mode Example (default)
Use this when you want broad Python behavior but need to block risky symbols:

```python
policy = RunnerPolicy(
    mode="restrict",
    blocked_imports=["os", "subprocess", "socket"],
    blocked_builtins=["eval", "exec", "open"],
)

result = run_code(
    code="import math\nresult = math.factorial(5)",
    policy=policy,
)
```

### Allow Mode Example (strict)
Use this when you want explicit control over what code can access:

```python
policy = RunnerPolicy(
    mode="allow",
    allowed_imports=["math"],
    allowed_builtins=["print", "len", "range"],
    allowed_globals=["x", "helper"],
    extra_globals={"helper": 10},
)

result = run_code(
    code="import math\nresult = math.sqrt(x) + helper",
    input_data={"x": 81},
    policy=policy,
)
```

### Load Policy from Config File
Instead of hardcoding policy values, you can load them from a TOML file:

```toml
[policy]
mode = "restrict"
timeout_seconds = 5
memory_limit_mb = 256
max_output_kb = 128
blocked_imports = ["os", "subprocess"]
blocked_builtins = ["eval", "exec", "open"]
allowed_imports = []
allowed_builtins = []
allowed_globals = []
blocked_globals = []

[policy.extra_globals]
project_name = "safe-py-runner"
```

```python
result = run_code(
    code="result = 1 + 1",
    policy_file="/absolute/path/to/policy.toml",
)
```

### Policy File from Python
You can load a config file first, then pass it as a normal policy object:

```python
policy = RunnerPolicy.from_file("/absolute/path/to/policy.toml")
result = run_code(code="result = 1 + 1", policy=policy)
```

You can also set `config_path` directly:

```python
policy = RunnerPolicy(config_path="/absolute/path/to/policy.toml")
result = run_code(code="result = 1 + 1", policy=policy)
```

### Policy File Selection per Request
This is useful for multi-tenant systems where each tenant has its own policy:

```python
tenant_policy_map = {
    "team-a": "/policies/team-a.toml",
    "team-b": "/policies/team-b.toml",
}

tenant_id = "team-a"
result = run_code(
    code="result = len(data)",
    input_data={"data": [1, 2, 3]},
    policy_file=tenant_policy_map[tenant_id],
)
```

### I/O Examples

```python
# 1) Flat input values become top-level variables (when allowed by mode).
result = run_code(code="result = x + y", input_data={"x": 3, "y": 4})

# 2) Nested data works too.
result = run_code(
    code="result = customer['name'].upper()",
    input_data={"customer": {"name": "ada"}},
)

# 3) Printed output is captured separately from `result`.
result = run_code(code="print('hello')\nresult = 123")
print(result.stdout)  # hello
print(result.result)  # 123
```

### Timeout and Resource Limits Example

```python
policy = RunnerPolicy(timeout_seconds=1, memory_limit_mb=64, max_output_kb=8)

result = run_code(
    code="while True:\n    pass",
    policy=policy,
)

print(result.ok)        # False
print(result.timed_out) # True
```

### Output Truncation Example (`max_output_kb`)

```python
policy = RunnerPolicy(max_output_kb=4)  # 4KB output cap
result = run_code(code="print('a' * (10 * 1024))", policy=policy)
print(len(result.stdout) <= 4 * 1024)  # True
```

### `SystemExit` Behavior Example

```python
ok_exit = run_code("import sys\nsys.exit(0)")
print(ok_exit.ok, ok_exit.exit_code)  # True, 0

err_exit = run_code("import sys\nsys.exit(2)")
print(err_exit.ok, err_exit.exit_code, err_exit.error)  # False, 2, "SystemExit: 2"
```

### Error Handling Example

```python
result = run_code(code="import os")
if not result.ok:
    print("error:", result.error)
    print("stderr:", result.stderr)
    print("exit_code:", result.exit_code)
```

### Mode Behavior and Precedence

- In `allow` mode, only `allowed_*` lists are enforced.
- In `restrict` mode, only `blocked_*` lists are enforced.
- If you provide both allow and block lists, the non-active list is ignored by current behavior.

### Common Gotchas

1. This is not a full sandbox.
For hostile public-user code, use Docker/VM/E2B-style isolation in addition to this package.

2. `allow` mode can break common Python code if builtins are too strict.
Example: if `print` or `len` is missing from `allowed_builtins`, user code can fail with `NameError`.

3. In `allow` mode, both input key injection and `extra_globals` are filtered by `allowed_globals`.
If `x` is missing in `allowed_globals`, code like `result = x + 1` fails even when `input_data={"x": 1}`.
If `helper` is missing in `allowed_globals`, `extra_globals={"helper": 10}` is also ignored.

4. `importlib` is blocked intentionally in all modes.
It is blocked even if you include it in `allowed_imports`, to reduce indirect import bypass patterns.

5. Memory limits differ by engine and platform.
LocalEngine relies on `RLIMIT_AS` (POSIX only), which is usually stronger on Linux and may be weaker on macOS.
DockerEngine also applies container memory limits, which are generally more predictable than host `RLIMIT_AS`.

6. `policy` and `policy_file` are mutually exclusive.
Pass one or the other to `run_code`, not both.

7. `engine` is required.
`run_code(...)` no longer supports implicit backend selection.

8. Package installation for `LocalEngine(packages=...)` and `DockerEngine(packages=...)` only accepts pinned specs.
Use `name==version` format (for example `pandas==2.2.2`), not unpinned names.

9. DockerEngine does not silently fall back to local execution.
If Docker CLI/daemon is unavailable, the run fails with a clear error.

### API Reference

`run_code(...)` parameters:
- `code`: Python code string to execute.
- `engine`: required engine instance (`LocalEngine` or `DockerEngine`).
- `input_data`: optional dictionary available as `input_data` and key-injected globals.
- `policy`: optional `RunnerPolicy` object.
- `policy_file`: optional path to TOML policy config.

`RunnerResult` fields:
- `ok`, `result`, `stdout`, `stderr`, `timed_out`, `resource_exceeded`, `error`, `exit_code`.

### Using a Custom Python Environment
Use `LocalEngine(venv_dir=...)` to create/reuse an isolated virtual environment:

```python
from safe_py_runner import LocalEngine, run_code

engine = LocalEngine(
    venv_dir="/path/to/project/.venv",
    venv_manager="uv",
    packages=["pandas==2.2.2"],
)

run_code(
    code="...",
    engine=engine,
)
```

### Docker Engine Recommendation
For production multi-user workloads, prefer `DockerEngine`.
It gives stronger OS-level isolation than local subprocess execution.

Docker Desktop:
- macOS/Windows: https://www.docker.com/products/docker-desktop/
- Linux Engine docs: https://docs.docker.com/engine/install/

Remote daemon support is available through DockerEngine options:
`docker_context`, `docker_host`, `ssh_host`, `ssh_user`, `ssh_port`, and `ssh_key_path`.

## Security Note

**This is not an OS-level sandbox.**
It uses Python runtime hooks and resource limits to prevent accidents and basic misuse. For hosting code from anonymous/hostile users, you MUST pair this with Docker or similar isolation.

Memory limit note: `RLIMIT_AS` behavior is platform-dependent. In particular, macOS may not enforce this as strictly as Linux.

## Contributing

Contributions are welcome! Please open an issue or PR on GitHub.

## CI and Release Automation

- Push to `master`: runs CI tests automatically via GitHub Actions.
- Push a tag like `v0.1.1`: builds `sdist` + wheel, creates a GitHub Release, and publishes to PyPI via Trusted Publishing.

Release title/description are read from:

- `.github/release/metadata.json`

Trusted Publishing configuration expected by this repo:

- workflow name: `release`
- workflow file: `.github/workflows/release.yml`
- GitHub environment: `pypi`

Example `release_metadata.md`:

```md
# safe-py-runner {{tag}}

Release notes for {{tag}}.

- Summarize key changes here.
- Add migration notes if any.
```

`{{tag}}` is replaced automatically with the pushed tag name by the release workflow.

## Commit Workflow (Step-by-Step)

Assuming `commit_message.txt` is already updated:

1. Run quality checks:

```bash
make test
```

`make test` runs `ruff`, `mypy`, and `pytest` (in that order).

2. Stage files:

```bash
make git-add
```

3. Commit:

```bash
make git-commit
```

`make git-commit` validates:
- `commit_message.txt` exists and is non-empty
- `commit_message.txt` is different from the latest git commit message

4. Push to `master`:

```bash
make git-push
```

Optional shortcut:

```bash
make push
```

Note: if you already ran atomic steps (`make git-add` + `make git-commit`), you can run either `make git-push` or `make push`. `make push` is smart now: when there are no local file changes, it skips commit/test steps and only pushes.

## Release Workflow (Step-by-Step)

Assuming `commit_message.txt` and `release_metadata.md` are updated:

1. Bump version:

```bash
make set-version 0.1.2
```

2. Regenerate release metadata JSON:

```bash
make metadata
```

3. Run quality checks:

```bash
make test
```

4. Stage files:

```bash
make git-add
```

5. Commit:

```bash
make git-commit
```

6. Push to `master`:

```bash
make git-push
```

7. Create and push release tag:

```bash
make git-tag
```

`make git-tag` reads version from `pyproject.toml` and will fail if:
- a version argument is provided
- version in `pyproject.toml` is missing or invalid
- current tag from `pyproject.toml` is already the latest tag

Optional shortcut:

```bash
make release
```

Note: if you run release as atomic steps and already executed `make git-commit`, continue with `make git-push` and `make git-tag` (or run `make push` first; it will detect no local file changes and only push).

## Additional Recommended Steps

1. Run `make help` to see available commands.
2. Verify GitHub Actions CI passed on `master` before tagging.
3. After tagging, verify the release workflow succeeded and wheel artifact is attached.
