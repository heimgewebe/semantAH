### 📄 tests/conftest.py

**Größe:** 535 B | **md5:** `2df90d78a2e9f5492215bcb9d8f78da8`

```python
import os

try:
    from hypothesis import settings
    from hypothesis.errors import InvalidArgument
except Exception:  # pragma: no cover - hypothesis optional in some environments
    settings = None
else:
    try:
        settings.register_profile(
            "ci",
            settings(max_examples=100, deadline=None, derandomize=True),
        )
    except InvalidArgument:
        # Profile bereits gesetzt (z. B. bei mehrfacher Test-Session)
        pass
    settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "default"))
```

### 📄 tests/test_push_index.py

**Größe:** 4 KB | **md5:** `9de0c222da3761c9414b28f505974bff`

```python
import pandas as pd
import pytest

from itertools import permutations
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
    assert _derive_chunk_id({"chunk_id": "G#abc", "embedding": [1, 0]}, doc_id="D") == "G#abc"
    cid = _derive_chunk_id({"chunk_id": True, "text": "X", "embedding": [1, 0]}, doc_id="D")
    assert cid.startswith("D#t")


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
```

### 📄 tests/test_push_index_e2e.py

**Größe:** 6 KB | **md5:** `6b2872f11b0fae00322c27e9e90597fb`

```python
import json
import os
import signal
import subprocess
import sys
import shlex
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import pytest


def _prebuild_indexd(timeout_s: float = 300.0) -> None:
    """
    Baut das 'indexd'-Binary vor dem Start des Servers.
    Verhindert, dass der Health-Check wegen kalter Builds in CI zu früh ausfällt.
    """
    try:
        # Schneller Check: Wenn das Release/Debug-Binary schon existiert, überspringen wir den Build nicht,
        # sondern verlassen uns trotzdem auf cargo's inkrementellen Build (schnell, no-op).
        cmd = ["cargo", "build", "-q", "-p", "indexd"]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout_s)
    except subprocess.CalledProcessError as e:
        out = e.stdout.decode("utf-8", "replace") if e.stdout else ""
        pytest.fail(f"Prebuild of indexd failed (rc={e.returncode}). Output:\n{out}")
    except subprocess.TimeoutExpired as e:
        pytest.fail(
            "Prebuild of indexd timed out after "
            f"{timeout_s:.0f}s. Command: {shlex.join(e.cmd) if isinstance(e.cmd, (list, tuple)) else e.cmd}"
        )


def _healthz_deadline_from_env(default: float = 120.0) -> float:
    """Erlaubt Override der Health-Check-Deadline via ENV (INDEXD_E2E_HEALTHZ_DEADLINE)."""
    val = os.environ.get("INDEXD_E2E_HEALTHZ_DEADLINE")
    return float(val) if val else default


def _http_json(url: str, payload: dict | None = None, timeout: float = 5.0):
    req = urllib.request.Request(url)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req.add_header("content-type", "application/json")
    else:
        data = None
    with urllib.request.urlopen(req, data=data, timeout=timeout) as resp:
        body = resp.read()
        ctype = resp.headers.get("content-type", "")
        if "application/json" in ctype:
            return json.loads(body.decode("utf-8"))
        return body.decode("utf-8")


def _wait_for_healthz(base: str, deadline_s: float = 15.0):
    url = f"{base}/healthz"
    start = time.time()
    last_err: Exception | None = None
    while time.time() - start < deadline_s:
        try:
            text = _http_json(url, None, timeout=1.5)
            if text == "ok":
                return
        except Exception as e:  # noqa: BLE001
            last_err = e
        time.sleep(0.25)
    raise RuntimeError(f"healthz did not become ready: {last_err!r}")


@contextmanager
def run_indexd():
    """
    Baut 'indexd' vorab, startet dann 'cargo run -p indexd' im Hintergrund auf Port 8080,
    wartet auf /healthz (mit großzügiger Deadline) und räumt beim Verlassen auf.
    """
    # 0) Vorab-Build (kann auf kalten CI-Runnern mehrere Minuten dauern)
    _prebuild_indexd()
    env = os.environ.copy()
    # persistenz in tmp, damit Tests nichts in echte Arbeitsverzeichnisse schreiben
    tmp_state = Path.cwd() / ".test-indexd-state"
    tmp_state.mkdir(exist_ok=True)
    env["INDEXD_DB_PATH"] = str(tmp_state / "store.jsonl")

    proc = subprocess.Popen(
        ["cargo", "run", "-q", "-p", "indexd"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    try:
        # 1) Auf Health warten – großzügige Default-Deadline, via ENV überschreibbar
        _wait_for_healthz(
            "http://127.0.0.1:8080",
            deadline_s=_healthz_deadline_from_env(default=120.0),
        )
        yield proc
    finally:
        # Sauber beenden
        try:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        finally:
            # Logausgabe im Fehlerfall anhängen
            if proc.stdout:
                out = proc.stdout.read().decode("utf-8", "replace")
                sys.stdout.write("\n[indexd output]\n")
                sys.stdout.write(out)
                sys.stdout.write("\n[/indexd output]\n")


@pytest.mark.integration
def test_push_index_script_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # 1) Start server
    with run_indexd():
        base = "http://127.0.0.1:8080"

        # 2) Schreibe Minimal-Parquet in isoliertem Arbeitsverzeichnis
        work = tmp_path / "work"
        (work / ".gewebe").mkdir(parents=True)
        parquet = work / ".gewebe" / "embeddings.parquet"
        df = pd.DataFrame(
            [
                dict(
                    doc_id="D1",
                    namespace="ns",
                    id="c1",
                    text="hello world",
                    embedding=[1.0, 0.0],
                )
            ]
        )
        # pandas benötigt i.d.R. pyarrow/fastparquet – in diesem Projekt sollte pyarrow verfügbar sein.
        df.to_parquet(parquet)

        # 3) push_index.py gegen den laufenden Dienst ausführen
        # Hinweis: wir setzen CWD auf 'work', damit der Default-Pfad funktioniert;
        # übergeben aber explizit --embeddings zur Sicherheit.
        script = Path("scripts") / "push_index.py"
        cmd = [
            sys.executable,
            str(script),
            "--embeddings",
            str(parquet),
            "--endpoint",
            f"{base}/index/upsert",
        ]
        proc = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=25)
        if proc.returncode != 0:
            pytest.fail(f"push_index.py failed: rc={proc.returncode}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")

        # 4) Suche absetzen und Treffer prüfen
        res = _http_json(
            f"{base}/index/search",
            dict(query="hello", k=5, namespace="ns", embedding=[1.0, 0.0]),
            timeout=5.0,
        )
        results = res.get("results", [])
        assert len(results) == 1
        assert results[0]["doc_id"] == "D1"
        assert results[0]["chunk_id"] == "c1"
        assert results[0]["score"] > 0.0
```

### 📄 tests/test_push_index_property.py

**Größe:** 3 KB | **md5:** `3e12e82ce65a8caf3768a9cf692b1b88`

```python
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
    "namespace_value",
    [None, "", "   ", float("nan"), "vault"],
)
def test_default_namespace_applied(namespace_value):
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
    assert batches[0]["namespace"] == "vault-default"
```

