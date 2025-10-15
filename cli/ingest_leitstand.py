#!/usr/bin/env python3
"""Read Leitstand export and produce today's insights."""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

MAX_BYTES_DEFAULT = 10 * 1024
DEFAULT_LIMIT = 32


@dataclass
class Insight:
    tags: List[str]
    title: str
    summary: str
    url: str

    @classmethod
    def from_record(cls, record: dict) -> "Insight | None":
        title = _coerce_str(record.get("title"))
        summary = _coerce_str(record.get("summary"))
        url = _coerce_str(record.get("url"))
        if not (title and summary and url):
            return None

        tags = _coerce_tags(record.get("tags"))
        return cls(tags=tags, title=title, summary=summary, url=url)

    def to_dict(self) -> dict:
        return {
            "tags": self.tags,
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
        }


def _coerce_str(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return str(value)


def _coerce_tags(value) -> List[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, Iterable) or isinstance(value, (bytes, bytearray)):
        return []
    tags = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            tags.append(text)
    return tags


def read_last_records(path: Path, limit: int) -> list[dict]:
    lines = deque(maxlen=limit)
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            lines.append(line)
    records: list[dict] = []
    for line in lines:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Cannot parse line as JSON: {line[:80]}...") from exc
    return records


def shrink_to_size(payload: dict, max_bytes: int) -> dict:
    """Drop oldest items until serialized payload fits into max_bytes."""
    items = payload.get("items", [])
    if not isinstance(items, list):
        return payload

    encoded = _encode(payload)
    while len(encoded) > max_bytes and items:
        items.pop(0)
        encoded = _encode(payload)
    if len(encoded) > max_bytes:
        raise ValueError(
            "Unable to satisfy max-bytes constraint even after dropping all items"
        )
    return payload


def _encode(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def build_payload(insights: list[Insight]) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "leitstand",
        "items": [insight.to_dict() for insight in insights],
    }


def ingest(args: argparse.Namespace) -> Path:
    source_path = Path(args.source).expanduser().resolve()
    output_path = Path(args.output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not source_path.is_file():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    raw_records = read_last_records(source_path, args.limit)
    insights = []
    for record in raw_records:
        insight = Insight.from_record(record)
        if insight is not None:
            insights.append(insight)

    payload = build_payload(insights)
    shrink_to_size(payload, args.max_bytes)

    data_bytes = _encode(payload)
    output_path.write_bytes(data_bytes)
    return output_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read Leitstand JSONL export and store the latest insights in "
            "vault/.gewebe/insights/today.json"
        )
    )
    parser.add_argument(
        "source",
        help="Path to leitstand/data/aussen.jsonl",
    )
    parser.add_argument(
        "--output",
        default="vault/.gewebe/insights/today.json",
        help="Target JSON file (default: vault/.gewebe/insights/today.json)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Number of trailing records to read (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=MAX_BYTES_DEFAULT,
        help="Maximum JSON payload size in bytes (default: 10240)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        output_path = ingest(args)
    except Exception as exc:  # pragma: no cover - small CLI
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
