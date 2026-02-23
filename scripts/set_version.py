#!/usr/bin/env python3
"""Update [project].version in pyproject.toml."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

VERSION_PATTERN = re.compile(r'^version\s*=\s*"([^"]+)"\s*$')


def set_project_version(pyproject_text: str, version: str) -> str:
    in_project = False
    changed = False
    output_lines: list[str] = []

    for line in pyproject_text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"

        if in_project and VERSION_PATTERN.match(stripped):
            newline = "\n" if line.endswith("\n") else ""
            output_lines.append(f'version = "{version}"{newline}')
            changed = True
            continue

        output_lines.append(line)

    if not changed:
        raise ValueError("Could not find [project].version in pyproject.toml")

    return "".join(output_lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Set pyproject.toml project version.")
    parser.add_argument("--version", required=True, help="New version, e.g. 0.1.2")
    parser.add_argument(
        "--pyproject",
        default="pyproject.toml",
        help="Path to pyproject.toml (default: pyproject.toml)",
    )
    args = parser.parse_args()

    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        raise ValueError("Version must match semantic format X.Y.Z")

    pyproject_path = Path(args.pyproject)
    updated = set_project_version(pyproject_path.read_text(encoding="utf-8"), args.version)
    pyproject_path.write_text(updated, encoding="utf-8")
    print(f"Updated {pyproject_path} to version {args.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
