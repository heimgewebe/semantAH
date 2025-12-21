"""
observatory_diff.py

Detects drift by comparing the current daily insights artifact against a baseline.
Output: artifacts/observatory.diff.json
"""

import json
import sys
from pathlib import Path

# Dependencies
try:
    import jsonschema
except ImportError:
    print("Error: jsonschema is missing. Install it via 'uv sync'.", file=sys.stderr)
    sys.exit(1)

# Canonical paths
ARTIFACTS_DIR = Path("artifacts")
SNAPSHOT_FILE = ARTIFACTS_DIR / "insights.daily.json"
BASELINE_FILE = Path("tests/fixtures/observatory.baseline.json")
DIFF_FILE = ARTIFACTS_DIR / "observatory.diff.json"
SCHEMA_FILE = Path("contracts/knowledge.observatory.schema.json")


def validate_payload(payload: dict, label: str = "Payload"):
    """
    Validates a payload against the knowledge observatory schema.
    """
    if not SCHEMA_FILE.exists():
        print(f"Error: Schema file not found at {SCHEMA_FILE}", file=sys.stderr)
        sys.exit(1)

    try:
        schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(
            schema, format_checker=jsonschema.FormatChecker()
        )
        validator.validate(payload)
        # print(f"{label} schema validation passed.") # Reduce noise in diff script
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse schema JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except jsonschema.ValidationError as e:
        print(f"Error: {label} failed schema validation: {e.message}", file=sys.stderr)
        sys.exit(1)


def generate_diff(current: dict):
    if not BASELINE_FILE.exists():
        print(f"No baseline data found ({BASELINE_FILE}). Skipping diff.")
        # We might want to output an empty diff or a specific 'no baseline' status
        # ensuring the artifact exists if downstream expects it.
        # For now, mirroring original behavior: just print and return.
        # But if the file is expected, we might want to touch it.
        # The original code just returned.
        return

    try:
        baseline_text = BASELINE_FILE.read_text(encoding="utf-8")
        baseline = json.loads(baseline_text)
    except Exception as e:
        print(f"Failed to read baseline data: {e}. Skipping diff.")
        return

    # Validate baseline as well to ensure valid contract comparison
    validate_payload(baseline, label="Baseline")

    # Enforce non-empty baseline for meaningful drift detection
    if not baseline.get("topics"):
        print(
            "Error: Baseline fixture has zero topics. Refusing drift comparison against empty baseline.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Simple metric comparison
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

    DIFF_FILE.write_text(
        json.dumps(diff, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Drift report generated at: {DIFF_FILE}")


def main() -> None:
    if not SNAPSHOT_FILE.exists():
        print(f"Error: Snapshot file not found at {SNAPSHOT_FILE}. Run observatory_mvp.py first.", file=sys.stderr)
        sys.exit(1)

    try:
        snapshot_text = SNAPSHOT_FILE.read_text(encoding="utf-8")
        snapshot = json.loads(snapshot_text)
    except Exception as e:
        print(f"Error: Failed to read snapshot file: {e}", file=sys.stderr)
        sys.exit(1)

    validate_payload(snapshot, label="Current Snapshot")
    generate_diff(snapshot)


if __name__ == "__main__":
    main()
