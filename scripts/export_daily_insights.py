#!/usr/bin/env python3
"""
Exportiert Tages-Insights (Canonical Artifact).

Ziel:
  - artifacts/insights.daily.json (kanonisch)

Format:
  Strikt konform zu `contracts/insights.daily.schema.json`.

  {
    "ts": "YYYY-MM-DD",
    "topics": [["topic", 0.42], ...],
    "questions": [],
    "deltas": [],
    "source": "semantAH",
    "metadata": {
      "generated_at": "YYYY-MM-DDTHH:MM:SSZ",
      "observatory_ref": "obs-...",  # Optional: Reference to observatory
      "uncertainty": 0.2              # Optional: Aggregated uncertainty (0.0-1.0)
    }
  }

Verhalten:
  - Validiert Output gegen das Schema.
  - Priorisiert `knowledge.observatory.json` als Quelle für Topics und Metadaten.
  - Fallback auf Vault-Scan, wenn kein Observatory vorhanden.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, List, Tuple, Optional

from observatory_lib import validate_payload_if_available


SCHEMA_PATH = Path("contracts") / "insights.daily.schema.json"
MAX_TOPICS = 16
WEIGHT_PRECISION = 3


@dataclass
class DailyInsights:
    """Repräsentiert die Tages-Insights gemäß insights.daily.schema.json."""

    ts: str
    topics: List[Tuple[str, float]]
    questions: List[str]
    deltas: List[str]
    source: str
    metadata: dict

    def to_json(self) -> dict:
        return {
            "ts": self.ts,
            "topics": [[name, weight] for name, weight in self.topics],
            "questions": self.questions,
            "deltas": self.deltas,
            "source": self.source,
            "metadata": self.metadata,
        }


def iso_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _iter_markdown_files(root: Path) -> Iterable[Path]:
    """
    Liefert alle Markdown-Dateien unterhalb von root.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune hidden directories in-place
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]

        for filename in filenames:
            if filename.endswith(".md") and not filename.startswith("."):
                yield Path(dirpath) / filename


def _derive_topics_from_vault(
    root: Path, files: Iterable[Path]
) -> List[Tuple[str, float]]:
    """
    Leitet grobe Themen aus Top-Level-Ordnern ab.
    """
    counter: Counter[str] = Counter()
    has_files = False
    for path in files:
        has_files = True
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue

        parts = rel.parts
        topic = parts[0] if len(parts) > 1 else "(root)"
        counter[topic] += 1

    if not has_files:
        return [("vault", 1.0)]

    items = counter.most_common(MAX_TOPICS)
    total_selected = sum(count for _, count in items)

    if total_selected == 0:
        return [("vault", 1.0)]

    return [
        (name, round(count / total_selected, WEIGHT_PRECISION)) for name, count in items
    ]


def _derive_topics_from_observatory(obs_data: dict) -> List[Tuple[str, float]]:
    """
    Extrahiert Topics aus dem Observatory-Payload.
    """
    raw_topics = obs_data.get("topics", [])
    if not raw_topics:
        return [("observatory-empty", 1.0)]

    # Map [topic, confidence] -> [topic, score]
    # We take top N by confidence
    sorted_topics = sorted(
        raw_topics, key=lambda x: x.get("confidence", 0.0), reverse=True
    )
    selected = sorted_topics[:MAX_TOPICS]

    return [
        (t["topic"], round(t.get("confidence", 0.0), WEIGHT_PRECISION))
        for t in selected
        if "topic" in t
    ]


def _build_payload(
    vault_root: Optional[Path], observatory_path: Optional[Path]
) -> DailyInsights:
    """
    Baut das Tages-Insights-Payload.
    """
    today = date.today().isoformat()
    metadata = {"generated_at": iso_now()}
    topics = []

    # Priority: Observatory -> Vault -> Stub
    observatory_used = False
    if observatory_path and observatory_path.exists():
        try:
            obs_data = json.loads(observatory_path.read_text(encoding="utf-8"))
            topics = _derive_topics_from_observatory(obs_data)

            # Enrich metadata
            if "observatory_id" in obs_data:
                metadata["observatory_ref"] = obs_data["observatory_id"]

            # Calculate aggregated uncertainty (1.0 - avg_confidence)
            raw_topics = obs_data.get("topics", [])
            if raw_topics:
                avg_conf = sum(t.get("confidence", 0.0) for t in raw_topics) / len(
                    raw_topics
                )
                metadata["uncertainty"] = round(1.0 - avg_conf, 2)
            else:
                metadata["uncertainty"] = 1.0  # Max uncertainty if no topics

            observatory_used = True
            print(f"::notice:: Derived insights from Observatory: {observatory_path}")
        except Exception as e:
            print(f"::warning:: Failed to read observatory data: {e}", file=sys.stderr)

    if not observatory_used:
        if vault_root and vault_root.is_dir():
            files = _iter_markdown_files(vault_root)
            topics = _derive_topics_from_vault(vault_root, files)
            print(f"::notice:: Derived insights from Vault: {vault_root}")
        else:
            topics = [("vault", 1.0)]
            print("::notice:: Using stub insights (no vault, no observatory)")

    return DailyInsights(
        ts=today,
        topics=topics,
        questions=[],
        deltas=[],
        source="semantAH",
        metadata=metadata,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Export daily insights artifact.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/insights.daily.json"),
        help="Path to the output JSON file.",
    )
    parser.add_argument(
        "--vault-root",
        type=Path,
        default=os.environ.get("VAULT_ROOT"),
        help="Path to the vault root (optional).",
    )
    parser.add_argument(
        "--observatory",
        type=Path,
        default=None,
        help="Path to knowledge.observatory.json input (optional).",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=None,
        help="Path to the JSON schema (overrides env var METAREPO_SCHEMA_INSIGHTS_DAILY and default).",
    )
    args = parser.parse_args()

    # Resolve schema path: Arg > Env > Default Local Mirror
    schema_path = (
        args.schema
        or os.environ.get("METAREPO_SCHEMA_INSIGHTS_DAILY")
        or Path("contracts/insights.daily.schema.json")
    )
    schema_path = Path(schema_path)

    insights = _build_payload(args.vault_root, args.observatory).to_json()

    # Validate
    validate_payload_if_available(insights, schema_path, label="Daily Insights")

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("w", encoding="utf-8") as fh:
        json.dump(insights, fh, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"Exported valid insights to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
