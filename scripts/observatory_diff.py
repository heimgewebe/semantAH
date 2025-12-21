"""
observatory_diff.py

Detects drift by comparing the current daily insights artifact against a baseline.
Output: artifacts/observatory.diff.json
"""

import argparse
import json
import sys
from pathlib import Path

# Dependencies
try:
    import jsonschema
except ImportError:
    print("Error: jsonschema is missing. Install it via 'uv sync'.", file=sys.stderr)
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description="Generate observatory drift report.")
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=Path("artifacts/insights.daily.json"),
        help="Path to the current snapshot file.",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("tests/fixtures/observatory.baseline.json"),
        help="Path to the baseline file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/observatory.diff.json"),
        help="Path to the output diff file.",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("contracts/knowledge.observatory.schema.json"),
        help="Path to the schema file for validation.",
    )
    return parser.parse_args()


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


def generate_diff(snapshot: dict, baseline: dict | None, baseline_status: dict) -> dict:
    diff = {
        "baseline_missing": baseline_status.get("missing", False),
        "baseline_error": baseline_status.get("error", False),
        "baseline_generated_at": baseline.get("generated_at") if baseline else None,
        "current_generated_at": snapshot.get("generated_at"),
        "topic_count_diff": None,
        "topics_changed": None,
        "new_topics": [],
        "removed_topics": [],
        "reason": baseline_status.get("reason"),
    }

    if baseline:
        b_topics = {t.get("topic_id") for t in baseline.get("topics", [])}
        c_topics = {t.get("topic_id") for t in snapshot.get("topics", [])}

        diff["topic_count_diff"] = len(c_topics) - len(b_topics)
        diff["topics_changed"] = b_topics != c_topics
        diff["new_topics"] = sorted(list(c_topics - b_topics))
        diff["removed_topics"] = sorted(list(b_topics - c_topics))
        diff["reason"] = None  # Clear reason if successful comparison

    return diff


def main() -> None:
    args = parse_args()

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    if not args.snapshot.exists():
        print(
            f"Error: Snapshot file not found at {args.snapshot}. Run observatory_mvp.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        snapshot_text = args.snapshot.read_text(encoding="utf-8")
        snapshot = json.loads(snapshot_text)
    except Exception as e:
        print(f"Error: Failed to read snapshot file: {e}", file=sys.stderr)
        sys.exit(1)

    validate_payload(snapshot, args.schema, label="Current Snapshot")

    baseline = None
    baseline_status = {"missing": False, "error": False, "reason": None}

    if not args.baseline.exists():
        baseline_status["missing"] = True
        baseline_status["reason"] = f"Baseline file not found at {args.baseline}"
        print(f"Warning: {baseline_status['reason']}")
    else:
        try:
            baseline_text = args.baseline.read_text(encoding="utf-8")
            baseline = json.loads(baseline_text)

            # Validate baseline
            validate_payload(baseline, args.schema, label="Baseline")

            # Check for empty topics
            if not baseline.get("topics"):
                raise ValueError("Baseline has zero topics")

        except Exception as e:
            baseline = None
            baseline_status["error"] = True
            baseline_status["reason"] = f"Failed to read/parse/validate baseline: {e}"
            print(f"Warning: {baseline_status['reason']}", file=sys.stderr)

    diff = generate_diff(snapshot, baseline, baseline_status)

    try:
        args.output.write_text(
            json.dumps(diff, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"Drift report generated at: {args.output}")
    except Exception as e:
        print(f"Error: Failed to write diff file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
