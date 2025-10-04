# Quickstart für semantAH

## Voraussetzungen
- **Rust** ≥ 1.75 (`rustup`), **Python** ≥ 3.10
- Optional: **uv** (schnelles Lock/Env), `make`

## Setup
```bash
make venv        # oder: uv sync
cp examples/semantah.example.yml semantah.yml
```

## Lauf
```bash
make all         # erstellt .gewebe/ Artefakte
cargo run -p indexd
```

## Hinweise
- Logs: `.gewebe/logs`
- Artefakte: `.gewebe/embeddings.parquet`, `.gewebe/out/*`
- Related-Blöcke in Markdown: nur wenn `related.write_back: true`
