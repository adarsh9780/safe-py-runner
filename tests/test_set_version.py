import importlib.util
from pathlib import Path

import pytest


def _load_set_version_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "set_version.py"
    spec = importlib.util.spec_from_file_location("set_version", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load set_version module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_set_project_version_updates_only_project_section():
    module = _load_set_version_module()
    source = (
        '[project]\n'
        'name = "safe-py-runner"\n'
        'version = "0.1.1"\n'
        '\n'
        '[tool.some]\n'
        'version = "keep-me"\n'
    )

    updated = module.set_project_version(source, "0.1.2")

    assert 'version = "0.1.2"' in updated
    assert 'version = "keep-me"' in updated


def test_set_project_version_raises_when_project_version_missing():
    module = _load_set_version_module()
    source = (
        '[project]\n'
        'name = "safe-py-runner"\n'
        '\n'
        '[tool.some]\n'
        'version = "keep-me"\n'
    )

    with pytest.raises(ValueError, match=r"Could not find \[project\]\.version"):
        module.set_project_version(source, "0.1.2")
