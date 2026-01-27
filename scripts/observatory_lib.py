"""
observatory_lib.py

Shared utilities for observatory scripts.
"""

import json
import os
import sys
from pathlib import Path


def _load_jsonschema():
    try:
        import jsonschema  # type: ignore
    except ImportError:
        if os.getenv("CI") == "true" or os.getenv("STRICT_CONTRACTS") == "1":
            print(
                "Error: jsonschema is required in strict mode. Install it to validate contracts.",
                file=sys.stderr,
            )
            sys.exit(1)
        return None

    return jsonschema


_SCHEMA_CACHE = {}


def validate_payload_if_available(
    payload: dict, schema_path: Path, label: str = "Payload"
):
    """
    Validate a payload against the knowledge observatory schema when jsonschema is
    available.
    """
    if not schema_path.exists():
        print(f"Error: Schema file not found at {schema_path}", file=sys.stderr)
        sys.exit(1)

    jsonschema = _load_jsonschema()
    if jsonschema is None:
        print(
            f"Warning: jsonschema missing; skipping schema validation for {label}.",
            file=sys.stderr,
        )
        return

    path_key = str(schema_path.resolve())
    validator = _SCHEMA_CACHE.get(path_key)

    if validator is None:
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            validator = jsonschema.Draft202012Validator(
                schema, format_checker=jsonschema.FormatChecker()
            )
            _SCHEMA_CACHE[path_key] = validator
        except json.JSONDecodeError as e:
            print(f"Error: Failed to parse schema JSON: {e}", file=sys.stderr)
            sys.exit(1)

    try:
        validator.validate(payload)
    except jsonschema.ValidationError as e:
        print(f"Error: {label} failed schema validation: {e.message}", file=sys.stderr)
        sys.exit(1)


# Backwards-compatible alias for existing scripts
validate_payload = validate_payload_if_available
