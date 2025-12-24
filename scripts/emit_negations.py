#!/usr/bin/env python3
"""
emit_negations.py

Reads a stream/list of insights (JSONL), detects conflicts (Thesis vs Antithesis),
and emits insight.negation events.

Usage:
    python scripts/emit_negations.py < input.jsonl > output.jsonl
"""

import hashlib
import json
import sys
from collections import defaultdict
from typing import Dict, List, Any

def get_stable_id(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

def emit_negations(insights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Group by (repo, file)
    groups = defaultdict(list)
    for i in insights:
        # Only process review.insight for now
        if i.get("type") != "review.insight":
            continue
        key = (i.get("repo"), i.get("file"))
        groups[key].append(i)

    negations = []

    for (repo, file_path), group in groups.items():
        # Simple heuristic:
        # Find pairs with high confidence (score >= 80) but conflicting buckets.
        # e.g. One is 'fail', one is 'info'/'pass' (if pass existed, but bucket is info/warn/fail).
        # Let's assume conflict is fail vs (info or warn).

        # Sort by id to ensure deterministic pairing
        group.sort(key=lambda x: x.get("id", ""))

        for idx, a in enumerate(group):
            for b in group[idx+1:]:
                score_a = a.get("score", 0)
                score_b = b.get("score", 0)

                if score_a < 80 or score_b < 80:
                    continue

                bucket_a = a.get("bucket")
                bucket_b = b.get("bucket")

                # Check for conflict
                # Conflict definition: distinct buckets, and at least one is 'fail'.
                # Or just distinct buckets? User said "Bucket-Konflikt (fail vs info)".
                if bucket_a == bucket_b:
                    continue

                is_conflict = ("fail" in [bucket_a, bucket_b])

                if is_conflict:
                    # Generate Negation
                    thesis_id = a.get("id")
                    antithesis_id = b.get("id")

                    if not thesis_id or not antithesis_id:
                        continue

                    # Stable ID for the negation itself
                    # hash(thesis_id + "::" + antithesis_id + "::neg")
                    raw_id_str = f"{thesis_id}::{antithesis_id}::neg"
                    neg_id = get_stable_id(raw_id_str)

                    negation = {
                        "type": "insight.negation",
                        "id": neg_id,
                        "repo": repo,
                        "file": file_path,
                        "source": "semantAH",
                        "score": min(score_a, score_b),
                        "verdict": f"Conflict detected between {bucket_a} and {bucket_b}",
                        "ingested_at": a.get("ingested_at"), # Inherit timestamp or now? User didn't specify. Inheriting from A is safe.
                        "bucket": "warn", # Negation itself is a warning?
                        "relation": {
                            "thesis": thesis_id,
                            "antithesis": antithesis_id
                        }
                    }
                    negations.append(negation)

    return negations

def main():
    inputs = []
    # Read from stdin or file
    if len(sys.argv) > 1:
        fpath = sys.argv[1]
        with open(fpath, "r") as f:
            for line in f:
                if line.strip():
                    inputs.append(json.loads(line))
    else:
        # Read from stdin
        if not sys.stdin.isatty():
            for line in sys.stdin:
                if line.strip():
                    inputs.append(json.loads(line))

    outputs = emit_negations(inputs)

    for item in outputs:
        print(json.dumps(item))

if __name__ == "__main__":
    main()
