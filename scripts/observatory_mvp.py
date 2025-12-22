#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from observatory_lib import (
    validate_payload as validate_json,
)  # keeps local validation semantics


ARTIFACTS_DIR = Path("artifacts")
OUT_PATH = ARTIFACTS_DIR / "insights.daily.json"
SCHEMA_PATH = Path("contracts") / "knowledge.observatory.schema.json"


def iso_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def main() -> int:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    # version: prefer env injected by CI; otherwise fall back to a safe dev marker
    version = os.getenv("SEMANTAH_VERSION") or os.getenv("GITHUB_SHA") or "0.0.0-dev"

    # Minimal, contract-konformes MVP:
    # - topics[]: topic + confidence required, sources/suggested_questions optional
    # - signals/blind_spots/considered_but_rejected are required top-level fields
    payload = {
        "observatory_id": f"obs-{uuid.uuid4()}",
        "generated_at": iso_now(),
        "source": {
            "component": "semantAH",
            "version": version,
        },
        "topics": [
            {
                "topic": "Epistemic Drift",
                "confidence": clamp01(0.80),
                "sources": [
                    {"type": "repo_file", "ref": "contracts/", "weight": 0.6},
                    {"type": "repo_file", "ref": "docs/", "weight": 0.4},
                ],
                "suggested_questions": [
                    "Which contracts changed since the last snapshot?",
                    "Is drift concentrated in one subsystem (semantics, CI, UI)?",
                ],
            },
            {
                "topic": "System Resilience",
                "confidence": clamp01(0.70),
                "sources": [],
                "suggested_questions": [
                    "Which single failure would break the artifact pipeline first?"
                ],
            },
        ],
        "signals": [
            {
                "type": "trend",
                "description": "Contract-first enforcement is tightening; examples act as the nail.",
            }
        ],
        "blind_spots": [
            "No real vault ingestion wired in this MVP.",
            "No external web signals ingested (by design).",
        ],
        "considered_but_rejected": [
            {
                "hypothesis": "Overfit schema too early",
                "reason": "Keep optional expansion points (sources, questions) while enforcing core fields.",
            }
        ],
    }

    # Validate locally before writing, so CI fails with a useful message.
    validate_json(payload, SCHEMA_PATH)

    OUT_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
