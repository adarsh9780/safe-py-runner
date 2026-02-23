from pathlib import Path
import importlib.util


def _load_release_module():
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "read_release_metadata.py"
    )
    spec = importlib.util.spec_from_file_location("read_release_metadata", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load read_release_metadata module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_write_outputs_uses_multiline_format_without_plain_eof(tmp_path: Path):
    module = _load_release_module()
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        (
            "{\n"
            '  "title": "safe-py-runner {{tag}}",\n'
            '  "description": "Release notes for {{tag}}.\\n\\n'
            '- Added GitHub Actions CI trigger for pushes and PRs to `main`.\\n'
            '- Added markdown-driven release metadata generator."\n'
            "}\n"
        ),
        encoding="utf-8",
    )

    title, body = module.build_release_text(metadata_path, "v0.1.2")

    output_file = tmp_path / "github_output.txt"
    module.write_outputs(output_file, title, body)
    content = output_file.read_text(encoding="utf-8")

    assert "title=safe-py-runner v0.1.2\n" in content
    assert "body<<GITHUB_OUTPUT_" in content
    assert "- Added GitHub Actions CI trigger for pushes and PRs to `main`." in content
