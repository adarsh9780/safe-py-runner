#!/usr/bin/env python3
"""Generate .github/release/metadata.json from a markdown file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_markdown(markdown_text: str) -> tuple[str, str]:
    lines = markdown_text.splitlines()

    title_idx = -1
    for i, line in enumerate(lines):
        if line.strip():
            title_idx = i
            break

    if title_idx == -1:
        raise ValueError("Input markdown is empty.")

    title_line = lines[title_idx].strip()
    if title_line.startswith("#"):
        title = title_line.lstrip("#").strip()
    else:
        title = title_line

    if not title:
        raise ValueError("Release title is empty.")

    description_lines = lines[title_idx + 1 :]
    while description_lines and not description_lines[0].strip():
        description_lines.pop(0)

    description = "\n".join(description_lines).strip()
    if not description:
        raise ValueError("Release description is empty. Add content after the title.")

    return title, description


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate release metadata JSON from markdown."
    )
    parser.add_argument(
        "--input",
        default="release_metadata.md",
        help="Path to input markdown file (default: release_metadata.md)",
    )
    parser.add_argument(
        "--output",
        default=".github/release/metadata.json",
        help="Path to output JSON file (default: .github/release/metadata.json)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    title, description = parse_markdown(input_path.read_text(encoding="utf-8"))

    payload = {
        "title": title,
        "description": description,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {output_path} from {input_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
