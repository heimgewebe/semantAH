"""
observatory_lib.py

Shared utilities for observatory scripts.
"""

import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("Error: jsonschema is missing. Install it via 'uv sync'.", file=sys.stderr)
    sys.exit(1)


def validate_payload(payload: dict, schema_path: Path, label: str = "Payload"):
    """
    Validates a payload against the knowledge observatory schema.
    """
    if not schema_path.exists():
        print(f"Error: Schema file not found at {schema_path}", file=sys.stderr)
        sys.exit(1)

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(
            schema, format_checker=jsonschema.FormatChecker()
        )
        validator.validate(payload)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse schema JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except jsonschema.ValidationError as e:
        print(f"Error: {label} failed schema validation: {e.message}", file=sys.stderr)
        sys.exit(1)
