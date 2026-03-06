
from unittest.mock import MagicMock
import urllib.error
from scripts.push_index import PooledUpsertClient
from itertools import permutations

import pandas as pd
import pytest

import scripts.push_index

from scripts.push_index import (
    _derive_chunk_id,
    _derive_doc_id,
    _is_missing,
    to_batches,
)


def test_namespace_fallback_and_grouping():
    df = pd.DataFrame(
        [
            {
                "doc_id": "d1",
                "namespace": "vault",
                "id": "c1",
                "text": "hello",
                "embedding": [0.1, 0.2],
            },
            {
                "doc_id": "d1",
                "namespace": float("nan"),
                "id": "c2",
                "text": "world",
                "embedding": [0.3, 0.4],
            },
            {
                "doc_id": "d2",
                "namespace": "   ",
                "id": "c3",
                "text": "!",
                "embedding": [0.5, 0.6],
            },
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


def test_chunk_id_fallback_stable_across_reordering():
    """Fallback per Text-Hash bleibt über beliebige Reihenfolgen stabil."""

    rows = [
        {"doc_id": "D", "text": "one", "embedding": [1.0, 0.0]},
        {"doc_id": "D", "text": "two", "embedding": [0.0, 1.0]},
        {"doc_id": "D", "text": "three", "embedding": [0.7, 0.7]},
    ]

    baseline = None
    for perm in permutations(rows):
        df = pd.DataFrame(list(perm))
        batches = list(to_batches(df, default_namespace="ns"))
        assert len(batches) == 1
        batch = batches[0]
        mapping = {c["text"]: c["id"] for c in batch["chunks"]}
        for cid in mapping.values():
            assert str(cid).startswith("D#")
            assert "nan" not in str(cid).lower()
        if baseline is None:
            baseline = mapping
        else:
            assert mapping == baseline


def test_chunk_id_global_ids_and_bool_skip():
    assert (
        _derive_chunk_id({"chunk_id": "G#abc", "embedding": [1, 0]}, doc_id="D")
        == "G#abc"
    )
    cid = _derive_chunk_id(
        {"chunk_id": True, "text": "X", "embedding": [1, 0]}, doc_id="D"
    )
    assert cid.startswith("D#t")


def test_is_missing_covers_nan_none_and_whitespace():
    assert _is_missing(None) is True
    assert _is_missing(float("nan")) is True
    assert _is_missing("   ") is True
    assert _is_missing("") is True
    assert _is_missing("x") is False


def test_is_missing_handles_pandas_and_numpy_na_types():
    np = pytest.importorskip("numpy")
    assert _is_missing(pd.NA) is True
    assert _is_missing(np.nan) is True


def test_normalise_meta_value_handles_stub_pandas(monkeypatch):
    """_normalise_meta_value sollte ohne echte pandas.Timestamp laufen."""

    class DummyPandas:
        pass

    monkeypatch.setattr(scripts.push_index, "pd", DummyPandas())

    value = "2024-01-01"
    # Should simply return the value without raising AttributeError
    assert scripts.push_index._normalise_meta_value(value) == value


def test_to_batches_end_to_end_no_nan_ids_and_namespace_default():
    df = pd.DataFrame(
        [
            {"doc_id": "D1", "text": "alpha", "embedding": [0.1, 0.2]},
            {
                "doc_id": "D2",
                "namespace": float("nan"),
                "__row": 7,
                "embedding": [0.3, 0.4],
            },
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





def test_pooled_client_invalid_endpoint():
    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        PooledUpsertClient("ftp://localhost/upsert")

    with pytest.raises(ValueError, match="Invalid or missing hostname"):
        PooledUpsertClient("http://")


def test_pooled_client_http_error(monkeypatch):
    client = PooledUpsertClient("http://localhost:8080/upsert")

    mock_conn = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status = 500
    mock_resp.reason = "Internal Server Error"
    mock_resp.read.return_value = b'{"error": "bad"}'
    mock_resp.headers.get.return_value = ""
    mock_conn.getresponse.return_value = mock_resp

    monkeypatch.setattr(client, "_get_conn", lambda: mock_conn)

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        client.post_upsert({"test": "data"})

    assert exc_info.value.code == 500
    assert exc_info.value.reason == "Internal Server Error"
    assert client.conn is None  # connection should be reset on 500


def test_pooled_client_url_error(monkeypatch):
    import http.client

    client = PooledUpsertClient("http://localhost:8080/upsert")

    mock_conn = MagicMock()
    mock_conn.request.side_effect = http.client.RemoteDisconnected("disconnected")

    monkeypatch.setattr(client, "_get_conn", lambda: mock_conn)

    with pytest.raises(urllib.error.URLError):
        client.post_upsert({"test": "data"})

    assert client.conn is None  # connection should be reset on network error


def test_pooled_client_connection_close_header(monkeypatch):
    client = PooledUpsertClient("http://localhost:8080/upsert")

    mock_conn = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b'{"status": "ok"}'

    def mock_header_get(key, default=""):
        if key.lower() == "connection":
            return "close"
        return default

    mock_resp.headers.get = mock_header_get

    mock_conn.getresponse.return_value = mock_resp

    # Pre-populate connection to test reset logic
    client.conn = mock_conn
    monkeypatch.setattr(client, "_get_conn", lambda: mock_conn)

    resp = client.post_upsert({"test": "data"})

    assert resp == {"status": "ok"}
    assert client.conn is None  # connection should be reset due to Connection: close
