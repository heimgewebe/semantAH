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
# passe vault_path und out_dir an
```

## Pipeline laufen lassen
```bash
make all           # embeddings → index → graph → related
cargo run -p indexd
curl -fsS localhost:8080/healthz || true
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
