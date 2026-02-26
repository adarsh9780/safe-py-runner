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
