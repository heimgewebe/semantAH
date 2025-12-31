import json
import glob
from pathlib import Path
from datetime import datetime, timezone

def main():
    repo_root = Path.cwd()
    contracts_dir = repo_root / "contracts"
    artifacts_dir = repo_root / "artifacts"
    reports_dir = repo_root / "reports/integrity"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # 1. Claims (Schemas)
    # Filter for top-level schema files that represent artifacts
    schemas = list(contracts_dir.glob("*.schema.json"))
    claims_list = [s.name for s in schemas]

    # 2. Artifacts (Output)
    # Check what is currently in artifacts/
    # We look for json files.
    artifacts = list(artifacts_dir.glob("*.json"))
    artifacts_list = [a.name for a in artifacts]

    # 3. Gaps
    # Simple heuristic: for each schema, is there a matching artifact?
    # e.g. foo.schema.json -> foo.json
    loop_gaps_list = []

    for schema in schemas:
        schema_name = schema.name
        if schema_name.endswith(".schema.json"):
            base_name = schema_name[:-len(".schema.json")] # remove .schema.json
            expected_artifact = artifacts_dir / f"{base_name}.json"

            if not expected_artifact.exists():
                loop_gaps_list.append(base_name)

    # 4. Unclear
    unclear_list = []

    # Prepare Summary
    summary = {
        "repo": "semantAH",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "counts": {
            "claims": len(claims_list),
            "artifacts": len(artifacts_list),
            "loop_gaps": len(loop_gaps_list),
            "unclear": len(unclear_list)
        },
        "details": {
            "claims": claims_list,
            "artifacts": artifacts_list,
            "loop_gaps": loop_gaps_list,
            "unclear": unclear_list
        }
    }

    # Write Report
    report_path = reports_dir / "summary.json"
    with open(report_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Generated Integrity Summary at {report_path}")

    # Generate partial Event Payload
    event_payload = {
        "repo": "semantAH",
        "generated_at": summary["generated_at"],
        "counts": summary["counts"]
    }

    # Write event payload to a file for easy consumption by the workflow
    with open("integrity_event_payload.json", "w") as f:
        json.dump(event_payload, f, indent=2)

if __name__ == "__main__":
    main()
