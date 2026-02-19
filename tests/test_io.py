from safe_py_runner import RunnerPolicy, run_code


def test_simple_io():
    """Verify simple input and output works."""
    code = "result = x + y"
    input_data = {"x": 10, "y": 20}
    result = run_code(code, input_data=input_data)

    assert result.ok
    assert result.result == 30


def test_dict_io():
    """Verify dictionary input and output."""
    code = """
result = {
    "sum": data["a"] + data["b"],
    "diff": data["a"] - data["b"]
}
"""
    input_data = {"data": {"a": 15, "b": 5}}
    result = run_code(code, input_data=input_data)

    assert result.ok
    assert result.result == {"sum": 20, "diff": 10}


def test_stdout_capture():
    """Verify print output is captured."""
    code = """
print("Hello")
print("World")
"""
    result = run_code(code)
    assert result.ok
    assert "Hello\nWorld" in result.stdout


def test_syntax_error():
    """Verify syntax errors in user code are captured correctly."""
    code = "def incomplete_function("
    result = run_code(code)

    assert not result.ok
    assert "SyntaxError" in (result.error or "")


def test_runtime_error():
    """Verify runtime exceptions are captured."""
    code = "x = 1 / 0"
    result = run_code(code)

    assert not result.ok
    assert "ZeroDivisionError" in (result.error or "")


def test_json_types_roundtrip():
    """Verify various JSON types (bool, null, float, list)."""
    code = """
result = {
    "is_valid": True,
    "none_val": None,
    "pi": 3.14159,
    "list_val": [1, 2, 3]
}
"""
    result = run_code(code)
    assert result.ok
    res = result.result
    assert res["is_valid"] is True
    assert res["none_val"] is None
    assert abs(res["pi"] - 3.14159) < 0.00001
    assert res["list_val"] == [1, 2, 3]


def test_reserved_keys_protection():
    """
    Verify that reserved input keys don't overwrite internal variables.
    reserved = {"__builtins__", "input_data", "result", "_print_", ...}
    """
    # Attempt to overwrite 'result' via input injection
    # worker.py protects 'result' from being overwritten by input_data key injection
    input_data = {"result": "malicious"}
    code = "pass"  # Do nothing, result should remain None
    result = run_code(code, input_data=input_data)

    assert result.ok
    assert result.result is None  # Should NOT be "malicious"

    # But user code CAN write to result, that's the point
    code = "result = 'valid'"
    result = run_code(code, input_data=input_data)
    assert result.result == "valid"
