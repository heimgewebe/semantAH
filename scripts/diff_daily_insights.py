"""
diff_daily_insights.py

Detects drift by comparing the current daily insights artifact against a baseline.
Output: artifacts/observatory.diff.json (or similar diff artifact)
"""

import argparse
import json
import sys
from pathlib import Path

# Shared validation logic
try:
    import observatory_lib
except ImportError:
    # If not running as a module, try adding current directory to path
    import sys

    sys.path.append(str(Path(__file__).parent))
    import observatory_lib


def parse_args():
    parser = argparse.ArgumentParser(description="Generate daily insights drift report.")
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=Path("artifacts/insights.daily.json"),
        help="Path to the current snapshot file.",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("tests/fixtures/insights.daily.baseline.json"),
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
        default=Path("contracts/insights.daily.schema.json"),
        help="Path to the schema file for validation.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail with exit code 1 if baseline is missing or invalid (Guard mode).",
    )
    return parser.parse_args()


def generate_diff(snapshot: dict, baseline: dict | None, baseline_status: dict) -> dict:
    diff = {
        "baseline_missing": baseline_status.get("missing", False),
        "baseline_error": baseline_status.get("error", False),
        "baseline_generated_at": None,
        "current_generated_at": None,
        "topic_count_diff": None,
        "topics_changed": None,
        "new_topics": [],
        "removed_topics": [],
        "reason": baseline_status.get("reason"),
    }

    def get_generated_at(data):
        if not data:
            return None
        # Metadata (insights.daily)
        if "metadata" in data and "generated_at" in data["metadata"]:
            return data["metadata"]["generated_at"]
        return None

    diff["current_generated_at"] = get_generated_at(snapshot)
    if baseline:
        diff["baseline_generated_at"] = get_generated_at(baseline)

    if baseline:

        def get_topics(data):
            topics = data.get("topics", [])
            if not topics:
                return set()
            # Handle list of lists (insights.daily: [name, score])
            # Strict mode: assumes insights.daily structure
            return {t[0] for t in topics}

        b_topics = get_topics(baseline)
        c_topics = get_topics(snapshot)

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
            f"Error: Snapshot file not found at {args.snapshot}. Run export_daily_insights.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        snapshot_text = args.snapshot.read_text(encoding="utf-8")
        snapshot = json.loads(snapshot_text)
    except Exception as e:
        print(f"Error: Failed to read snapshot file: {e}", file=sys.stderr)
        sys.exit(1)

    observatory_lib.validate_payload(snapshot, args.schema, label="Current Snapshot")

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
            observatory_lib.validate_payload(baseline, args.schema, label="Baseline")

            # Check for empty topics
            if not baseline.get("topics"):
                raise ValueError("Baseline has zero topics")

        except Exception as e:
            baseline = None
            baseline_status["error"] = True
            baseline_status["reason"] = f"Failed to read/parse/validate baseline: {e}"
            print(f"Warning: {baseline_status['reason']}", file=sys.stderr)

    # Check for strict mode failure conditions
    if args.strict:
        if baseline_status["missing"] or baseline_status["error"]:
            print(
                f"Error: Strict mode enabled. Failing due to invalid/missing baseline. Reason: {baseline_status['reason']}",
                file=sys.stderr,
            )
            sys.exit(1)

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
