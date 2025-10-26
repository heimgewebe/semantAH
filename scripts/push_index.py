#!/usr/bin/env python3
"""Push embeddings from `.gewebe/embeddings.parquet` to the local indexd service."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple
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
    parser = argparse.ArgumentParser(description="Push vorhandene Embeddings in indexd.")
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


def to_batches(df: pd.DataFrame, default_namespace: str) -> Iterable[Dict[str, Any]]:
    """Gruppiert DataFrame-Zeilen zu Upsert-Batches."""

    records = df.to_dict(orient="records")
    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}
    # Für Kollisionsfreiheit pro (namespace, doc_id)
    used_ids: Dict[Tuple[str, str], Set[str]] = {}

    for record in records:
        doc_id = _derive_doc_id(record)
        # Treat NaN/None/empty/whitespace namespaces as missing before defaulting
        _ns_value = record.get("namespace")
        if _is_missing(_ns_value):
            namespace = str(default_namespace)
        else:
            namespace = str(_ns_value).strip() or str(default_namespace)
        key = (namespace, doc_id)
        batch = grouped.setdefault(
            key,
            {
                "doc_id": doc_id,
                "namespace": namespace,
                "chunks": [],
            },
        )
        chunk = _record_to_chunk(record, doc_id)

        # Sicherstellen, dass die Chunk-ID innerhalb desselben Dokuments eindeutig ist
        seen = used_ids.setdefault(key, set())
        original_id = str(chunk["id"])
        candidate = original_id
        disambig = 1
        while candidate in seen:
            disambig += 1
            candidate = f"{original_id}~{disambig}"
        chunk["id"] = candidate
        seen.add(candidate)

        batch["chunks"].append(chunk)

    return grouped.values()


def _derive_doc_id(record: Dict[str, Any]) -> str:
    for key in ("doc_id", "path", "id"):
        value = record.get(key)
        # Skip NaN/None/empty values reported by pandas before accepting
        if _is_missing(value):
            continue
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
            continue
        return str(value)
    raise ValueError("Record without doc identifier")


def _record_to_chunk(record: Dict[str, Any], doc_id: str) -> Dict[str, Any]:
    # robust & kollisionssicher: ggf. mit doc_id präfixieren
    chunk_id = _derive_chunk_id(record, doc_id)
    text = str(record.get("text") or "")
    embedding = _to_embedding(record.get("embedding"))

    meta: Dict[str, Any] = {"embedding": embedding}

    # Zusätzliche Metadaten mitschicken (falls vorhanden)
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


def _derive_chunk_id(record: Dict[str, Any], doc_id: str) -> str:
    """Leite eine kollisionssichere Chunk-ID ab.

    Regeln:
    - Wenn ein Kandidat bereits wie "<doc>#<suffix>" aussieht oder ein '#' enthält,
      wird er direkt verwendet (global eindeutig angenommen).
    - Andernfalls wird der Kandidat als Suffix interpretiert und mit dem doc_id
      per "<doc_id>#<suffix>" kombiniert.
    - Fallback (keine Kandidaten): nutze nur doc_id (entspricht Single-Chunk-Dokument).
    """

    candidates = [
        record.get("chunk_id"),
        record.get("chunk_index"),
        record.get("i"),
        record.get("offset"),
        record.get("id"),
    ]

    for value in candidates:
        if _is_missing(value):
            continue

        if isinstance(value, str):
            v = value.strip()
            if not v:
                continue
            if v.startswith(f"{doc_id}#") or "#" in v:
                return v
            return f"{doc_id}#{v}"

        # Verhindere True/False als numerische Suffixe (#1/#0)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)) and not math.isnan(float(value)):
            return f"{doc_id}#{int(value)}"

        return f"{doc_id}#{value}"

    return str(doc_id)


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


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        result = pd.isna(value)
    except Exception:
        return False
    else:
        if isinstance(result, bool):
            return result
        if hasattr(result, "all"):
            try:
                return bool(result.all())
            except Exception:
                return False
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
    req = request.Request(endpoint, data=data, headers={"Content-Type": "application/json"})
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
        print(f"[push-index] Konnte {args.embeddings} nicht lesen: {exc}", file=sys.stderr)
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
                    response = post_upsert(args.endpoint, sub_batch, timeout=args.timeout)
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
                    status = response.get("status") if isinstance(response, dict) else "ok"
                    print(
                        f"[push-index] Upsert gesendet • doc={sub_batch['doc_id']} namespace={sub_batch['namespace']} chunks={chunks} status={status}",
                    )
                    break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
