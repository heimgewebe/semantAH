#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from observatory_lib import (
    validate_payload_if_available as validate_json,
)  # keeps local validation semantics


ARTIFACTS_DIR = Path("artifacts")
OUT_PATH = ARTIFACTS_DIR / "knowledge.observatory.json"
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


def collect_embedding_stats():
    """
    Collect embedding statistics from available sources.
    Returns dict with namespace counts and model info.
    
    NOTE: This is MVP-level - only counts total embeddings.
    Namespace-level tracking requires parsing the actual store format.
    """
    stats = {
        "namespaces": None,  # Not yet implemented - would need store format parser
        "model_revision": None,
        "total_count": 0,
    }

    # Check for embedding data in .gewebe or artifacts
    # For now, only count total lines - namespace extraction needs store format definition

    # Check if indexd store exists
    indexd_store = Path(".gewebe/indexd/store.jsonl")
    if indexd_store.exists():
        try:
            with open(indexd_store, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        stats["total_count"] += 1
                        # TODO: Parse namespace from actual data once store format is stable
        except (FileNotFoundError, IOError):
            # Store file disappeared or is unreadable - not critical for MVP
            pass
        except Exception as e:
            # Unexpected error - log for debugging but don't fail
            print(f"Warning: Failed to read indexd store: {e}", file=sys.stderr)

    return stats


def main() -> int:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    # version: prefer env injected by CI; otherwise fall back to a safe dev marker
    version = os.getenv("SEMANTAH_VERSION") or os.getenv("GITHUB_SHA") or "0.0.0-dev"

    # Collect embedding statistics
    embedding_stats = collect_embedding_stats()
    
    # Build topics list with embedding-aware content
    topics = [
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
    ]

    # Add embedding infrastructure topic only if we have actual data
    if embedding_stats["total_count"] > 0:
        topics.append(
            {
                "topic": "Semantic Infrastructure",
                "confidence": clamp01(0.85),
                "sources": [
                    {"type": "repo_file", "ref": "crates/indexd/", "weight": 0.7},
                    {
                        "type": "repo_file",
                        "ref": "contracts/os.context.text.embed.schema.json",
                        "weight": 0.3,
                    },
                ],
                "suggested_questions": [
                    "Are embeddings being generated?",
                    "Is the store format stable?",
                ],
            }
        )

    # Build signals list
    signals = [
        {
            "type": "trend",
            "description": "Contract-first enforcement is tightening; examples act as the nail.",
        }
    ]

    # Add embedding-related signals only if we have data
    if embedding_stats["total_count"] > 0:
        signals.append(
            {
                "type": "metadata",
                "description": f"Total embeddings in store: {embedding_stats['total_count']}",
            }
        )

    if embedding_stats["model_revision"]:
        signals.append(
            {
                "type": "metadata",
                "description": f"Active embedding model revision: {embedding_stats['model_revision']}",
            }
        )

    # Build blind spots list
    blind_spots = [
        "No real vault ingestion wired in this MVP.",
        "No external web signals ingested (by design).",
    ]

    if embedding_stats["total_count"] == 0:
        blind_spots.append("No embedding data available for analysis.")
    
    # Add namespace tracking as explicit blind spot
    if embedding_stats["namespaces"] is None:
        blind_spots.append("Namespace-level embedding tracking not yet implemented (requires stable store format).")

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
        "topics": topics,
        "signals": signals,
        "blind_spots": blind_spots,
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

    # Check for empty output
    if not OUT_PATH.is_file() or OUT_PATH.stat().st_size == 0:
        raise SystemExit(f"Missing or empty artifact: {OUT_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
