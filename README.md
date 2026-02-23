# safe-py-runner

A lightweight, secure-by-default Python code runner designed for LLM agents.

[![PyPI version](https://badge.fury.io/py/safe-py-runner.svg)](https://badge.fury.io/py/safe-py-runner)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**The Missing Middleware for AI Agents:**
When building agents that write code, you often face a dilemma:
1.  **Run Blindly:** Use `exec()` in your main process (Dangerous, fragile).
2.  **Full Sandbox:** Spin up Docker containers for every execution (Heavy, slow, complex).
3.  **SaaS:** Pay for external sandbox APIs (Expensive, latency).

**`safe-py-runner` offers a middle path:** It runs code in a **subprocess** with **timeout**, **memory limits**, and **input/output marshalling**. It's perfect for internal tools, data analysis agents, and POCs where full Docker isolation is overkill.

## Features

- 🛡️ **Process Isolation:** User code runs in a separate subprocess, protecting your main app from crashes.
- ⏱️ **Timeouts:** Automatically kill scripts that run too long (default 5s).
- 💾 **Memory Limits:** Enforce RAM usage caps (default 256MB) on POSIX systems.
- 🚫 **Import Blocklist:** Prevent access to dangerous modules (`os`, `subprocess`, `socket`).
- 📦 **Magic I/O:** Automatically injects input variables and captures results as JSON.

## Installation

```bash
pip install safe-py-runner
```

## Quick Start

```python
from safe_py_runner import RunnerPolicy, run_code

# Define a policy (optional, defaults are safe)
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

## Advanced Configuration

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
```

## Security Note

**This is not an OS-level sandbox.**
It uses Python runtime hooks and resource limits to prevent accidents and basic misuse. For hosting code from anonymous/hostile users, you MUST pair this with Docker or similar isolation.

## Contributing

Contributions are welcome! Please open an issue or PR on GitHub.

## CI and Release Automation

- Push to `main`: runs CI tests automatically via GitHub Actions.
- Push a tag like `v0.1.1`: builds a wheel and creates a GitHub Release with the wheel attached.

Release title/description are read from:

- `.github/release/metadata.json`

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

## Additional Recommended Steps

1. Run `make help` to see available commands.
2. Verify GitHub Actions CI passed on `main` before tagging.
3. After tagging, verify the release workflow succeeded and wheel artifact is attached.
