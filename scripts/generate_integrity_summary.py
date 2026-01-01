"""
Generate Integrity Summary for semantAH

This script diagnoses the integrity loop by comparing:
- Claims: Schema files in contracts/ (*.schema.json) that define expected artifacts
- Artifacts: Generated JSON files in artifacts/ representing produced outputs
- Loop Gaps: Schemas without corresponding artifacts (integrity gaps)
- Unclear: Items that need manual review

Output:
- reports/integrity/summary.json: Full integrity report
- reports/integrity/event_payload.json: Event payload for Chronik/Plexer

The summary is uploaded as a CI artifact and published as a release asset,
then sent to Plexer as an integrity.summary.published.v1 event.

Environment Variables:
- INTEGRITY_OUT_DIR: Output directory (default: reports/integrity)
- SOURCE_DATE_EPOCH: Unix timestamp for deterministic output (for tests/CI)
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone


def main():
    repo_root = Path.cwd()
    contracts_dir = repo_root / "contracts"
    artifacts_dir = repo_root / "artifacts"

    # Validate directory structure
    if not contracts_dir.is_dir():
        raise SystemExit("contracts/ missing: integrity loop cannot evaluate claims")

    # Ensure artifacts directory exists (artifact detection scans this)
    if not artifacts_dir.exists():
        # It's okay if artifacts dir doesn't exist yet (first run), but we can't find artifacts
        pass

    # Configurable output directory
    integrity_out_dir = os.getenv("INTEGRITY_OUT_DIR", "reports/integrity")
    output_dir = repo_root / integrity_out_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Claims (Schemas)
    # Filter for top-level schema files that represent artifacts
    schemas = list(contracts_dir.glob("*.schema.json"))
    claims_list = sorted([s.name for s in schemas])

    # 2. Artifacts (Output)
    # Intentionally top-level only; do not recurse into artifacts/* to avoid
    # counting integrity outputs.
    if artifacts_dir.exists():
        artifacts = list(artifacts_dir.glob("*.json"))
        artifacts_list = sorted([a.name for a in artifacts])
    else:
        artifacts_list = []

    # 3. Gaps
    # Simple heuristic: for each schema, is there a matching artifact?
    # e.g. foo.schema.json -> foo.json
    loop_gaps_list = []

    for schema in schemas:
        schema_name = schema.name
        base_name = schema_name[: -len(".schema.json")]  # remove .schema.json
        expected_artifact = artifacts_dir / f"{base_name}.json"

        if not expected_artifact.exists():
            loop_gaps_list.append(base_name)

    loop_gaps_list.sort()

    # 4. Unclear
    # Placeholder for future heuristics to detect items that need manual review.
    unclear_list = []

    # Determine Status
    # OK: No gaps, no unclear
    # WARN: Gaps exist
    # UNCLEAR: Unclear items exist (and no gaps)
    # FAIL: Not used by this script
    # MISSING: Not used by this script (Leitstand uses this if summary is missing)
    if len(loop_gaps_list) > 0:
        status = "WARN"
    elif len(unclear_list) > 0:
        status = "UNCLEAR"
    else:
        status = "OK"

    # Determine timestamp (deterministic if SOURCE_DATE_EPOCH is set)
    source_date_epoch = os.getenv("SOURCE_DATE_EPOCH")
    if source_date_epoch:
        generated_at = (
            datetime.fromtimestamp(int(source_date_epoch), tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
    else:
        generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Prepare Summary
    summary = {
        "repo": "semantAH",
        "generated_at": generated_at,
        "status": status,
        "counts": {
            "claims": len(claims_list),
            "artifacts": len(artifacts_list),
            "loop_gaps": len(loop_gaps_list),
            "unclear": len(unclear_list),
        },
        "details": {
            "claims": claims_list,
            "artifacts": artifacts_list,
            "loop_gaps": loop_gaps_list,
            "unclear": unclear_list,
        },
    }

    # Write Report to output directory
    summary_path = output_dir / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Generated Integrity Summary at {summary_path}")

    # Generate Event Payload (compliant with integrity.summary.published.v1)
    event_payload = {
        "repo": "semantAH",
        "generated_at": summary["generated_at"],
        "status": status,
        "counts": summary["counts"],
    }

    # Write event payload to output directory
    event_payload_path = output_dir / "event_payload.json"
    with open(event_payload_path, "w") as f:
        json.dump(event_payload, f, indent=2)

    print(f"Generated Event Payload at {event_payload_path}")


if __name__ == "__main__":
    main()
