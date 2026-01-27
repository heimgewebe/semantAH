"""
observatory_lib.py

Shared utilities for observatory scripts.
"""

import functools
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


@functools.lru_cache(maxsize=32)
def _get_cached_validator(path_str: str, mtime: int, size: int):
    """
    Load and parse a JSON schema, returning a validator.
    Cached based on path and file metadata (mtime, size) to ensure freshness.
    """
    jsonschema = _load_jsonschema()
    # Note: caller ensures jsonschema is available before calling this.

    schema = json.loads(Path(path_str).read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    )


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

    try:
        # Get file stats to serve as cache key invalidation
        # st_mtime_ns and st_size are robust enough for our needs
        stat = schema_path.stat()
        validator = _get_cached_validator(
            str(schema_path.resolve()), stat.st_mtime_ns, stat.st_size
        )
        validator.validate(payload)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse schema JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except jsonschema.ValidationError as e:
        print(f"Error: {label} failed schema validation: {e.message}", file=sys.stderr)
        sys.exit(1)


# Backwards-compatible alias for existing scripts
validate_payload = validate_payload_if_available
