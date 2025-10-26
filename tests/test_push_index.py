import pandas as pd
import pytest

from scripts.push_index import (
    to_batches,
    _derive_doc_id,
    _derive_chunk_id,
    _is_missing,
)


def test_namespace_fallback_and_grouping():
    df = pd.DataFrame(
        [
            {"doc_id": "d1", "namespace": "vault", "id": "c1", "text": "hello", "embedding": [0.1, 0.2]},
            {"doc_id": "d1", "namespace": float("nan"), "id": "c2", "text": "world", "embedding": [0.3, 0.4]},
            {"doc_id": "d2", "namespace": "   ", "id": "c3", "text": "!", "embedding": [0.5, 0.6]},
        ]
    )
    batches = list(to_batches(df, default_namespace="defaultNS"))

    keys = {(b["namespace"], b["doc_id"]): len(b["chunks"]) for b in batches}
    assert keys == {
        ("vault", "d1"): 1,
        ("defaultNS", "d1"): 1,
        ("defaultNS", "d2"): 1,
    }


def test_doc_id_derivation_order_and_missing():
    assert _derive_doc_id({"doc_id": "  abc  "}) == "abc"
    assert _derive_doc_id({"path": " /notes/n1.md "}) == "/notes/n1.md"
    assert _derive_doc_id({"id": "xyz"}) == "xyz"
    with pytest.raises(ValueError):
        _derive_doc_id({"doc_id": None, "path": "  ", "id": float("nan")})


def test_chunk_id_hash_fallback_is_stable_and_collision_resistant():
    record = {"text": "Same text here", "embedding": [1.0, 0.0]}
    cid1 = _derive_chunk_id(record, doc_id="D")
    cid2 = _derive_chunk_id(record, doc_id="D")
    assert cid1 == cid2
    assert cid1.startswith("D#t")

    record2 = {"__row": 42, "embedding": [1.0, 0.0]}
    cid3 = _derive_chunk_id(record2, doc_id="D")
    assert cid3 == "D#r42"

    record3 = {"embedding": [1.0, 0.0]}
    cid4 = _derive_chunk_id(record3, doc_id="D")
    assert cid4 == "D#chunk"


def test_is_missing_covers_nan_none_and_whitespace():
    assert _is_missing(None) is True
    assert _is_missing(float("nan")) is True
    assert _is_missing("   ") is True
    assert _is_missing("") is True
    assert _is_missing("x") is False


def test_to_batches_end_to_end_no_nan_ids_and_namespace_default():
    df = pd.DataFrame(
        [
            {"doc_id": "D1", "text": "alpha", "embedding": [0.1, 0.2]},
            {"doc_id": "D2", "namespace": float("nan"), "__row": 7, "embedding": [0.3, 0.4]},
            {"doc_id": "D3", "namespace": "   ", "embedding": [0.5, 0.6]},
        ]
    )
    default_ns = "vault-default"
    batches = list(to_batches(df, default_namespace=default_ns))

    for batch in batches:
        assert batch["namespace"] == default_ns
        for chunk in batch["chunks"]:
            chunk_id = str(chunk["id"]).lower()
            assert chunk_id != "nan"
            assert "nan" not in chunk_id
            assert chunk_id.strip() != ""
