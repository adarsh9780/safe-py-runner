from pathlib import Path


def test_readme_links_bubblewrap_comparison_doc() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    comparison_doc = root / "docs" / "BUBBLEWRAP_COMPARISON.md"
    comparison_text = comparison_doc.read_text(encoding="utf-8")

    assert "## Bubblewrap Comparison" in readme
    assert "[docs/BUBBLEWRAP_COMPARISON.md](docs/BUBBLEWRAP_COMPARISON.md)" in readme
    assert comparison_doc.exists()
    assert "| Capability | `safe-py-runner` | `bubblewrap` (`bwrap`) |" in comparison_text


def test_readme_has_explicit_honest_scope_statement() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")

    assert "Honest scope:" in readme
    assert "Good fit:" in readme
    assert "Not good alone:" in readme


def test_readme_common_gotchas_are_current() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")

    assert "### Common Gotchas" in readme
    assert "`importlib` is blocked intentionally in all modes." in readme
    assert "`engine` is required." in readme
    assert "only accepts pinned specs." in readme
    assert "DockerEngine does not silently fall back to local execution." in readme


def test_pypi_readme_includes_gotchas_section() -> None:
    root = Path(__file__).resolve().parents[1]
    pypi_readme = (root / "docs" / "README_PYPI.md").read_text(encoding="utf-8")

    assert "## Common Gotchas" in pypi_readme
    assert "`engine` is required for `run_code(...)`" in pypi_readme
    assert "`importlib` is intentionally blocked in all modes." in pypi_readme
