#!/usr/bin/env python3
"""Read release metadata JSON and write GitHub Action step outputs safely."""

from __future__ import annotations

import argparse
import json
import os
import uuid
from pathlib import Path


def build_release_text(metadata_path: Path, tag: str) -> tuple[str, str]:
    data = json.loads(metadata_path.read_text(encoding="utf-8"))

    title = data["title"].replace("{{tag}}", tag)
    description = data["description"].replace("{{tag}}", tag)
    return title, description


def _make_delimiter(body: str) -> str:
    delimiter = f"GITHUB_OUTPUT_{uuid.uuid4().hex}"
    while delimiter in body:
        delimiter = f"GITHUB_OUTPUT_{uuid.uuid4().hex}"
    return delimiter


def write_outputs(output_path: Path, title: str, body: str) -> None:
    delimiter = _make_delimiter(body)
    with output_path.open("a", encoding="utf-8") as out:
        out.write(f"title={title}\n")
        out.write(f"body<<{delimiter}\n")
        out.write(body)
        out.write(f"\n{delimiter}\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read release metadata JSON and write workflow outputs."
    )
    parser.add_argument(
        "--metadata-file",
        default=".github/release/metadata.json",
        help="Path to release metadata json file",
    )
    parser.add_argument(
        "--tag",
        default=os.environ.get("GITHUB_REF_NAME", ""),
        help="Release tag name (defaults to GITHUB_REF_NAME env var)",
    )
    parser.add_argument(
        "--output-file",
        default=os.environ.get("GITHUB_OUTPUT", ""),
        help="Path to GitHub output file (defaults to GITHUB_OUTPUT env var)",
    )
    args = parser.parse_args()

    if not args.tag:
        raise ValueError("Tag is required. Pass --tag or set GITHUB_REF_NAME.")
    if not args.output_file:
        raise ValueError(
            "Output file is required. Pass --output-file or set GITHUB_OUTPUT."
        )

    title, description = build_release_text(Path(args.metadata_file), args.tag)
    write_outputs(Path(args.output_file), title, description)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
