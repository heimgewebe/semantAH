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
  Aktuell liefert der Stub eine leere Trefferliste; das Schema ist dennoch stabil und kann für Clients genutzt werden.

### `GET /healthz`
- **Zweck:** Liveness-Check; antwortet mit `200 OK` und Body `"ok"`.

## Antwortschema & Fehlercodes
- Erfolgreiche Antworten sind JSON (`application/json`).
- Fehlerhafte Requests geben `400 Bad Request` mit `{ "error": "…" }` zurück.
- Weitere HTTP-Codes (z. B. `500`) sind für zukünftige Persistenzfehler reserviert.

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
          "meta": { "embedding": [0.1, 0.2] }
        },
        "namespace": "vault",
        "k": 5
      }'
```

## Logging & Observability
- Jeder Request wird über `tracing` mit Doc-ID/Namespace protokolliert.
- Für Telemetrie-Exports kann der Dienst um OTLP-Exporter ergänzt werden (siehe `docs/runbook.observability.md`).
