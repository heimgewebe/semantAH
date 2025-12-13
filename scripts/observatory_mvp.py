"""
observatory_mvp.py

Minimaler Producer für Capability C1 "Semantisches Observatorium".
Absichtlich ohne Embeddings/Clustering/Heuristik: nur Existenz + Contract-Konformität.

Output: data/observatory/observatory-<timestamp>.json
Contract: knowledge.observatory.schema.json (kanonisch im heimgewebe/metarepo)
"""

from __future__ import annotations

import datetime as _dt
import json
import uuid
from pathlib import Path


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
        sources.append({"source_type": "repo_file", "ref": ".", "tags": ["mvp", "fallback"]})

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
    }


def main() -> None:
    output_dir = Path("data/observatory")
    output_dir.mkdir(parents=True, exist_ok=True)

    now = _utc_now()
    ts_str = now.strftime("%Y%m%d-%H%M%S")

    payload = build_payload(now)

    output_file = output_dir / f"observatory-{ts_str}.json"
    output_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Observatory report generated at: {output_file}")


if __name__ == "__main__":
    main()
