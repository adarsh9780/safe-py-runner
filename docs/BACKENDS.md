# Backends

`safe-py-runner` uses explicit engine objects.

## API

```python
from safe_py_runner import LocalEngine, DockerEngine, run_code

local = LocalEngine(venv_dir="/tmp/safe_py_runner_local")
docker = DockerEngine(container_registry="safe-py-runner-runtime:local")

result = run_code("result = 1 + 1", engine=local)
result = run_code("result = 1 + 1", engine=docker)
```

## LocalEngine

- Requires `venv_dir`.
- Creates/reuses the virtual environment automatically.
- Optional `packages=[...]` supports pinned package installation (`name==version`).
- `venv_dir` must be the full path to the virtual environment folder (for example `/repo/.venv`).
- If `venv_manager="uv"` and `uv` is unavailable, use `venv_manager="python"` to fallback to `python -m venv`.

## DockerEngine

- Runs worker in hardened containers (`--network none`, read-only root, dropped caps).
- Uses warm pool with rotation:
  - `pool_size=min(cpu_count, 4)`
  - `max_runs=25`
  - `ttl_seconds=600`
- Supports package environments:
  - package specs must be pinned (`name==version`)
  - builds image once per environment hash and reuses it
- Remote daemon targeting options:
  - `docker_context="my-context"`
  - `docker_host="ssh://user@server"` or SSH fields (`ssh_host`, `ssh_user`, `ssh_port`, `ssh_key_path`)

### Image Resolution

1. If `container_registry` is provided, use that image.
2. If `packages` are provided, build/reuse hash-tagged image.
3. Otherwise try default GHCR runtime image.
4. If GHCR pull is unavailable, auto-build local runtime image from `docker/runtime/Dockerfile`.

Caching behavior:
- Image pull/build happens once per image tag.
- Later runs reuse existing local image cache.

## Managed Resource Controls

DockerEngine exposes managed-only controls:

- `list_containers(all_states=False)`
- `list_images()`
- `stop_container(container_id, timeout_seconds=10)`
- `kill_container(container_id)`
- `cleanup_stale()`

Only resources labeled as safe-py-runner managed are controlled by these methods.

## CLI Controls

The same managed controls are available via CLI:

```bash
python -m spr list containers
python -m spr list images
python -m spr container <id-or-name>
python -m spr stop container <id>
python -m spr kill container <id>
python -m spr cleanup
```

Remote options:

```bash
python -m spr --docker-context my-remote-context list containers
python -m spr --ssh-host server --ssh-user ubuntu --ssh-port 22 list containers
```

## Docker Setup

Recommended for production workloads.

- Docker Desktop (macOS/Windows): https://www.docker.com/products/docker-desktop/
- Docker Engine install docs (Linux): https://docs.docker.com/engine/install/

Basic validation:

```bash
docker ps
docker images
```

## Production Note: Remote Docker Hosts

You can run DockerEngine against a remote Docker daemon directly through constructor options.

Example with context:

```python
from safe_py_runner import DockerEngine

engine = DockerEngine(docker_context="my-remote-context")
```

Example with SSH:

```python
from safe_py_runner import DockerEngine

engine = DockerEngine(
    ssh_host="my-server.example.com",
    ssh_user="ubuntu",
    ssh_port=22,
    ssh_key_path="/home/me/.ssh/id_ed25519",
)
```

Rules:
- Use either `docker_context` or `docker_host/ssh_*`, not both.
- If you do not pass these options, DockerEngine uses your current local Docker CLI defaults.

You can still use environment-level Docker configuration if preferred.

## Migration Note

Old backend arguments on `run_code` were removed.
Use `run_code(..., engine=LocalEngine(...))` or `run_code(..., engine=DockerEngine(...))`.
