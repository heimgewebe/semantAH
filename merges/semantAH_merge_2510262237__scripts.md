### 📄 scripts/README.md

**Größe:** 2 KB | **md5:** `54a7526b2afa9ee3bb4852a60476ddc8`

```markdown
# Pipeline-Skripte

Die Python-Skripte im Verzeichnis `scripts/` bilden den orchestrierten Pipeline-Flow von semantAH nach. Aktuell handelt es sich um ausführbare Stubs, die Struktur, Artefakte und Logging demonstrieren. Sie können als Ausgangspunkt für produktive Implementierungen dienen.

| Skript | Zweck | Output | Hinweise |
| --- | --- | --- | --- |
| `build_index.py` | Erstellt Embedding-Datei (`embeddings.parquet`). | `.gewebe/embeddings.parquet` | Legt bei Bedarf das Zielverzeichnis an und erzeugt eine CSV-ähnliche Platzhalterdatei. |
| `build_graph.py` | Übersetzt Embeddings in Graph-Knoten/-Kanten. | `.gewebe/nodes.jsonl`, `.gewebe/edges.jsonl` | Schreibt minimal valide JSONL-Zeilen, damit Folgeprozesse getestet werden können. |
| `update_related.py` | Fügt Markdown-Dateien einen Related-Block hinzu. | `notes_stub/example.md` | Verhindert doppelte Blöcke durch Marker `<!-- related:auto:start -->`. |
| `export_insights.py` | Exportiert Tageszusammenfassungen für Dashboards. | `$VAULT_ROOT/.gewebe/insights/today.json` | Erwartet die Umgebungsvariable `VAULT_ROOT`; erzeugt strukturierte JSON-Stubs ≤10 KB. |

## Ausführung
```bash
make venv           # virtuelle Umgebung anlegen
. .venv/bin/activate
python scripts/build_index.py
python scripts/build_graph.py
python scripts/update_related.py
```

Die Skripte nutzen aktuell keine externen Abhängigkeiten und lassen sich direkt mit Python ≥3.10 ausführen. Für produktiven Einsatz sollten die Stub-Ausgaben durch echte Pipeline-Schritte ersetzt und mit `semantah.yml` parametrisiert werden.
```

### 📄 scripts/build_graph.py

**Größe:** 636 B | **md5:** `17da42d1abe3ab91b758ce562c52c1fb`

```python
#!/usr/bin/env python3
"""Stub script to turn embeddings into graph nodes and edges.

This is a placeholder for the full implementation.
See `docs/blueprint.md` for the full concept.
"""

import json
from pathlib import Path

GEWEBE = Path(".gewebe")
NODES = GEWEBE / "nodes.jsonl"
EDGES = GEWEBE / "edges.jsonl"


def main() -> None:
    GEWEBE.mkdir(exist_ok=True)
    NODES.write_text(f"{json.dumps({'id': 'stub:node'})}\n")
    EDGES.write_text(f"{json.dumps({'s': 'stub:node', 'p': 'related', 'o': 'stub:other', 'w': 0.0})}\n")
    print("[stub] build_graph → wrote", NODES, "and", EDGES)


if __name__ == "__main__":
    main()
```

### 📄 scripts/build_index.py

**Größe:** 504 B | **md5:** `54e7e86820d86a0bc6935bd52e81f022`

```python
#!/usr/bin/env python3
"""Stub script for building embeddings and chunk index artifacts.

This is a placeholder for the full implementation.
See `docs/blueprint.md` for the full concept.
"""

from pathlib import Path

OUTPUT = Path(".gewebe/embeddings.parquet")


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if not OUTPUT.exists():
        OUTPUT.write_text("id,text,embedding\n")
    print("[stub] build_index → wrote", OUTPUT)


if __name__ == "__main__":
    main()
```

### 📄 scripts/export_insights.py

**Größe:** 1 KB | **md5:** `c19d848a351934d606ebb312990933ac`

```python
#!/usr/bin/env python3
"""
Stub: exportiert Tages-Insights als JSON.
Ziel: $VAULT_ROOT/.gewebe/insights/today.json
"""
from __future__ import annotations
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

def main() -> int:
    vault_root = os.environ.get("VAULT_ROOT", os.path.expanduser("~/Vaults/main"))
    out_dir = Path(vault_root) / ".gewebe" / "insights"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "today.json"

    now = datetime.now(timezone.utc).astimezone()
    payload = {
        "date": now.date().isoformat(),
        "generated_at": now.isoformat(),
        "version": 1,
        "summary": {
            "notes_processed": 0,
            "embeddings_added": 0,
            "graph_edges_new": 0,
            "top_tags": [],
        },
        "meta": {
            "hostname": os.uname().nodename if hasattr(os, "uname") else "unknown",
            "vault_root": vault_root,
        },
    }
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"Wrote insights → {out_file}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### 📄 scripts/push_index.py

**Größe:** 11 KB | **md5:** `a0618f716bb70ae930f09ba86064bdaa`

```python
#!/usr/bin/env python3
"""Push embeddings from `.gewebe/embeddings.parquet` to the local indexd service."""

from __future__ import annotations

import argparse
import hashlib
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
        ns_value = record.get("namespace")
        if _is_missing(ns_value):
            namespace = default_namespace
        else:
            namespace = str(ns_value).strip()
            if not namespace:
                namespace = default_namespace
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
    """Derive a stable document identifier from a record."""

    for key in ("doc_id", "path", "id"):
        value = record.get(key)
        if _is_missing(value):
            continue
        if isinstance(value, (str, int)):
            candidate = str(value).strip()
            if candidate:
                return candidate
            continue
        if value is not None:
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
    - Wenn ein Kandidat bereits wie ``<doc_id>#<suffix>`` aussieht oder ein ``#`` enthält,
      wird er direkt verwendet (global eindeutig angenommen).
    - Ansonsten wird der Kandidat als Suffix interpretiert und mit dem ``doc_id`` kombiniert.
    - Fallbacks (keine Kandidaten): nutze Text-Hash oder Row-Hints, dann erst generisches ``#chunk``.
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

        # Verhindere True/False als numerische Suffixe (#1/#0)
        if isinstance(value, bool):
            continue

        if isinstance(value, str):
            v = value.strip()
            if not v:
                continue
            if v.startswith(f"{doc_id}#") or "#" in v:
                return v
            return f"{doc_id}#{v}"

        try:
            if isinstance(value, (int, float)) and not math.isnan(float(value)):
                return f"{doc_id}#{int(value)}"
        except Exception:
            pass

        return f"{doc_id}#{str(value)}"

    text = record.get("text")
    if not _is_missing(text):
        digest = hashlib.blake2b(str(text).encode("utf-8"), digest_size=8).hexdigest()
        return f"{doc_id}#t{digest}"

    for hint_key in ("__row", "_row", "row_index", "_i", "i"):
        hint = record.get(hint_key)
        if not _is_missing(hint):
            return f"{doc_id}#r{hint}"

    return f"{doc_id}#chunk"


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
```

### 📄 scripts/update_related.py

**Größe:** 913 B | **md5:** `6be07c80b0c1c3d138c5ad78ff63540c`

```python
#!/usr/bin/env python3
"""Stub script to inject related blocks into Markdown files.

This is a placeholder for the full implementation.
See `docs/blueprint.md` for the full concept.
"""

from pathlib import Path

RELATED_BLOCK = """<!-- related:auto:start -->\n## Related\n- [[Example]] — (0.00; stub)\n<!-- related:auto:end -->\n"""


def inject_related(note: Path) -> None:
    text = note.read_text(encoding="utf-8") if note.exists() else ""
    if "<!-- related:auto:start -->" in text:
        return
    note.write_text(text + "\n" + RELATED_BLOCK, encoding="utf-8")


def main() -> None:
    notes_dir = Path(".gewebe/notes_stub")
    notes_dir.mkdir(parents=True, exist_ok=True)
    note = notes_dir / "example.md"
    note.write_text("# Example Note\n", encoding="utf-8")
    inject_related(note)
    print("[stub] update_related → injected block into", note)


if __name__ == "__main__":
    main()
```

