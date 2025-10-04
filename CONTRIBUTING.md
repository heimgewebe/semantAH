# CONTRIBUTING

## Dev-Setup
1. Rust ≥ 1.75, Python ≥ 3.10
2. `make venv` (oder `uv sync`)
3. `make all`, `cargo run -p indexd`

## Konventionen
- Rust: `cargo fmt`, `cargo clippy`
- Python: `ruff check`, `pytest`
- Commits: klar und klein; PRs mit reproduzierbaren Schritten

## Tests
- `just`/`make` Targets folgen noch in der Roadmap
