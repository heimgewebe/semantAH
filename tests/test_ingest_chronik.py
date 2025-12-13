import json
from pathlib import Path

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
