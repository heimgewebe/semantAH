# HTTP-API Referenz (`indexd`)

Der Dienst `crates/indexd` stellt einen JSON-basierten HTTP-API-Layer bereit. Die Routen werden über Axum exponiert und laufen standardmäßig auf `http://localhost:8080`.

## Authentifizierung
Lokale Entwicklungsumgebungen laufen ohne Authentifizierung. Für produktive Setups ist ein vorgelagerter Reverse-Proxy mit Auth/ACL vorgesehen.

## Endpunkte
### `POST /index/upsert`
- **Zweck:** Registriert oder aktualisiert Chunks eines Dokuments.
- **Body:**
  ```json
  {
    "doc_id": "note-42",
    "namespace": "vault",
    "chunks": [
      {
        "id": "note-42#0",
        "text": "Ein Abschnitt...",
        "meta": {
          "embedding": [0.12, 0.98],
          "source_path": "notes/example.md",
          "tags": ["project/infra"]
        }
      }
    ]
  }
  ```
- **Antwort:**
  ```json
  {
    "status": "accepted",
    "chunks": 1
  }
  ```
- **Fehler:** `400 Bad Request` falls `meta.embedding` fehlt oder unterschiedliche Dimensionalität festgestellt wird.

### `POST /index/delete`
- **Zweck:** Entfernt sämtliche Chunks eines Dokuments innerhalb eines Namespace.
- **Body:** `{ "doc_id": "note-42", "namespace": "vault" }`
- **Antwort:** `{ "status": "accepted" }`

### `POST /index/search`
- **Zweck:** Führt eine vektorbasierte Suche aus.
- **Body:**
  ```json
  {
    "query": {
      "text": "backup policy",
      "meta": {
        "embedding": [0.12, 0.98]
      }
    },
    "namespace": "vault",
    "k": 10,
    "filters": { "tags": ["policy"] }
  }
  ```
- **Antwort:**
  ```json
  {
    "results": [
      {
        "doc_id": "note-42",
        "chunk_id": "note-42#0",
        "score": 0.87,
        "snippet": "...",
        "rationale": ["Tag match: policy", "Vector cosine: 0.87"]
      }
    ]
  }
  ```
  **Kompatibilität & Priorität:** Es gibt mehrere Quellen für Embeddings.
  Die Auswertungsreihenfolge ist **klar definiert** (erstes vorhandenes gewinnt):
  1. `query.meta.embedding`
  2. Top-Level `embedding`
  3. Legacy Top-Level `meta.embedding`
  4. **Serverseitig**: Falls oben nichts gesetzt und `INDEXD_EMBEDDER_PROVIDER` konfiguriert ist,
     wird der Query-Text serverseitig eingebettet (z. B. via Ollama).

  Ein `embedding` ist eine Liste von Gleitkommazahlen (`f32`). Ist auf dem
  Server `INDEXD_EMBEDDER_PROVIDER=ollama` (plus optionale Parameter) gesetzt,
  wird – falls kein Embedding im Request vorliegt – der Query-Text über den
  konfigurierten Provider eingebettet.
  Aktuell liefert der Stub eine leere Trefferliste; das Schema ist dennoch stabil und kann für Clients genutzt werden.

### `GET /healthz`
- **Zweck:** Liveness-Check; antwortet mit `200 OK` und Body `"ok"`.

### `POST /embed/text`
- **Zweck:** Erzeugt ein versioniertes, schema-konformes Embedding mit vollständiger Provenienz.
- **Requires:** `INDEXD_EMBEDDER_PROVIDER` muss konfiguriert sein (z.B. `ollama`).
- **Body:**
  ```json
  {
    "text": "Text to embed",
    "namespace": "osctx",
    "source_ref": "event-abc-123"
  }
  ```
  - `namespace`: Muss einer der fünf kanonischen Namespaces sein: `chronik`, `osctx`, `docs`, `code`, `insights`.
  - `source_ref`: Eindeutige Referenz zur Quelle (Event-ID, Pfad, Hash). Darf nicht leer sein.
- **Antwort (Schema-konform mit `os.context.text.embed.schema.json`):**
  ```json
  {
    "embedding_id": "embed-uuid-...",
    "text": "Text to embed",
    "embedding": [0.123, -0.456, 0.789, ...],
    "embedding_model": "nomic-embed-text",
    "embedding_dim": 768,
    "model_revision": "nomic-embed-text-768",
    "generated_at": "2026-01-03T21:00:00Z",
    "namespace": "osctx",
    "source_ref": "event-abc-123",
    "producer": "semantAH",
    "determinism_tolerance": 1e-6
  }
  ```
- **Fehler:**
  - `400 Bad Request`: Leerer `text` oder leerer `source_ref`.
  - `422 Unprocessable Entity`: Ungültiger Namespace (nicht einer der 5 kanonischen Namespaces).
  - `503 Service Unavailable`: Embedder nicht konfiguriert oder fehlgeschlagen.
- **Garantien:**
  - **Determinismus (Ziel)**: Gleicher Input + gleiche Modellrevision sollte reproduzierbare Vektoren liefern (innerhalb Provider-Grenzen). Reproduzierbarkeit ist provider-abhängig (GPU, BLAS, Provider-Updates können Varianz verursachen). `determinism_tolerance` (1e-6) ist Vergleichstoleranz, keine Garantie.
  - **Versionierung**: `model_revision` identifiziert Modell und Dimensionalität eindeutig.
  - **Provenienz**: Jedes Embedding hat `source_ref` und `producer`.

## Antwortschema & Fehlercodes
- Erfolgreiche Antworten sind JSON (`application/json`).
+- **400 Bad Request**: Clientseitige Probleme (z. B. falsches `embedding`-Format,
+  Dimensionsmismatch, invalides JSON) – Response: `{ "error": "…" }`.
+- **503 Service Unavailable**: Serverseitige Einbettung fehlgeschlagen
+  (z. B. Embedder/Provider nicht erreichbar oder liefert keine Vektoren).
+  Clients sollten verzögert **retry** ausführen. Response: `{ "error": "…" }`.
 - Weitere HTTP-Codes (z. B. `500`) sind für zukünftige Persistenzfehler reserviert.

## Beispiele mit `curl`
```bash
curl -X POST http://localhost:8080/index/upsert \
  -H 'Content-Type: application/json' \
  -d '{
        "doc_id": "note-42",
        "namespace": "vault",
        "chunks": [{"id":"note-42#0","text":"...","meta":{"embedding":[0.1,0.2]}}]
      }'

curl -X POST http://localhost:8080/index/search \
  -H 'Content-Type: application/json' \
  -d '{
        "query": {
          "text": "backup",
          "meta": {"embedding": [0.1, 0.2]}
        },
        "namespace": "vault",
        "k": 5
      }'

# Serverseitige Embeddings
curl -X POST http://localhost:8080/index/search \
  -H 'Content-Type: application/json' \
  -d '{
        "query": "backup",
        "namespace": "vault",
        "k": 5
      }'

# Top-Level `embedding`
curl -X POST http://localhost:8080/index/search \
  -H 'Content-Type: application/json' \
  -d '{
        "query": "backup",
        "namespace": "vault",
        "embedding": [0.1, 0.2],
        "k": 5
      }'

# Legacy `meta.embedding` (Top-Level)
curl -X POST http://localhost:8080/index/search \
  -H 'Content-Type: application/json' \
  -d '{
        "query": "backup",
        "namespace": "vault",
        "meta": {"embedding": [0.1, 0.2]},
        "k": 5
      }'
```

## Logging & Observability
- Jeder Request wird über `tracing` mit Doc-ID/Namespace protokolliert.
- Für Telemetrie-Exports kann der Dienst um OTLP-Exporter ergänzt werden (siehe `docs/runbook.observability.md`).
