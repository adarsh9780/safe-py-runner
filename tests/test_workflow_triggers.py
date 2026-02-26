from pathlib import Path


def test_ci_workflow_triggers_on_master_and_main() -> None:
    root = Path(__file__).resolve().parents[1]
    ci = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert 'branches: [ "master", "main" ]' in ci
