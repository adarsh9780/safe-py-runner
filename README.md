# safe-py-runner

A lightweight, secure-by-default Python code runner designed for LLM agents.

[![PyPI version](https://badge.fury.io/py/safe-py-runner.svg)](https://badge.fury.io/py/safe-py-runner)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Recent updates are tracked in [CHANGELOG.md](CHANGELOG.md).
Detailed docs are available in [docs/README.md](docs/README.md).

**The Missing Middleware for AI Agents:**
When building agents that write code, you often face a dilemma:
1.  **Run Blindly:** Use `exec()` in your main process (Dangerous, fragile).
2.  **Full Sandbox:** Spin up Docker containers for every execution (Heavy, slow, complex).
3.  **SaaS:** Pay for external sandbox APIs (Expensive, latency).

**`safe-py-runner` offers a middle path:** It runs code in a **subprocess** with **timeout**, **memory limits**, and **input/output marshalling**. It's perfect for internal tools, data analysis agents, and POCs where full Docker isolation is overkill.

## Features

- 🛡️ **Process Isolation:** User code runs in a separate subprocess, protecting your main app from crashes.
- ⏱️ **Timeouts:** Automatically kill scripts that run too long (default 5s).
- 💾 **Memory Limits:** Enforce RAM usage caps (default 256MB) on POSIX systems. On macOS, address-space limits can be weaker, so keep strict timeouts and use container isolation for stronger guarantees.
- 🚫 **Import/Builtin Blocklist:** Secure defaults block dangerous modules and builtins (for example `os`, `subprocess`, `socket`, `eval`, `exec`, and `open`).
- 📦 **Magic I/O:** Automatically injects input variables and captures results as JSON.

## Installation

```bash
pip install safe-py-runner
```

## Quick Start

```python
from safe_py_runner import RunnerPolicy, run_code

# Define a policy (optional, defaults are already restrictive)
policy = RunnerPolicy(
    timeout_seconds=5,
    memory_limit_mb=128,
    blocked_imports=["os", "subprocess", "socket"],
)

# Run code
result = run_code(
    code="import math\nresult = math.sqrt(input_data['x'])",
    input_data={"x": 81},
    policy=policy,
    # Optional: Path to a specific Python executable (e.g., in a venv)
    # python_executable="/path/to/venv/bin/python",
)

if result.ok:
    print(f"Result: {result.result}")  # 9.0
else:
    print(f"Error: {result.error}")
```

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
For hostile public-user code, use Docker/VM isolation in addition to this package.

2. `allow` mode can break common Python code if builtins are too strict.
Example: if `print` or `len` is missing from `allowed_builtins`, user code can fail with `NameError`.

3. In `allow` mode, input keys are only injected if listed in `allowed_globals`.
If `x` is missing in `allowed_globals`, code like `result = x + 1` fails.

4. `importlib` is blocked intentionally.
This prevents indirect import bypass patterns.

5. Memory limits vary by platform.
`RLIMIT_AS` is usually stronger on Linux and may be weaker on macOS.

6. `policy` and `policy_file` are mutually exclusive.
Pass one or the other to `run_code`, not both.

### API Reference

`run_code(...)` parameters:
- `code`: Python code string to execute.
- `input_data`: optional dictionary available as `input_data` and key-injected globals.
- `policy`: optional `RunnerPolicy` object.
- `policy_file`: optional path to TOML policy config.
- `python_executable`: optional Python interpreter path.

`RunnerResult` fields:
- `ok`, `result`, `stdout`, `stderr`, `timed_out`, `resource_exceeded`, `error`, `exit_code`.

### Using a Custom Python Environment
By default, `safe-py-runner` uses `sys.executable` (the same Python running your app).
To improve isolation or provide specific libraries to the runner, creating a dedicated virtual environment is recommended:

1. Create a venv: `python -m venv runner_env`
2. Install allowed packages: `runner_env/bin/pip install pandas numpy`
3. Pass the path to `run_code`:

```python
run_code(
    code="...",
    python_executable="/path/to/runner_env/bin/python"
)
```

## Security Note

**This is not an OS-level sandbox.**
It uses Python runtime hooks and resource limits to prevent accidents and basic misuse. For hosting code from anonymous/hostile users, you MUST pair this with Docker or similar isolation.

Memory limit note: `RLIMIT_AS` behavior is platform-dependent. In particular, macOS may not enforce this as strictly as Linux.

## Contributing

Contributions are welcome! Please open an issue or PR on GitHub.

## CI and Release Automation

- Push to `main`: runs CI tests automatically via GitHub Actions.
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

1. Run tests:

```bash
make test
```

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

4. Push to `main`:

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

3. Run tests:

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

6. Push to `main`:

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
2. Verify GitHub Actions CI passed on `main` before tagging.
3. After tagging, verify the release workflow succeeded and wheel artifact is attached.
