from __future__ import annotations

import argparse
from functools import partial
from dataclasses import fields, is_dataclass
from typing import Any, Never, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.pretty import Pretty
from rich.table import Table
from rich_argparse import RawTextRichHelpFormatter
from safe_py_runner import DockerEngine

_CONSOLE = Console(no_color=False)


class _CLIHelpFormatter(RawTextRichHelpFormatter):
    """Rich formatter with explicit high-contrast CLI styles.

    Example:
        ```python
        parser = argparse.ArgumentParser(formatter_class=_CLIHelpFormatter)
        ```
    """

    styles = {
        "argparse.args": "bold cyan",
        "argparse.groups": "bold magenta",
        "argparse.help": "white",
        "argparse.metavar": "bold yellow",
        "argparse.prog": "bold bright_blue",
        "argparse.syntax": "bold bright_white",
        "argparse.text": "bright_white",
    }


_HELP_FORMATTER = partial(
    _CLIHelpFormatter,
    max_help_position=34,
    width=120,
)


class _RichArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that renders errors via Rich.

    Example:
        ```python
        parser = _RichArgumentParser(prog="python -m spr")
        ```
    """

    def error(self, message: str) -> Never:
        """Render parse errors with Rich and exit.

        Example:
            ```python
            # parser.error("invalid usage")
            ```
        """
        _CONSOLE.print(Panel.fit(f"[bold red]Error:[/bold red] {message}", border_style="red"))
        self.print_help()
        raise SystemExit(2)

    def print_help(self, file: Any | None = None) -> None:
        """Render help text to the target stream.

        Example:
            ```python
            parser.print_help()
            ```
        """
        super().print_help(file=file)

    def print_usage(self, file: Any | None = None) -> None:
        """Render usage text to the target stream.

        Example:
            ```python
            parser.print_usage()
            ```
        """
        super().print_usage(file=file)


def _to_jsonable(value: object) -> Any:
    """Convert CLI return values into printable payloads.

    Example:
        ```python
        payload = _to_jsonable(result)
        ```
    """
    if not isinstance(value, type) and is_dataclass(value):
        return {field.name: getattr(value, field.name) for field in fields(value)}
    if hasattr(value, "__dict__"):
        return vars(value)
    return value


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for safe-py-runner container operations.

    Example:
        ```python
        parser = build_parser()
        ```
    """
    parser = _RichArgumentParser(
        prog="python -m spr",
        description=(
            "safe-py-runner CLI\n"
            "Manage only safe-py-runner-managed Docker resources.\n"
            "This CLI never modifies non-managed containers or images."
        ),
        epilog=(
            "Quick Examples:\n"
            "  python -m spr list containers\n"
            "  python -m spr list images\n"
            "  python -m spr container <id-or-name>\n"
            "  python -m spr stop container <id>\n"
            "  python -m spr kill container <id>\n"
            "  python -m spr cleanup\n\n"
            "Remote Examples:\n"
            "  python -m spr --docker-context my-remote-context list containers\n"
            "  python -m spr --docker-host ssh://ubuntu@server list containers\n"
            "  python -m spr --ssh-host server --ssh-user ubuntu --ssh-port 22 list containers"
        ),
        formatter_class=_HELP_FORMATTER,
    )
    parser.add_argument(
        "--docker-context",
        help=(
            "Use an existing Docker context name.\n"
            "Example: --docker-context prod-us-east\n"
            "Mutually exclusive with --docker-host and --ssh-host."
        ),
    )
    parser.add_argument(
        "--docker-host",
        help=(
            "Connect directly with DOCKER_HOST.\n"
            "Examples: ssh://user@server, tcp://host:2376"
        ),
    )
    parser.add_argument(
        "--ssh-host",
        help=(
            "SSH shortcut for remote Docker.\n"
            "Builds DOCKER_HOST=ssh://<user>@<host> from SSH options."
        ),
    )
    parser.add_argument(
        "--ssh-user",
        help="SSH username used with --ssh-host (default: current OS user).",
    )
    parser.add_argument(
        "--ssh-port",
        type=int,
        help="SSH port used with --ssh-host (default: 22).",
    )
    parser.add_argument(
        "--ssh-key-path",
        help="Path to SSH private key file used with --ssh-host.",
    )

    sub = parser.add_subparsers(
        dest="command",
        required=True,
        parser_class=_RichArgumentParser,
    )

    list_cmd = sub.add_parser(
        "list",
        help="List managed containers or images.",
        description=(
            "List resources created and labeled by safe-py-runner.\n"
            "Use this command to inspect pool state and cached images."
        ),
        formatter_class=_HELP_FORMATTER,
    )
    list_cmd_sub = list_cmd.add_subparsers(
        dest="resource",
        required=True,
        parser_class=_RichArgumentParser,
    )
    list_cmd_sub.add_parser(
        "containers",
        help="List managed containers.",
        description=(
            "Show managed containers in running and exited states.\n"
            "Includes id, name, image, state, and status."
        ),
        formatter_class=_HELP_FORMATTER,
    )
    list_cmd_sub.add_parser(
        "images",
        help="List managed images.",
        description=(
            "Show managed image cache entries.\n"
            "Includes repository, tag, age, and size."
        ),
        formatter_class=_HELP_FORMATTER,
    )

    container_cmd = sub.add_parser(
        "container",
        help="Show one managed container by id prefix or exact name.",
        description=(
            "Show details for one managed container.\n"
            "Accepts exact name or id prefix."
        ),
        epilog=(
            "Examples:\n"
            "  python -m spr container 8a91e1c\n"
            "  python -m spr container safe-py-runner-2"
        ),
        formatter_class=_HELP_FORMATTER,
    )
    container_cmd.add_argument("container_id")

    stop_cmd = sub.add_parser(
        "stop",
        help="Gracefully stop managed container resources.",
        description=(
            "Stop commands operate only on managed containers.\n"
            "Use `spr stop container <id>` for a graceful stop."
        ),
        epilog=(
            "Examples:\n"
            "  python -m spr stop container abc123\n"
            "  python -m spr stop container abc123 --timeout-seconds 10\n"
            "  python -m spr stop all --timeout-seconds 10"
        ),
        formatter_class=_HELP_FORMATTER,
    )
    stop_cmd_sub = stop_cmd.add_subparsers(
        dest="resource",
        required=True,
        parser_class=_RichArgumentParser,
    )
    stop_container = stop_cmd_sub.add_parser(
        "container",
        help="Gracefully stop one managed container by id.",
        description="Gracefully stop a managed container and allow clean shutdown.",
        formatter_class=_HELP_FORMATTER,
    )
    stop_container.add_argument("container_id")
    stop_container.add_argument(
        "--timeout-seconds",
        type=int,
        default=10,
        help="Grace period before force kill by Docker (default: 10).",
    )
    stop_all = stop_cmd_sub.add_parser(
        "all",
        help="Gracefully stop all running managed containers.",
        description="Gracefully stop all currently running managed containers.",
        formatter_class=_HELP_FORMATTER,
    )
    stop_all.add_argument(
        "--timeout-seconds",
        type=int,
        default=10,
        help="Grace period before force kill by Docker (default: 10).",
    )

    kill_cmd = sub.add_parser(
        "kill",
        help="Force kill managed container resources.",
        description=(
            "Kill commands operate only on managed containers.\n"
            "Use `spr kill container <id>` for immediate termination."
        ),
        epilog=(
            "Examples:\n"
            "  python -m spr kill container abc123"
        ),
        formatter_class=_HELP_FORMATTER,
    )
    kill_cmd_sub = kill_cmd.add_subparsers(
        dest="resource",
        required=True,
        parser_class=_RichArgumentParser,
    )
    kill_container = kill_cmd_sub.add_parser(
        "container",
        help="Force kill one managed container by id.",
        description="Force kill a managed container immediately.",
        formatter_class=_HELP_FORMATTER,
    )
    kill_container.add_argument("container_id")

    sub.add_parser(
        "cleanup",
        help="Remove stale managed resources.",
        description=(
            "Remove stale managed resources.\n"
            "Deletes exited managed containers and removable managed images."
        ),
        epilog=(
            "Example:\n"
            "  python -m spr cleanup"
        ),
        formatter_class=_HELP_FORMATTER,
    )

    return parser


def build_engine(args: argparse.Namespace) -> DockerEngine:
    """Create a DockerEngine from global CLI connection flags.

    Example:
        ```python
        engine = build_engine(args)
        ```
    """
    return DockerEngine(
        docker_context=args.docker_context,
        docker_host=args.docker_host,
        ssh_host=args.ssh_host,
        ssh_user=args.ssh_user,
        ssh_port=args.ssh_port,
        ssh_key_path=args.ssh_key_path,
    )


def _print_containers(rows: list[dict[str, Any]]) -> None:
    """Render managed containers in a rich table.

    Example:
        ```python
        _print_containers([{"id": "abc", "name": "safe-py-runner-1"}])
        ```
    """
    table = Table(title="Managed Containers")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="magenta")
    table.add_column("Image")
    table.add_column("State")
    table.add_column("Status")
    for row in rows:
        table.add_row(row["id"], row["name"], row["image"], row["state"], row["status"])
    _CONSOLE.print(table)


def _print_images(rows: list[dict[str, Any]]) -> None:
    """Render managed images in a rich table.

    Example:
        ```python
        _print_images([{"id": "sha", "repository": "safe", "tag": "v1", "created_since": "1m", "size": "100MB"}])
        ```
    """
    table = Table(title="Managed Images")
    table.add_column("ID", style="cyan")
    table.add_column("Repository", style="magenta")
    table.add_column("Tag")
    table.add_column("Created")
    table.add_column("Size")
    for row in rows:
        table.add_row(
            row["id"],
            row["repository"],
            row["tag"],
            row["created_since"],
            row["size"],
        )
    _CONSOLE.print(table)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the `spr` CLI command handler.

    Example:
        ```python
        code = main(["list", "containers"])
        ```
    """
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    engine = build_engine(args)

    if args.command == "list" and args.resource == "containers":
        rows = [_to_jsonable(c) for c in engine.list_containers(all_states=True)]
        _print_containers(rows)
        return 0
    if args.command == "list" and args.resource == "images":
        rows = [_to_jsonable(i) for i in engine.list_images()]
        _print_images(rows)
        return 0
    if args.command == "container":
        needle = args.container_id
        rows = [_to_jsonable(c) for c in engine.list_containers(all_states=True)]
        matches = [
            row
            for row in rows
            if isinstance(row, dict)
            and isinstance(row.get("id"), str)
            and isinstance(row.get("name"), str)
            and (row["id"].startswith(needle) or row["name"] == needle)
        ]
        if not matches:
            _CONSOLE.print(Panel.fit(f"No managed container matched '{needle}'", style="bold red"))
            return 1
        _CONSOLE.print(Panel.fit(Pretty(matches[0]), title="Container", border_style="cyan"))
        return 0
    if args.command == "stop" and args.resource == "container":
        engine.stop_container(args.container_id, timeout_seconds=args.timeout_seconds)
        _CONSOLE.print(Panel.fit(f"Stopped container {args.container_id}", style="bold green"))
        return 0
    if args.command == "stop" and args.resource == "all":
        rows = [_to_jsonable(c) for c in engine.list_containers(all_states=True)]
        running = [
            row
            for row in rows
            if isinstance(row, dict)
            and isinstance(row.get("id"), str)
            and row.get("state") == "running"
        ]
        if not running:
            _CONSOLE.print(Panel.fit("No running managed containers to stop.", style="bold yellow"))
            return 0
        for row in running:
            engine.stop_container(row["id"], timeout_seconds=args.timeout_seconds)
        _CONSOLE.print(
            Panel.fit(
                f"Stopped {len(running)} managed container(s) with timeout {args.timeout_seconds}s",
                style="bold green",
            )
        )
        return 0
    if args.command == "kill" and args.resource == "container":
        engine.kill_container(args.container_id)
        _CONSOLE.print(Panel.fit(f"Killed container {args.container_id}", style="bold yellow"))
        return 0
    if args.command == "cleanup":
        summary = _to_jsonable(engine.cleanup_stale())
        _CONSOLE.print(Panel.fit(Pretty(summary), title="Cleanup Summary", border_style="green"))
        return 0

    parser.error("Unhandled command")
    return 2
