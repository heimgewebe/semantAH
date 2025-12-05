#!/usr/bin/env python3
"""
Exportiert Tages-Insights für den Vault.

Ziel:
  - $VAULT_ROOT/.gewebe/insights/daily/YYYY-MM-DD.json
  - $VAULT_ROOT/.gewebe/insights/today.json (Alias auf denselben Inhalt)

Format:
  Entspricht grob `contracts/insights.daily.schema.json` im metarepo:

  {
    "ts": "YYYY-MM-DD",
    "topics": [["topic", 0.42], ...],
    "questions": [],
    "deltas": []
  }

Die Implementierung ist bewusst leichtgewichtig:
  - keine LLMs,
  - keine Abhängigkeiten außer der Standardbibliothek,
  - Fokus auf „brauchbare Stubs mit echter Struktur“, damit
    Leitstand/hausKI/chronik darauf aufbauen können.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, List, Tuple


VAULT_ENV_VAR = "VAULT_ROOT"
MAX_TOPICS = 16
WEIGHT_PRECISION = 3


@dataclass
class DailyInsights:
    """Repräsentiert die Tages-Insights gemäß insights.daily.schema.json."""

    ts: str
    topics: List[Tuple[str, float]]
    questions: List[str]
    deltas: List[dict]

    def to_json(self) -> dict:
        return {
            "ts": self.ts,
            "topics": [[name, weight] for name, weight in self.topics],
            "questions": list(self.questions),
            "deltas": list(self.deltas),
        }


def _get_vault_root() -> Path:
    env = os.environ.get(VAULT_ENV_VAR)
    if not env:
        print(
            f"{VAULT_ENV_VAR} ist nicht gesetzt. "
            "Bitte Pfad zum Vault setzen (z. B. export VAULT_ROOT=/pfad/zur/obsidian-vault).",
            file=sys.stderr,
        )
        raise SystemExit(1)

    root = Path(env).expanduser()
    if not root.exists():
        print(
            f"{VAULT_ENV_VAR} verweist auf einen nicht existierenden Pfad: {root}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if not root.is_dir():
        print(
            f"{VAULT_ENV_VAR} muss auf ein Verzeichnis zeigen, nicht auf eine Datei: {root}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    return root


def _iter_markdown_files(root: Path) -> Iterable[Path]:
    """
    Liefert alle Markdown-Dateien unterhalb von root.

    Schließt versteckte Verzeichnisse (beginnend mit '.') wie .gewebe aus.
    """
    for path in root.rglob("*.md"):
        rel = path.relative_to(root)
        # Schließe Dateien aus, die in versteckten Verzeichnissen liegen
        if any(part.startswith(".") for part in rel.parts):
            continue
        yield path


def _derive_topics(root: Path, files: Iterable[Path]) -> List[Tuple[str, float]]:
    """
    Leitet grobe Themen aus Top-Level-Ordnern ab.

    Beispiel:
      VAULT_ROOT/
        schule/note1.md   -> topic "schule"
        projekte/x.md      -> topic "projekte"
        note_im_root.md    -> topic "(root)"
    """
    counter: Counter[str] = Counter()
    for path in files:
        try:
            rel = path.relative_to(root)
        except ValueError:
            # Sollte eigentlich nicht vorkommen, aber wir sind robust.
            continue

        parts = rel.parts
        topic = parts[0] if len(parts) > 1 else "(root)"
        counter[topic] += 1

    if not counter:
        # Fallback – Schema trotzdem bedienen
        return [("vault", 1.0)]

    total = sum(counter.values())
    items = counter.most_common(MAX_TOPICS)

    # Normiere auf 0..1, auf drei Nachkommastellen gerundet.
    return [(name, round(count / total, WEIGHT_PRECISION)) for name, count in items]


def _build_payload(vault_root: Path) -> DailyInsights:
    """
    Baut das Tages-Insights-Payload für den gegebenen Vault.

    Args:
        vault_root (Path): Wurzelverzeichnis des Vaults.

    Returns:
        DailyInsights: Das generierte Insights-Objekt für den aktuellen Tag.
    """
    today = date.today().isoformat()
    files = _iter_markdown_files(vault_root)
    topics = _derive_topics(vault_root, files)

    # Platzhalter: noch keine automatischen Fragen oder Deltas.
    # Diese können später z. B. aus hausKI- oder chronik-Daten gespeist werden.
    return DailyInsights(
        ts=today,
        topics=topics,
        questions=[],
        deltas=[],
    )


def main() -> int:
    vault_root = _get_vault_root()
    insights = _build_payload(vault_root).to_json()

    insights_root = vault_root / ".gewebe" / "insights"
    daily_dir = insights_root / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)

    daily_path = daily_dir / f"{insights['ts']}.json"
    today_path = insights_root / "today.json"

    for target in (daily_path, today_path):
        with target.open("w", encoding="utf-8") as fh:
            json.dump(insights, fh, ensure_ascii=False, indent=2, sort_keys=True)

    print(
        f"[export_insights] geschrieben: {daily_path} und {today_path}", file=sys.stderr
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
