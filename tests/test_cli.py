from __future__ import annotations

import io

import pytest

from spr import cli


class _FakeContainer:
    def __init__(self, c_id: str, name: str) -> None:
        self.id = c_id
        self.name = name
        self.image = "img:tag"
        self.state = "running"
        self.status = "Up 10s"


class _FakeImage:
    def __init__(self, i_id: str) -> None:
        self.id = i_id
        self.repository = "safe-py-runner-env"
        self.tag = "v1"
        self.created_since = "1 minute ago"
        self.size = "123MB"


class _FakeSummary:
    def __init__(self) -> None:
        self.removed_containers = 1
        self.removed_images = 2


class _FakeEngine:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.stopped: tuple[str, int] | None = None
        self.killed: str | None = None

    def list_containers(self, all_states: bool = False):
        return [_FakeContainer("abc123", "safe-py-runner-1")]

    def list_images(self):
        return [_FakeImage("sha256:1")]

    def stop_container(self, container_id: str, timeout_seconds: int = 10) -> None:
        self.stopped = (container_id, timeout_seconds)

    def kill_container(self, container_id: str) -> None:
        self.killed = container_id

    def cleanup_stale(self):
        return _FakeSummary()


@pytest.fixture(autouse=True)
def _patch_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "DockerEngine", _FakeEngine)


def test_cli_list_containers(capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main(["list", "containers"])
    captured = capsys.readouterr()
    assert code == 0
    assert "safe-py-runner-1" in captured.out


def test_cli_stop_container(capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main(["stop", "container", "abc123", "--timeout-seconds", "3"])
    output = capsys.readouterr().out
    assert code == 0
    assert "Stopped container abc123" in output


def test_cli_stop_all_containers(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    class _StopAllEngine(_FakeEngine):
        stopped_ids: list[tuple[str, int]] = []

        def list_containers(self, all_states: bool = False):
            running = _FakeContainer("abc123", "safe-py-runner-1")
            exited = _FakeContainer("def456", "safe-py-runner-2")
            exited.state = "exited"
            return [running, exited]

        def stop_container(self, container_id: str, timeout_seconds: int = 10) -> None:
            self.__class__.stopped_ids.append((container_id, timeout_seconds))

    monkeypatch.setattr(cli, "DockerEngine", _StopAllEngine)
    _StopAllEngine.stopped_ids = []
    code = cli.main(["stop", "all", "--timeout-seconds", "7"])
    output = capsys.readouterr().out
    assert code == 0
    assert "Stopped 1 managed container(s) with timeout 7s" in output
    assert _StopAllEngine.stopped_ids == [("abc123", 7)]


def test_cli_stop_all_no_running_containers(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    class _NoRunningEngine(_FakeEngine):
        def list_containers(self, all_states: bool = False):
            exited = _FakeContainer("def456", "safe-py-runner-2")
            exited.state = "exited"
            return [exited]

    monkeypatch.setattr(cli, "DockerEngine", _NoRunningEngine)
    code = cli.main(["stop", "all"])
    output = capsys.readouterr().out
    assert code == 0
    assert "No running managed containers to stop." in output


def test_cli_container_not_found(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class _NoContainerEngine(_FakeEngine):
        def list_containers(self, all_states: bool = False):
            return []

    monkeypatch.setattr(cli, "DockerEngine", _NoContainerEngine)
    code = cli.main(["container", "missing"])
    output = capsys.readouterr().out
    assert code == 1
    assert "No managed container matched" in output


def test_cli_subcommand_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["stop", "--help"])
    output = capsys.readouterr().out
    assert exc.value.code == 0
    assert "Gracefully stop one managed container by id." in output


def test_cli_top_level_help_examples(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    output = capsys.readouterr().out
    assert exc.value.code == 0
    assert "Quick Examples:" in output
    assert "python -m spr list images" in output
    assert "Remote Examples:" in output


def test_cli_print_help_writes_to_requested_stream(capsys: pytest.CaptureFixture[str]) -> None:
    parser = cli.build_parser()
    buffer = io.StringIO()
    parser.print_help(file=buffer)
    output = capsys.readouterr().out
    assert output == ""
    help_text = buffer.getvalue()
    assert "Usage:" in help_text
    assert "safe-py-runner CLI" in help_text
