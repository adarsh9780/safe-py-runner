from safe_py_runner.execution.capabilities import capabilities_for_backend


def test_local_and_docker_capabilities_support_policy_controls() -> None:
    local = capabilities_for_backend("local")
    docker = capabilities_for_backend("docker")

    assert local.supports_import_blocking
    assert local.supports_builtin_blocking
    assert local.supports_memory_limit
    assert local.supports_timeout

    assert docker.supports_import_blocking
    assert docker.supports_builtin_blocking
    assert docker.supports_memory_limit
    assert docker.supports_timeout
