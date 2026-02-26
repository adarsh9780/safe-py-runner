import pytest

from safe_py_runner import DockerEngine


def test_docker_context_conflicts_with_docker_host() -> None:
    with pytest.raises(ValueError, match="either docker_context"):
        DockerEngine(docker_context="remote", docker_host="ssh://user@host")


def test_ssh_user_requires_ssh_host() -> None:
    with pytest.raises(ValueError, match="ssh_user requires ssh_host"):
        DockerEngine(ssh_user="alice")


def test_ssh_env_is_constructed() -> None:
    engine = DockerEngine(ssh_host="example.com", ssh_user="alice", ssh_port=2222)
    env = engine._docker_env()  # noqa: SLF001 - validating internal connection config
    assert env["DOCKER_HOST"] == "ssh://alice@example.com"
    assert "-p 2222" in env["DOCKER_SSH_COMMAND"]
