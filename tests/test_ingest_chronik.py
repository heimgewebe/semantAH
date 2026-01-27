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


def test_read_last_records_standard(tmp_path: Path):
    """Verify it returns the last N valid JSON objects in chronological order."""
    source = tmp_path / "chronik.jsonl"
    # Create 10 records
    records = [{"id": i} for i in range(10)]
    source.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")

    # Read last 3
    result = ingest_chronik.read_last_records(source, 3)
    assert len(result) == 3
    assert result == records[-3:]
    assert result[0]["id"] == 7
    assert result[2]["id"] == 9


def test_read_last_records_trailing_newlines(tmp_path: Path):
    """Verify trailing blank lines at the end of the file are ignored."""
    source = tmp_path / "chronik.jsonl"
    records = [{"id": i} for i in range(5)]
    content = "\n".join(json.dumps(r) for r in records)
    # Add multiple newlines at end
    content += "\n\n\n"
    source.write_text(content, encoding="utf-8")

    result = ingest_chronik.read_last_records(source, 2)
    assert len(result) == 2
    assert result == records[-2:]


def test_read_last_records_interleaved_newlines(tmp_path: Path):
    """Verify empty lines between records are ignored."""
    source = tmp_path / "chronik.jsonl"
    records = [{"id": i} for i in range(5)]
    # Interleave with empty lines
    lines = []
    for r in records:
        lines.append(json.dumps(r))
        lines.append("")  # Empty line
    content = "\n".join(lines)
    source.write_text(content, encoding="utf-8")

    result = ingest_chronik.read_last_records(source, 5)
    assert len(result) == 5
    assert result == records


def test_read_last_records_large_record_chunk_boundary(tmp_path: Path):
    """Verify correct behavior when a record exceeds or crosses chunk size."""
    source = tmp_path / "chronik.jsonl"

    # 16KB chunk size is used in implementation.
    # Create a large record ~20KB
    large_data = "a" * 20000
    large_record = {"id": 99, "data": large_data}

    records = [{"id": i} for i in range(5)]
    records.append(large_record)
    records.append({"id": 100})

    source.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")

    # Read last 2 records (should include large_record and id=100)
    result = ingest_chronik.read_last_records(source, 2)

    assert len(result) == 2
    assert result[0]["id"] == 99
    assert result[1]["id"] == 100
    assert result[0]["data"] == large_data


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
    items = [dict(item) for _ in range(5)]
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


def test_shrink_to_size_maximality():
    # Construct items of varying sizes
    items = [
        {"id": 1, "data": "a" * 10},
        {"id": 2, "data": "b" * 20},
        {"id": 3, "data": "c" * 30},
        {"id": 4, "data": "d" * 40},
    ]
    payload = {
        "generated_at": "2023-01-01T00:00:00+00:00",
        "source": "chronik",
        "items": items,
    }

    # Calculate sizes for suffixes
    # items[3:] -> id 4
    # items[2:] -> id 3, 4
    # items[1:] -> id 2, 3, 4

    # Let's target a size that fits item 4 and 3, but not 2.
    # We will verify that we get [3, 4] and not just [4].

    # Construct target payload with [3, 4]
    p_34 = payload.copy()
    p_34["items"] = items[2:]
    size_34 = len(ingest_chronik._encode(p_34))

    # Construct target payload with [2, 3, 4]
    p_234 = payload.copy()
    p_234["items"] = items[1:]
    size_234 = len(ingest_chronik._encode(p_234))

    # Set limit to exact size of [3, 4]
    # This should return [3, 4]
    res1 = ingest_chronik.shrink_to_size(payload.copy(), size_34)
    assert res1["items"] == items[2:]

    # Set limit to size of [3, 4] + 1 byte
    # This should still return [3, 4] because [2, 3, 4] is much larger
    res2 = ingest_chronik.shrink_to_size(payload.copy(), size_34 + 1)
    assert res2["items"] == items[2:]

    # Set limit to size of [2, 3, 4] - 1 byte
    # This should return [3, 4] (fails to fit 2)
    res3 = ingest_chronik.shrink_to_size(payload.copy(), size_234 - 1)
    assert res3["items"] == items[2:]


def test_shrink_to_size_restores_on_exception():
    items = [{"title": "t", "summary": "s", "url": "u"}]
    payload = {
        "generated_at": "2023-01-01T00:00:00+00:00",
        "source": "chronik",
        "items": items,
    }

    # Force base size violation
    # Calculate base size
    payload_empty = payload.copy()
    payload_empty["items"] = []
    base_size = len(ingest_chronik._encode(payload_empty))

    with pytest.raises(ValueError, match="Unable to satisfy max-bytes constraint"):
        ingest_chronik.shrink_to_size(payload, base_size - 1)

    # Verify items are restored
    assert payload["items"] == items
