import ast
from pathlib import Path


def _python_files() -> list[Path]:
    root = Path(__file__).resolve().parents[1] / "src" / "safe_py_runner"
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def test_all_functions_have_docstring_with_example() -> None:
    missing: list[str] = []
    missing_example: list[str] = []

    for file_path in _python_files():
        module = ast.parse(file_path.read_text(encoding="utf-8"))
        for node in ast.walk(module):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            name = node.name
            if name in {"<lambda>"}:
                continue
            doc = ast.get_docstring(node)
            location = f"{file_path}:{node.lineno}:{name}"
            if not doc:
                missing.append(location)
                continue
            if "Example:" not in doc:
                missing_example.append(location)

    assert not missing, "Missing function docstrings:\n" + "\n".join(missing)
    assert not missing_example, "Docstrings without Example section:\n" + "\n".join(
        missing_example
    )
