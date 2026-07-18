# `indexd` crate

`indexd` ist der Axum-Dienst für den semantischen Index. Die kanonische
Ist-Architektur, Leistungsgrenzen und Nichtaussagen stehen in
[`docs/indexd-architecture.md`](../../docs/indexd-architecture.md).

## Implementierte Komponenten

- `AppState`: hält einen `Tokio::RwLock<VectorStore>` und optional einen Embedder.
- `run`: lädt optional `INDEXD_DB_PATH`, startet den Server standardmäßig auf
  `0.0.0.0:8080` und speichert beim geordneten Shutdown atomar zurück. Die Bind-Adresse
  kann über `INDEXD_BIND_ADDR` gesetzt werden.
- `store`: exakte lineare Cosinus-Suche über normalisierte Vektoren, Namespace-Isolation,
  deterministische Tie-Breaks und O(1)-Snapshots für Ranking außerhalb des Store-Locks.
- `persist`: JSONL-Start-/Shutdown-Persistenz; kein WAL und keine kontinuierliche
  Durability-Garantie.

## HTTP-API

| Methode & Pfad | Verhalten |
| --- | --- |
| `POST /index/upsert` | Fügt Chunks ein oder ersetzt sie atomar; alle Vektoren müssen dieselbe Dimension haben. |
| `POST /index/delete` | Entfernt alle Chunks eines Dokuments innerhalb eines Namespace. |
| `POST /index/search` | Führt exakte Top-k-Suche aus und liefert Score sowie optional `meta.snippet`; `filters` wird derzeit nicht angewendet. |
| `POST /embed/text` | Erzeugt über den konfigurierten Embedder ein provenancegebundenes Embedding. |
| `GET /healthz` | Liveness-Check. |

Die vollständigen Payloads und Fehlerverträge stehen in
[`docs/indexd-api.md`](../../docs/indexd-api.md).

## Start

```bash
cargo run -p indexd
```

Optional:

```bash
export INDEXD_BIND_ADDR=127.0.0.1:49152
export INDEXD_DB_PATH=.gewebe/indexd/store.jsonl
cargo run -p indexd
```

## Tests und Benchmark

```bash
cargo test -p indexd --all-features --locked
cargo bench -p indexd --bench indexd_real_workload -- --profile smoke
```

Nicht implementiert sind HNSW/Faiss/andere ANN-Indizes, Metadatenfilter, Sled/SQLite,
Write-Ahead-Logging, Authentifizierung und Multi-Instanz-Koordination.
