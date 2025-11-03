### 📄 crates/indexd/Cargo.toml

**Größe:** 624 B | **md5:** `f0c0a86441e61016f3521680a54e7680`

```toml
[package]
name = "indexd"
version = "0.1.0"
edition = "2021"
license = "MIT"
description = "HTTP service for indexing and semantic search"

[dependencies]
anyhow.workspace = true
axum.workspace = true
serde.workspace = true
serde_json.workspace = true
tokio.workspace = true
tracing.workspace = true
tracing-subscriber.workspace = true
config.workspace = true
thiserror.workspace = true
futures.workspace = true

[dependencies.embeddings]
path = "../embeddings"

[dev-dependencies]
tower = "0.5"
tempfile = "3"
reqwest = { version = "0.12", default-features = false, features = ["json", "rustls-tls"] }
async-trait = "0.1"
```

### 📄 crates/indexd/README.md

**Größe:** 2 KB | **md5:** `5d1fc59707444675aeef4e3d42a991da`

```markdown
# `indexd` crate

`indexd` ist der HTTP-Dienst für den semantischen Index. Er kapselt den Axum-Server, einen im Speicher gehaltenen `VectorStore` und stellt CRUD-Operationen für Chunks sowie eine Suchroute bereit.

## Komponenten
- `AppState`: verwaltet den `VectorStore` (RW-Lock) und kann in Tests ersetzt werden.
- `run`: Hilfsfunktion, die den Server unter `0.0.0.0:8080` startet und zusätzliche Routen injiziert.
- `store`-Modul: In-Memory-Vektorablage mit Namensraum-Unterstützung und einfacher Persistenz-Erweiterbarkeit.

## HTTP-API
| Methode & Pfad | Beschreibung | Beispiel-Payload |
| --- | --- | --- |
| `POST /index/upsert` | Nimmt Chunks mit Embeddings entgegen und ersetzt vorhandene Einträge atomar. | `{ "doc_id": "note-42", "namespace": "vault", "chunks": [{ "id": "note-42#0", "text": "...", "meta": { "embedding": [0.1, 0.2], "source_path": "notes/foo.md" }}] }` |
| `POST /index/delete` | Entfernt alle Chunks eines Dokuments aus einem Namespace. | `{ "doc_id": "note-42", "namespace": "vault" }` |
| `POST /index/search` | Führt eine k-Nearest-Nachbarn-Suche aus und liefert Treffer mitsamt Score & Rationale zurück. Aktuell noch Stub → leeres `results`-Array. | `{ "query": "backup policy", "namespace": "vault", "k": 10 }` |
| `GET /healthz` | Healthcheck für Liveness-Probes. | – |

Antworten enthalten bei Fehlern strukturierte JSON-Bodies (`{"error": "..."}`) sowie `400 Bad Request` bei Validierungsproblemen.

## Beispielstart
```bash
cargo run -p indexd
```

## Tests
- `tests/healthz.rs`: prüft den Healthcheck-Endpunkt.
- Integrationstest in `src/main.rs`: stellt sicher, dass fehlende Dimensionalität nicht zum teilweisen Upsert führt.

Für persistente Vector-Stores oder echte Ähnlichkeitssuche kann das `store`-Modul ersetzt und `handle_search` erweitert werden.
```

