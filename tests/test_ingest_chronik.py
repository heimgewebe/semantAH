import json
from pathlib import Path
from datetime import datetime, timezone

import pytest

from cli import ingest_chronik


def test_read_last_records_rejects_negative_limit(tmp_path: Path):
    source = tmp_path / "chronik.jsonl"
    source.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="limit must be non-negative"):
        ingest_chronik.read_last_records(source, -1)


def test_read_last_records_zero_limit_returns_empty(tmp_path: Path):
    source = tmp_path / "chronik.jsonl"
    records = [{"title": "t", "summary": "s", "url": "u"}]
    source.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

    assert ingest_chronik.read_last_records(source, 0) == []


def test_shrink_to_size_no_change_needed():
    items = [{"title": "test", "summary": "short", "url": "http://example.com"}]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "chronik",
        "items": items,
    }
    encoded = ingest_chronik._encode(payload)
    max_bytes = len(encoded) + 10

    result = ingest_chronik.shrink_to_size(payload, max_bytes)
    assert result["items"] == items
    assert len(ingest_chronik._encode(result)) <= max_bytes


def test_shrink_to_size_drops_items():
    # item size approx 60-70 bytes
    item = {"title": "t", "summary": "s", "url": "u"}
    items = [item for _ in range(5)]
    payload = {
        "generated_at": "2023-01-01T00:00:00+00:00",
        "source": "chronik",
        "items": items,
    }

    # Calculate size of 2 items
    payload_2 = payload.copy()
    payload_2["items"] = items[:2]
    size_2 = len(ingest_chronik._encode(payload_2))

    # Set max_bytes to allow only 2 items
    # Note: shrink_to_size drops oldest (from start of list).
    # If we want to keep 2 items, we expect it to keep the LAST 2 items.

    result = ingest_chronik.shrink_to_size(payload, size_2)
    assert len(result["items"]) == 2
    # Should be the last 2 items
    assert result["items"] == items[3:]
    assert len(ingest_chronik._encode(result)) <= size_2


def test_shrink_to_size_drops_all_items():
    item = {"title": "t", "summary": "s", "url": "u"}
    items = [item]
    payload = {
        "generated_at": "2023-01-01T00:00:00+00:00",
        "source": "chronik",
        "items": items,
    }

    # Calculate base size (empty items)
    payload_empty = payload.copy()
    payload_empty["items"] = []
    base_size = len(ingest_chronik._encode(payload_empty))

    # Max bytes = base_size. Should allow empty list.
    result = ingest_chronik.shrink_to_size(payload, base_size)
    assert result["items"] == []
    assert len(ingest_chronik._encode(result)) <= base_size


def test_shrink_to_size_raises_if_base_too_large():
    payload = {
        "generated_at": "2023-01-01T00:00:00+00:00",
        "source": "chronik",
        "items": [],
    }
    base_size = len(ingest_chronik._encode(payload))

    with pytest.raises(ValueError, match="Unable to satisfy max-bytes constraint"):
        ingest_chronik.shrink_to_size(payload, base_size - 1)


def test_shrink_to_size_unicode():
    # Emoji takes 4 bytes in UTF-8
    item = {"title": "😀", "summary": "🚀", "url": "u"}
    items = [item]
    payload = {
        "generated_at": "2023-01-01T00:00:00+00:00",
        "source": "chronik",
        "items": items,
    }

    full_size = len(ingest_chronik._encode(payload))

    # If we reduce limit by 1 byte, it should drop the item
    result = ingest_chronik.shrink_to_size(payload, full_size - 1)
    assert result["items"] == []
