"""
observatory_mvp.py

Minimaler Producer für Capability C1 "Semantisches Observatorium".
Absichtlich ohne Embeddings/Clustering/Heuristik: nur Existenz + Contract-Konformität.

Output: artifacts/insights.daily.json
Contract: contracts/knowledge.observatory.schema.json
"""

from __future__ import annotations

import datetime as _dt
import json
import uuid
from pathlib import Path
import sys
import shutil

# Canonical output path
ARTIFACTS_DIR = Path("artifacts")
OUTPUT_FILE = ARTIFACTS_DIR / "insights.daily.json"
PREV_FILE = ARTIFACTS_DIR / "observatory.prev.json"
DIFF_FILE = ARTIFACTS_DIR / "observatory.diff.json"


def _utc_now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _iso(ts: _dt.datetime) -> str:
    # ISO 8601 with timezone
    return ts.isoformat()


def _pick_repo_sources() -> list[dict]:
    """
    Sehr dumm: wir picken ein paar typische Dateien, wenn sie existieren.
    Das erfüllt 'reale Repo-Quellen', ohne irgendwelche Semantik zu behaupten.
    """
    candidates = [
        "README.md",
        "pyproject.toml",
        "docs/roadmap.md",
        "docs/ist-stand-vs-roadmap.md",
        "docs/README.md",
    ]

    sources: list[dict] = []
    for rel in candidates:
        p = Path(rel)
        if p.exists() and p.is_file():
            sources.append(
                {
                    "source_type": "repo_file",
                    "ref": rel,
                    # optional fields per schema:
                    "tags": ["mvp"],
                }
            )

    # Fallback: wenn nichts existiert, wenigstens die Repo-Root als Referenz,
    # damit das Feld nicht leer ist (Schema erlaubt leer, aber das ist useless).
    if not sources:
        sources.append(
            {"source_type": "repo_file", "ref": ".", "tags": ["mvp", "fallback"]}
        )

    return sources


def build_payload(now: _dt.datetime) -> dict:
    obs_id = f"obs-{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    topic_id = f"topic-mvp-{now.strftime('%Y%m%d')}"

    return {
        "observatory_id": obs_id,
        "generated_at": _iso(now),
        "source": "semantAH",
        "topics": [
            {
                "topic_id": topic_id,
                "title": "MVP Observatory Snapshot",
                "summary": "Minimaler, schema-konformer Snapshot aus Repo-Dateien (ohne Semantik).",
                "sources": _pick_repo_sources(),
                "suggested_questions": [
                    "Welche Quellen sollen künftig priorisiert werden (Vault, Chronik, Repos)?",
                    "Welche minimale Heuristik wäre als nächstes erlaubt, ohne die Kette zu brechen?",
                ],
                "suggested_next_steps": [
                    "Leitstand: Fixture und Renderer auf den gleichen Contract ziehen.",
                    "Metarepo: optional Fixture-Validation erweitern (falls gewünscht).",
                ],
                "meta": {"mvp": True},
            }
        ],
        "considered_but_rejected": [],
        "low_confidence_patterns": [],
        "blind_spots": []
    }


def compare_with_prev(current: dict):
    if not PREV_FILE.exists():
        print("No previous observatory data found (artifacts/observatory.prev.json). Skipping diff.")
        return

    try:
        prev_text = PREV_FILE.read_text(encoding="utf-8")
        prev = json.loads(prev_text)
    except Exception as e:
        print(f"Failed to read previous observatory data: {e}. Skipping diff.")
        return

    # Simple metric comparison
    diff = {
        "generated_at_prev": prev.get("generated_at"),
        "generated_at_curr": current.get("generated_at"),
        "topic_count_diff": len(current.get("topics", [])) - len(prev.get("topics", [])),
        "topics_changed": False # Placeholder
    }

    # We can do a slightly deeper check
    prev_topics = {t.get("topic_id") for t in prev.get("topics", [])}
    curr_topics = {t.get("topic_id") for t in current.get("topics", [])}

    if prev_topics != curr_topics:
        diff["topics_changed"] = True
        diff["new_topics"] = list(curr_topics - prev_topics)
        diff["removed_topics"] = list(prev_topics - curr_topics)

    DIFF_FILE.write_text(
        json.dumps(diff, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Drift report generated at: {DIFF_FILE}")


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    now = _utc_now()
    payload = build_payload(now)

    OUTPUT_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"Observatory report generated at: {OUTPUT_FILE}")

    compare_with_prev(payload)

    # Update prev file for next run?
    # The user instruction says "Lege im Repo ein: artifacts/observatory.prev.json" and "Beim Lauf: Vergleiche...".
    # It does not explicitly say "Overwrite prev". But typically diffs are today vs yesterday.
    # If we don't update prev, we always compare against the static repo file.
    # Assuming for now we leave prev as is, unless the user manually updates it or CI handles it.
    # But usually a drift detection needs a moving window.
    # Given "Drift-Sichtbarkeit herstellen" and "Vergleich Heute vs. Gestern",
    # it implies we might want to rotate it. But let's stick to reading it for now.

    # Verify mandatory fields (redundant with schema but good for immediate feedback)
    missing = []
    for field in ["considered_but_rejected", "low_confidence_patterns", "blind_spots"]:
        if field not in payload:
            missing.append(field)

    if missing:
        print(f"ERROR: Missing mandatory fields: {missing}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
