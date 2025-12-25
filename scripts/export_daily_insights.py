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
      "generated_at": "YYYY-MM-DDTHH:MM:SSZ"
    }
  }

Verhalten:
  - Validiert Output gegen das Schema.
  - Wenn kein Vault gefunden wird, wird ein minimaler, gültiger Stub erzeugt.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, List, Tuple, Optional

try:
    import jsonschema
except ImportError:
    print("Error: jsonschema is missing. Install it via 'uv sync'.", file=sys.stderr)
    sys.exit(1)


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


def validate_payload(payload: dict, schema_path: Path):
    if not schema_path.exists():
        print(f"Error: Schema file not found at {schema_path}", file=sys.stderr)
        sys.exit(1)

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(
            schema, format_checker=jsonschema.FormatChecker()
        )
        validator.validate(payload)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse schema JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except jsonschema.ValidationError as e:
        print(f"Error: Payload failed schema validation: {e.message}", file=sys.stderr)
        sys.exit(1)


def _iter_markdown_files(root: Path) -> Iterable[Path]:
    """
    Liefert alle Markdown-Dateien unterhalb von root.
    """
    for path in root.rglob("*.md"):
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        yield path


def _derive_topics(root: Path, files: Iterable[Path]) -> List[Tuple[str, float]]:
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
        # Fallback – Schema trotzdem bedienen
        return [("vault", 1.0)]

    items = counter.most_common(MAX_TOPICS)
    total_selected = sum(count for _, count in items)

    if total_selected == 0:
        return [("vault", 1.0)]

    return [
        (name, round(count / total_selected, WEIGHT_PRECISION)) for name, count in items
    ]


def _build_payload(vault_root: Optional[Path]) -> DailyInsights:
    """
    Baut das Tages-Insights-Payload.
    """
    today = date.today().isoformat()

    if vault_root and vault_root.is_dir():
        files = _iter_markdown_files(vault_root)
        topics = _derive_topics(vault_root, files)
    else:
        topics = [("vault", 1.0)]

    return DailyInsights(
        ts=today,
        topics=topics,
        questions=[],
        deltas=[],
        source="semantAH",
        metadata={
            "generated_at": iso_now()
        }
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

    insights = _build_payload(args.vault_root).to_json()

    # Validate
    validate_payload(insights, schema_path)

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("w", encoding="utf-8") as fh:
        json.dump(insights, fh, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"Exported valid insights to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
