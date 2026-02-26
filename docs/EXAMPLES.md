# Examples

This page shows practical usage patterns for `safe-py-runner`.

## 1) LocalEngine with Existing `.venv`

```python
from safe_py_runner import LocalEngine, run_code

engine = LocalEngine(
    venv_dir="/absolute/path/to/your/project/.venv",
    venv_manager="uv",
)

result = run_code("result = 2 + 2", engine=engine)
print(result.ok, result.result)
```

Note: `venv_dir` should point to the virtual environment directory itself (usually `.venv`).

## 2) LocalEngine with Python Venv Fallback (no `uv`)

```python
from safe_py_runner import LocalEngine, run_code

engine = LocalEngine(
    venv_dir="/absolute/path/to/your/project/.venv",
    venv_manager="python",
)

result = run_code("result = 10 + 5", engine=engine)
print(result.result)
```

## 3) LocalEngine with Pinned Packages

```python
from safe_py_runner import LocalEngine, run_code

engine = LocalEngine(
    venv_dir="/absolute/path/to/your/project/.venv",
    packages=["pandas==2.2.2", "numpy==1.26.4"],
)

result = run_code("import pandas as pd\nresult = pd.__version__", engine=engine)
print(result.result)
```

## 4) DockerEngine with Explicit Image

```python
from safe_py_runner import DockerEngine, run_code

engine = DockerEngine(container_registry="safe-py-runner-runtime:local")
result = run_code("result = 6 * 7", engine=engine)
print(result.ok, result.result, result.error)
```

## 5) DockerEngine with Package-Built Environment

```python
from safe_py_runner import DockerEngine, run_code

engine = DockerEngine(
    packages=["packaging==24.1"],
    name="packaging-demo",
)

first = run_code("import packaging\nresult = packaging.__version__", engine=engine)
second = run_code("import packaging\nresult = packaging.__version__", engine=engine)

print(first.result, second.result)
```

First run may build image; later runs reuse cached image.

## 6) DockerEngine with Policy

```python
from safe_py_runner import DockerEngine, RunnerPolicy, run_code

engine = DockerEngine(container_registry="safe-py-runner-runtime:local")
policy = RunnerPolicy(blocked_imports=["os"])

result = run_code("import os", engine=engine, policy=policy)
print(result.ok, result.error)
```

## 7) Docker Managed Resource Controls

```python
from safe_py_runner import DockerEngine

engine = DockerEngine(container_registry="safe-py-runner-runtime:local")

print(engine.list_containers(all_states=True))
print(engine.list_images())

# Managed-only safety checks apply.
# engine.stop_container("<managed_container_id>")
# engine.kill_container("<managed_container_id>")
```

## 8) Remote Docker Host (Production Pattern)

Use constructor options directly:

```python
from safe_py_runner import DockerEngine

engine = DockerEngine(docker_context="my-remote-context")
```

or

```python
from safe_py_runner import DockerEngine

engine = DockerEngine(
    ssh_host="my-server.example.com",
    ssh_user="ubuntu",
    ssh_port=22,
    ssh_key_path="/home/me/.ssh/id_ed25519",
)
```

Then run your Python app with `run_code(..., engine=engine)` normally.

## 9) CLI Container Operations

```bash
python -m spr list containers
python -m spr list images
python -m spr container <id-or-name>
python -m spr stop container <id>
python -m spr kill container <id>
python -m spr cleanup
```

Remote examples:

```bash
python -m spr --docker-context my-remote-context list containers
python -m spr --ssh-host server --ssh-user ubuntu --ssh-port 22 list containers
```
