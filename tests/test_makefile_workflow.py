from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_make_test_target_runs_lint_type_and_pytest() -> None:
    makefile = (_project_root() / "Makefile").read_text(encoding="utf-8")
    start = makefile.index("test:\n")
    end = makefile.index("\n\nlint:\n")
    block = makefile[start:end]

    assert "uv run --extra dev ruff check ." in block
    assert "uv run --extra dev mypy" in block
    assert "uv run --extra dev pytest" in block


def test_readme_push_docs_match_master_branch() -> None:
    readme = (_project_root() / "README.md").read_text(encoding="utf-8")

    assert "Push to `master`" in readme
    assert "Push to `main`" not in readme
    assert "passed on `master`" in readme


def test_check_version_target_prints_version_number() -> None:
    makefile = (_project_root() / "Makefile").read_text(encoding="utf-8")
    start = makefile.index("check-version:\n")
    end = makefile.index("\n\ncheck-version-different-from-pyproject:")
    block = makefile[start:end]

    assert 'echo "pyproject.toml version: $$pyproject_version (valid)"' in block
