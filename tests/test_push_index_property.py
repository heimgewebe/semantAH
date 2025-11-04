import collections
from typing import Any, Dict, List, Tuple

import pandas as pd
import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, settings, strategies as st  # type: ignore

from scripts.push_index import to_batches


def _entries_from_batches(batches: List[Dict[str, Any]]) -> List[Tuple[str, str, str, str]]:
    """Flacht die Batches auf (namespace, doc_id, chunk_id, text)."""

    flattened: List[Tuple[str, str, str, str]] = []
    for batch in batches:
        namespace = str(batch["namespace"])
        doc_id = str(batch["doc_id"])
        for chunk in batch["chunks"]:
            chunk_id = str(chunk["id"])
            text = str(chunk.get("text", ""))
            flattened.append((namespace, doc_id, chunk_id, text))
    return flattened


_namespace_strategy = st.one_of(
    st.none(),
    st.floats(allow_nan=True),
    st.just(""),
    st.just("   "),
    st.text(min_size=1, max_size=8),
)

_doc_id_strategy = st.text(min_size=1, max_size=8)

_maybe_chunk_id = st.one_of(
    st.none(),
    st.booleans(),
    st.text(min_size=1, max_size=8),
)

_text_strategy = st.text(min_size=1, max_size=32)

_embedding_strategy = st.lists(
    st.floats(allow_nan=False, allow_infinity=False, width=16), min_size=2, max_size=2
)

_record_strategy = st.fixed_dictionaries(
    {
        "doc_id": _doc_id_strategy,
        "namespace": _namespace_strategy,
        "chunk_id": _maybe_chunk_id,
        "id": st.none(),
        "text": _text_strategy,
        "embedding": _embedding_strategy,
    }
)


def _counter(entries: List[Tuple[str, str, str, str]]) -> collections.Counter:
    return collections.Counter(entries)


@settings(max_examples=100, deadline=None)
@given(st.lists(_record_strategy, min_size=1, max_size=8))
def test_chunk_ids_stable_across_permutations(records: List[Dict[str, Any]]):
    """Chunk-IDs bleiben bei unterschiedlichen Reihenfolgen stabil."""

    default_namespace = "ns-default"

    df = pd.DataFrame(records)
    baseline_entries = _entries_from_batches(list(to_batches(df, default_namespace=default_namespace)))
    baseline_counter = _counter(baseline_entries)
    assert all("nan" not in chunk_id.lower() for (_, _, chunk_id, _) in baseline_entries)

    shuffled_df = df.sample(frac=1.0, random_state=123).reset_index(drop=True)
    reversed_df = df.iloc[::-1].reset_index(drop=True)

    for dframe in (shuffled_df, reversed_df):
        entries = _entries_from_batches(list(to_batches(dframe, default_namespace=default_namespace)))
        counter = _counter(entries)
        assert counter == baseline_counter
        assert all("nan" not in chunk_id.lower() for (_, _, chunk_id, _) in entries)


@pytest.mark.parametrize(
    "namespace_value,expected_namespace",
    [
        (None, "vault-default"),
        ("", "vault-default"),
        ("   ", "vault-default"),
        (float("nan"), "vault-default"),
        ("vault", "vault"),
    ],
)
def test_default_namespace_applied(namespace_value, expected_namespace):
    df = pd.DataFrame(
        [
            {
                "doc_id": "D",
                "namespace": namespace_value,
                "text": "x",
                "embedding": [0.1, 0.2],
            }
        ]
    )
    batches = list(to_batches(df, default_namespace="vault-default"))
    assert batches[0]["namespace"] == expected_namespace
