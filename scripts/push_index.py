#!/usr/bin/env python3
"""Push embeddings from `.gewebe/embeddings.parquet` to the local indexd service."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set
from urllib import error, request

import pandas as pd

try:  # NumPy ist optional, hilft aber beim Typ-Check der Embeddings
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - fallback ohne NumPy
    np = None  # type: ignore

DEFAULT_EMBEDDINGS = Path(".gewebe/embeddings.parquet")
DEFAULT_ENDPOINT = "http://localhost:8080/index/upsert"
DEFAULT_NAMESPACE = "vault"
DEFAULT_TIMEOUT = 10.0
DEFAULT_RETRIES = 2
DEFAULT_MAX_CHUNKS = 500


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Push vorhandene Embeddings in indexd."
    )
    parser.add_argument(
        "--embeddings",
        type=Path,
        default=DEFAULT_EMBEDDINGS,
        help="Pfad zur embeddings.parquet-Datei",
    )
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help="HTTP-Endpunkt von indexd (/index/upsert)",
    )
    parser.add_argument(
        "--namespace",
        default=DEFAULT_NAMESPACE,
        help="Fallback-Namespace, falls keiner in den Daten vorhanden ist.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"HTTP-Timeout in Sekunden (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=f"HTTP-Retries bei Fehlern (default: {DEFAULT_RETRIES})",
    )
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=DEFAULT_MAX_CHUNKS,
        help=f"Max. Chunks pro Upsert-Request (default: {DEFAULT_MAX_CHUNKS})",
    )
    return parser.parse_args()


def to_batches(
    df: pd.DataFrame, default_namespace: str = "default"
) -> Iterable[Dict[str, Any]]:
    """
    Groups rows into batches by (namespace, doc_id) and converts them to chunks.
    - `doc_id` is robustly populated per *row* (even if the column exists but values are empty/NaN).
    - Chunk IDs are made unique within a document (..._2, ..._3, ...) to prevent overwrites.
    """
    df = df.copy()

    # Spalten sicherstellen
    if "namespace" not in df.columns:
        df["namespace"] = None
    if "doc_id" not in df.columns:
        # Spalte fehlt komplett -> aus Zeileninhalt ableiten
        df["doc_id"] = df.apply(_derive_doc_id, axis=1)
    else:
        # Spalte existiert -> pro Zeile fehlende/blanke Werte ersetzen
        def _fill_doc_id(row: pd.Series) -> str:
            raw = row.get("doc_id")
            if _is_missing(raw) or (isinstance(raw, str) and not raw.strip()):
                return _derive_doc_id(row)
            return str(raw).strip()

        df["doc_id"] = df.apply(_fill_doc_id, axis=1)

    # Namespace standardisieren
    df["namespace"] = df["namespace"].apply(
        lambda ns: default_namespace if _is_missing(ns) else str(ns).strip()
    )

    # Gruppieren und Chunks erzeugen – mit per-Doc eindeutigen IDs
    for (ns, doc), group in df.groupby(["namespace", "doc_id"]):
        used_ids: Set[str] = set()
        chunks: List[Dict[str, Any]] = []
        for rec in group.to_dict(orient="records"):
            ch = _record_to_chunk(rec, doc_id=str(doc))
            base = str(ch["id"])
            cid = base
            # Eindeutigkeit je Dokument erzwingen
            i = 2
            while cid in used_ids:
                cid = f"{base}_{i}"
                i += 1
            ch["id"] = cid
            used_ids.add(cid)
            chunks.append(ch)

        yield {
            "namespace": ns,
            "doc_id": doc,
            "chunks": chunks,
        }


def _derive_doc_id(rec: Dict[str, Any]) -> str:
    for key in ("doc_id", "path", "id"):
        val = rec.get(key)
        if not _is_missing(val):
            stripped = str(val).strip()
            if stripped:  # Ensure stripped value is not empty
                return stripped
    # Fallback: generate a synthetic doc_id from text hash
    text = rec.get("text")
    if not _is_missing(text):
        h = hashlib.blake2b(str(text).encode("utf-8"), digest_size=8).hexdigest()
        return f"doc#{h}"
    # Final fallback: if text field exists (even if missing), generate synthetic doc_id
    if "text" in rec:
        rec_str = str(sorted(rec.items()))
        h = hashlib.blake2b(rec_str.encode("utf-8"), digest_size=8).hexdigest()
        return f"doc#{h}"
    raise ValueError("No valid doc_id/path/id field found")


def _record_to_chunk(record: Dict[str, Any], doc_id: str) -> Dict[str, Any]:
    chunk_id = _derive_chunk_id(record, doc_id)
    text = str(record.get("text") or "")
    embedding = _to_embedding(record.get("embedding"))

    meta: Dict[str, Any] = {"embedding": embedding}

    for key, value in record.items():
        if key in {"embedding", "text", "doc_id", "namespace", "id"}:
            continue
        if _is_missing(value):
            continue
        if key == "path":
            meta["source_path"] = str(value)
            continue
        if key == "chunk_id":
            try:
                meta["chunk_id"] = int(value)
            except Exception:
                meta["chunk_id"] = value
            continue
        meta[key] = _normalise_meta_value(value)

    return {"id": str(chunk_id), "text": text, "meta": meta}


def _derive_chunk_id(rec: Dict[str, Any], doc_id: str) -> str:
    if isinstance(rec.get("chunk_id"), str) and rec["chunk_id"].startswith("G#"):
        return rec["chunk_id"]
    if isinstance(rec.get("chunk_id"), bool):
        # Boolean values are not valid chunk_ids; fall through to the
        # default row-based logic below. We explicitly do nothing here so
        # that the function continues with the __row fallback.
        pass

    # Use the "id" field if present as chunk_id
    id_val = rec.get("id")
    if not _is_missing(id_val) and not isinstance(id_val, bool):
        return str(id_val)

    row_val = rec.get("__row")
    if row_val is not None and not _is_missing(row_val):
        return f"{doc_id}#r{int(row_val)}"

    text = rec.get("text")
    if _is_missing(text):
        return f"{doc_id}#chunk"
    h = hashlib.blake2b(str(text).encode("utf-8"), digest_size=6).hexdigest()[:6]
    return f"{doc_id}#t{h}"


def _to_embedding(value: Any) -> List[float]:
    if value is None:
        raise ValueError("Missing embedding in record")
    if hasattr(value, "tolist"):
        value = value.tolist()
    if np is not None and isinstance(value, np.ndarray):  # type: ignore[arg-type]
        value = value.tolist()
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"Unexpected embedding type: {type(value)!r}")
    return [float(x) for x in value]


def _is_missing(x: Any) -> bool:
    if x is None:
        return True
    if isinstance(x, float) and math.isnan(x):
        return True
    if isinstance(x, str):
        stripped = x.strip()
        if stripped == "" or stripped.lower() == "nan":
            return True
    return False


def _normalise_meta_value(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "tolist"):
        return value.tolist()  # type: ignore[no-any-return]
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()  # type: ignore[no-any-return]
        except Exception:
            pass
    return value


def _split_batch(batch: Dict[str, Any], max_chunks: int) -> Iterable[Dict[str, Any]]:
    chunks = batch["chunks"]
    if len(chunks) <= max_chunks:
        yield batch
        return

    for offset in range(0, len(chunks), max_chunks):
        yield {
            "doc_id": batch["doc_id"],
            "namespace": batch["namespace"],
            "chunks": chunks[offset : offset + max_chunks],
        }


def post_upsert(
    endpoint: str, payload: Dict[str, Any], *, timeout: float
) -> Dict[str, Any] | None:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint, data=data, headers={"Content-Type": "application/json"}
    )
    with request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8").strip()
        if not body:
            return None
        return json.loads(body)


def main() -> int:
    args = parse_args()

    if not args.embeddings.exists():
        print(f"[push-index] Fehlend: {args.embeddings}", file=sys.stderr)
        return 1

    try:
        df = pd.read_parquet(args.embeddings)
    except Exception as exc:  # pragma: no cover - IO-Fehler
        print(
            f"[push-index] Konnte {args.embeddings} nicht lesen: {exc}", file=sys.stderr
        )
        return 1

    if df.empty:
        print("[push-index] Keine Embeddings gefunden — nichts zu tun.")
        return 0

    batches = list(to_batches(df, args.namespace))
    if not batches:
        print("[push-index] Keine gültigen Batches erzeugt.", file=sys.stderr)
        return 1

    for batch in batches:
        for sub_batch in _split_batch(batch, args.max_chunks):
            for attempt in range(args.retries + 1):
                try:
                    response = post_upsert(
                        args.endpoint, sub_batch, timeout=args.timeout
                    )
                except error.HTTPError as exc:
                    if attempt >= args.retries:
                        print(
                            f"[push-index] HTTP-Fehler für doc={sub_batch['doc_id']} namespace={sub_batch['namespace']}: {exc}",
                            file=sys.stderr,
                        )
                        return 1
                    continue
                except error.URLError as exc:
                    if attempt >= args.retries:
                        print(
                            f"[push-index] Konnte {args.endpoint} nicht erreichen: {exc.reason}",
                            file=sys.stderr,
                        )
                        return 1
                    continue
                else:
                    chunks = len(sub_batch["chunks"])
                    status = (
                        response.get("status") if isinstance(response, dict) else "ok"
                    )
                    print(
                        f"[push-index] Upsert gesendet • doc={sub_batch['doc_id']} namespace={sub_batch['namespace']} chunks={chunks} status={status}",
                    )
                    break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
