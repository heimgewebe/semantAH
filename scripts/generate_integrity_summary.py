"""
Generate Integrity Summary for semantAH

Compares claims (schemas) vs. artifacts (files) to detect gaps.
Output: reports/integrity/summary.json and event_payload.json.

Integrity Artifacts:
- reports/integrity/summary.json: The full human-readable/machine-parsable report with counts and details.
- reports/integrity/event_payload.json: The canonical strict payload artifact for the event. Contains NO counts.
- reports/integrity/event.json: The derived transport envelope (convenience) ready for ingestion.
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone


def main():
    repo_root = Path.cwd()
    contracts_dir = repo_root / "contracts"
    artifacts_dir = repo_root / "artifacts"

    if not contracts_dir.is_dir():
        raise SystemExit("contracts/ missing: integrity loop cannot evaluate claims")

    # Canonical path: reports/integrity
    # INTEGRITY_OUT_DIR is an override only.
    integrity_out_dir = os.getenv("INTEGRITY_OUT_DIR", "reports/integrity")
    output_dir = repo_root / integrity_out_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Claims (Schemas)
    schemas = list(contracts_dir.glob("*.schema.json"))
    claims_list = sorted([s.name for s in schemas])

    # 2. Artifacts (Output)
    if artifacts_dir.exists():
        artifacts = list(artifacts_dir.glob("*.json"))
        artifacts_list = sorted([a.name for a in artifacts])
    else:
        artifacts_list = []

    # 3. Gaps (Claims without Artifacts)
    loop_gaps_list = []
    for schema in schemas:
        schema_name = schema.name
        base_name = schema_name[: -len(".schema.json")]
        expected_artifact = artifacts_dir / f"{base_name}.json"
        if not expected_artifact.exists():
            loop_gaps_list.append(base_name)

    loop_gaps_list.sort()
    unclear_list = []

    # Status: OK | WARN | UNCLEAR
    if len(loop_gaps_list) > 0:
        status = "WARN"
    elif len(unclear_list) > 0:
        status = "UNCLEAR"
    else:
        status = "OK"

    # Timestamp
    source_date_epoch = os.getenv("SOURCE_DATE_EPOCH")
    if source_date_epoch:
        generated_at = (
            datetime.fromtimestamp(int(source_date_epoch), tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
    else:
        generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Summary (Canonical Artifact)
    summary = {
        "repo": "heimgewebe/semantAH",
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

    summary_path = output_dir / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Generated Integrity Summary at {summary_path}")

    # Event Payload (Strict Schema: url, generated_at, repo, status)
    report_url = os.getenv(
        "INTEGRITY_REPORT_URL",
        "https://github.com/heimgewebe/semantAH/releases/download/knowledge-observatory/summary.json",
    )

    event_payload = {
        "url": report_url,
        "generated_at": summary["generated_at"],
        "repo": "heimgewebe/semantAH",
        "status": status,
    }

    event_payload_path = output_dir / "event_payload.json"
    with open(event_payload_path, "w") as f:
        json.dump(event_payload, f, indent=2)

    print(f"Generated Event Payload at {event_payload_path}")

    # Full Event Envelope (Optional convenience)
    event_envelope = {
        "type": "integrity.summary.published.v1",
        "source": os.getenv("GITHUB_REPOSITORY", "heimgewebe/semantAH"),
        "payload": event_payload,
    }

    event_path = output_dir / "event.json"
    with open(event_path, "w") as f:
        json.dump(event_envelope, f, indent=2)

    print(f"Generated Event Envelope at {event_path}")


if __name__ == "__main__":
    main()
