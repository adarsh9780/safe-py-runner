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

## Release Steps (Contributors)

Step 1: Update `release_metadata.md` in project root (this file is local and gitignored).

Step 2: Run metadata generator:

```bash
uv run python scripts/generate_release_metadata.py
```

Step 3: Bump version in `pyproject.toml` (for example `0.1.0` -> `0.1.1`).

Step 4: Run tests locally:

```bash
uv run --extra dev pytest
```

Step 5: Commit and push changes to `main` (including `.github/release/metadata.json`).

Step 6: Create and push release tag:

```bash
git tag -a v0.1.1 -m "Release v0.1.1"
git push origin v0.1.1
```

Step 7: Verify GitHub Actions release workflow succeeded and wheel is attached to the GitHub Release.

## Test and Push Steps (Contributors)

Step 1: Run tests locally:

```bash
uv run --extra dev pytest
```

Step 2: Stage files:

```bash
git add .
```

Step 3: Commit:

```bash
git commit -m "Describe your change"
```

Step 4: Push to `main`:

```bash
git push origin main
```
