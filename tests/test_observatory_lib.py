"""
Tests for scripts/observatory_lib.py

Covers strict mode enforcement and optional validation behavior.
"""

from __future__ import annotations

import json
import sys

import pytest

# Import the module under test
# We need to import it at module level to access its functions
import scripts.observatory_lib as observatory_lib


@pytest.fixture
def mock_missing_jsonschema(monkeypatch):
    """
    Fixture to mock missing jsonschema import.
    
    Removes jsonschema from sys.modules to ensure the mocked ImportError
    is triggered reliably, regardless of whether jsonschema was previously imported.
    """
    import builtins
    
    # Remove jsonschema from sys.modules to ensure deterministic test behavior
    if "jsonschema" in sys.modules:
        monkeypatch.delitem(sys.modules, "jsonschema", raising=False)
    
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "jsonschema":
            raise ImportError("No module named 'jsonschema'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)


def test_load_jsonschema_when_available():
    """
    Test that _load_jsonschema returns jsonschema module when it's available.
    """
    # This test assumes jsonschema is installed in the test environment
    # If it's not, we skip the test
    try:
        import jsonschema  # noqa: F401
    except ImportError:
        pytest.skip("jsonschema not installed in test environment")

    result = observatory_lib._load_jsonschema()
    assert result is not None
    assert hasattr(result, "Draft202012Validator")


def test_load_jsonschema_missing_non_strict(
    monkeypatch, mock_missing_jsonschema, capsys
):
    """
    Test that _load_jsonschema returns None without emitting warnings
    when jsonschema is missing in non-strict mode.
    
    Note: Warnings are emitted by validate_payload_if_available, not by
    _load_jsonschema itself.
    """
    # Unset strict mode environment variables
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("STRICT_CONTRACTS", raising=False)

    result = observatory_lib._load_jsonschema()

    assert result is None
    # _load_jsonschema should not emit warnings in non-strict mode
    captured = capsys.readouterr()
    assert captured.err == ""


def test_load_jsonschema_missing_strict_via_ci(
    monkeypatch, mock_missing_jsonschema, capsys
):
    """
    Test that _load_jsonschema exits with code 1 when jsonschema is missing
    and CI=true is set (strict mode).
    """
    monkeypatch.setenv("CI", "true")
    monkeypatch.delenv("STRICT_CONTRACTS", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        observatory_lib._load_jsonschema()

    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "Error: jsonschema is required in strict mode" in captured.err


def test_load_jsonschema_missing_strict_via_strict_contracts(
    monkeypatch, mock_missing_jsonschema, capsys
):
    """
    Test that _load_jsonschema exits with code 1 when jsonschema is missing
    and STRICT_CONTRACTS=1 is set (strict mode).
    """
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("STRICT_CONTRACTS", "1")

    with pytest.raises(SystemExit) as exc_info:
        observatory_lib._load_jsonschema()

    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "Error: jsonschema is required in strict mode" in captured.err


def test_validate_payload_if_available_with_missing_jsonschema(
    tmp_path, monkeypatch, capsys
):
    """
    Test that validate_payload_if_available prints contextual warning
    when jsonschema is missing in non-strict mode.
    """
    # Unset strict mode
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("STRICT_CONTRACTS", raising=False)

    # Mock _load_jsonschema to return None
    monkeypatch.setattr(observatory_lib, "_load_jsonschema", lambda: None)

    # Create a dummy schema file
    schema_path = tmp_path / "test_schema.json"
    schema_path.write_text(json.dumps({"type": "object"}))

    # Call validate_payload_if_available
    payload = {"test": "data"}
    observatory_lib.validate_payload_if_available(
        payload, schema_path, label="Test Payload"
    )

    captured = capsys.readouterr()
    assert "Warning: jsonschema missing; skipping schema validation for Test Payload." in captured.err


def test_validate_payload_if_available_schema_not_found(tmp_path, capsys):
    """
    Test that validate_payload_if_available exits when schema file is not found.
    """
    schema_path = tmp_path / "nonexistent_schema.json"
    payload = {"test": "data"}

    with pytest.raises(SystemExit) as exc_info:
        observatory_lib.validate_payload_if_available(payload, schema_path)

    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "Error: Schema file not found" in captured.err


def test_validate_payload_if_available_invalid_schema_json(tmp_path, capsys):
    """
    Test that validate_payload_if_available exits when schema is invalid JSON.
    """
    # This test requires jsonschema to be available
    try:
        import jsonschema  # noqa: F401
    except ImportError:
        pytest.skip("jsonschema not installed in test environment")

    schema_path = tmp_path / "invalid_schema.json"
    schema_path.write_text("{ invalid json }")

    payload = {"test": "data"}

    with pytest.raises(SystemExit) as exc_info:
        observatory_lib.validate_payload_if_available(payload, schema_path)

    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "Error: Failed to parse schema JSON" in captured.err


def test_validate_payload_if_available_validation_fails(tmp_path, capsys):
    """
    Test that validate_payload_if_available exits when payload fails validation.
    """
    # This test requires jsonschema to be available
    try:
        import jsonschema  # noqa: F401
    except ImportError:
        pytest.skip("jsonschema not installed in test environment")

    # Create a schema that requires a "name" field
    schema_path = tmp_path / "schema.json"
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    schema_path.write_text(json.dumps(schema))

    # Payload missing required field
    payload = {"test": "data"}

    with pytest.raises(SystemExit) as exc_info:
        observatory_lib.validate_payload_if_available(
            payload, schema_path, label="Test Payload"
        )

    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "Error: Test Payload failed schema validation" in captured.err


def test_validate_payload_if_available_validation_succeeds(tmp_path, capsys):
    """
    Test that validate_payload_if_available succeeds with valid payload.
    """
    # This test requires jsonschema to be available
    try:
        import jsonschema  # noqa: F401
    except ImportError:
        pytest.skip("jsonschema not installed in test environment")

    # Create a simple schema
    schema_path = tmp_path / "schema.json"
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    schema_path.write_text(json.dumps(schema))

    # Valid payload
    payload = {"name": "test"}

    # Should not raise
    observatory_lib.validate_payload_if_available(
        payload, schema_path, label="Test Payload"
    )

    captured = capsys.readouterr()
    # No error or warning expected
    assert captured.err == ""


def test_backwards_compatible_alias():
    """
    Test that validate_payload is an alias for validate_payload_if_available.
    """
    assert observatory_lib.validate_payload is observatory_lib.validate_payload_if_available
