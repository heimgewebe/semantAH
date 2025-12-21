"""
observatory_diff.py

Generates a diff between two observatory JSON artifacts.
"""
import json
import sys
from pathlib import Path
import argparse

# Dependencies for validation
try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

def validate_payload(payload: dict, schema_path: Path, label: str = "Payload"):
    if not HAS_JSONSCHEMA:
        # If jsonschema is missing but we requested validation (schema_path provided),
        # we should probably warn.
        if schema_path:
            print("Warning: jsonschema missing, skipping validation.", file=sys.stderr)
        return

    if not schema_path.exists():
        print(f"Error: Schema file not found at {schema_path}", file=sys.stderr)
        sys.exit(1)

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(
            schema, format_checker=jsonschema.FormatChecker()
        )
        validator.validate(payload)
        print(f"{label} schema validation passed.")
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse schema JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except jsonschema.ValidationError as e:
        print(f"Error: {label} failed schema validation: {e.message}", file=sys.stderr)
        sys.exit(1)

def diff_observatory(
    current_path: Path,
    baseline_path: Path,
    output_path: Path,
    schema_path: Path = None,
    enforce_baseline_not_empty: bool = False
) -> None:

    # Read current first to report its timestamp even if baseline missing
    try:
        current_text = current_path.read_text(encoding="utf-8")
        current = json.loads(current_text)
        current_generated_at = current.get("generated_at")
    except Exception as e:
         print(f"Failed to read current data: {e}.", file=sys.stderr)
         sys.exit(1)

    if schema_path:
        validate_payload(current, schema_path, label="Current")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not baseline_path.exists():
        print(f"No baseline data found ({baseline_path}). Generating missing-baseline report.")
        diff = {
            "baseline_missing": True,
            "current_generated_at": current_generated_at,
            "reason": "No baseline/prev file found (first run or cache miss).",
            "topics_changed": None,
            "new_topics": [],
            "removed_topics": []
        }
        output_path.write_text(json.dumps(diff, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return

    try:
        baseline_text = baseline_path.read_text(encoding="utf-8")
        baseline = json.loads(baseline_text)
    except Exception as e:
        print(f"Failed to read baseline data: {e}. Generating error report.")
        diff = {
            "baseline_error": True,
            "current_generated_at": current_generated_at,
            "reason": f"Failed to read baseline data: {e}",
            "topics_changed": None,
            "new_topics": [],
            "removed_topics": []
        }
        output_path.write_text(json.dumps(diff, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return

    if schema_path:
        validate_payload(baseline, schema_path, label="Baseline")

    if enforce_baseline_not_empty and not baseline.get("topics"):
        print(
            "Error: Baseline fixture has zero topics. Refusing drift comparison against empty baseline.",
            file=sys.stderr,
        )
        sys.exit(1)

    baseline_topics = {t.get("topic_id") for t in baseline.get("topics", [])}
    curr_topics = {t.get("topic_id") for t in current.get("topics", [])}
    topics_changed = baseline_topics != curr_topics

    diff = {
        "baseline_generated_at": baseline.get("generated_at"),
        "current_generated_at": current.get("generated_at"),
        "topic_count_diff": len(current.get("topics", []))
        - len(baseline.get("topics", [])),
        "topics_changed": topics_changed,
        "new_topics": sorted(list(curr_topics - baseline_topics)),
        "removed_topics": sorted(list(baseline_topics - curr_topics)),
    }

    output_path.write_text(
        json.dumps(diff, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Drift report generated at: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Diff observatory artifacts.")
    parser.add_argument("current", type=Path, help="Path to current insights.daily.json")
    parser.add_argument("baseline", type=Path, help="Path to baseline/prev json")
    parser.add_argument("output", type=Path, help="Path to output diff json")
    parser.add_argument("--schema", type=Path, help="Path to schema for validation")
    parser.add_argument("--enforce-not-empty", action="store_true", help="Fail if baseline is empty")

    args = parser.parse_args()

    diff_observatory(
        args.current,
        args.baseline,
        args.output,
        schema_path=args.schema,
        enforce_baseline_not_empty=args.enforce_not_empty
    )

if __name__ == "__main__":
    main()
