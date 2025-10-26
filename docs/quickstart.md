# semantAH · Quickstart

## Voraussetzungen
- Rust (stable), Python ≥ 3.10
- Optional: `uv` (für schnelle Envs)

## Installation (lokal)
```bash
uv sync            # oder: make venv
```

## Konfiguration
```bash
cp examples/semantah.example.yml semantah.yml
# passe vault_path und out_dir an (aktuell noch nicht ausgewertet)
```

## Pipeline laufen lassen
```bash
make all           # embeddings → index → graph → related
cargo run -p indexd
curl -fsS localhost:8080/healthz || true

# Index-Stubs registrieren (Embeddings im Meta-Objekt)
curl -sS localhost:8080/index/upsert \
  -H 'content-type: application/json' \
  -d '{
    "doc_id": "demo-note",
    "namespace": "vault",
    "chunks": [{
      "id": "demo-note#0",
      "text": "Hello demo",
      "meta": {
        "embedding": [0.1, 0.2, 0.3],
        "snippet": "Hello demo"
      }
    }]
  }'

# Smoke-Test: Suche mit query.meta.embedding (liefert ggf. leere Treffer)
curl -sS localhost:8080/index/search \
  -H 'content-type: application/json' \
  -d '{
    "query": {
      "text": "hello",
      "meta": { "embedding": [0.1, 0.2, 0.3] }
    },
    "namespace": "vault",
    "k": 5
  }'
```

Weitere Details:
- API-Beispiele: [indexd-api.md](indexd-api.md)
- Pipeline-Skripte: [scripts/README.md](../scripts/README.md)
- Operative Schritte: [Runbooks](runbooks/)

## Artefakte
- `.gewebe/embeddings.parquet`
- `.gewebe/out/{nodes.jsonl,edges.jsonl,reports.json}`

## Troubleshooting
- Leere/zu große Dateien werden übersprungen → Logs in `.gewebe/logs` prüfen.
- Bei fehlenden Modellen: Provider in `semantah.yml` anpassen.
