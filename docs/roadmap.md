<!--
Quelle: /home/alex/vault-gewebe/coding/semantAH/semantAH brainstorm.md
-->

# semantAH Roadmap

Dieses Dokument überträgt die Ideen aus der Brainstorming-Notiz in umsetzbare Meilensteine.

## Milestone 1 – Grundgerüst
- Rust-Workspace mit `embeddings`-Crate (Ollama-Backend) und `indexd`-Crate (Axum-HTTP, HNSW-Wrapper).
- Persistenz-Pfade `.local/state/hauski/index/obsidian` vorbereiten.
- Feature-Flags: `safe_mode`, `limits.latency.index_topk20_ms` an HNSW koppeln.
- Erste HTTP-Routen:
  - `POST /index/upsert`
  - `POST /index/delete`
  - `POST /index/search`
- Python-Skripte als Platzhalter einchecken.

## Milestone 2 – Ranking & Policies
- Boosts: Zeit, Tags, Canvas-Hop, Cluster.
- Qualitäts-Gates (`score >= 0.82`, Keyphrases ≥ 2, Canvas-Hop ≤ 2 oder shared project).
- Rationale-Felder in `edges.jsonl` und Related-Block.

## Milestone 3 – Feedback & Reports
- Feedback-Schleife für Accept/Reject.
- Orphan-Report, Duplicate-Detection, Topic-Drift.
- Explain-UI im Obsidian-Plugin (separates Repo/Plugin).

## Milestone 4 – Advanced Features
- Session-Context-Boost (aktuelle Arbeitssession).
- Cross-Vault-Namespace (read-only).
- Manual-Lock (`relations_lock: true`).

## Umsetzungshinweise
- Jede Funktionalität modular halten, sodass Experimente / A/B-Tests (Cutoffs) möglich bleiben.
- Alle Heuristiken als Config-Werte in `.gewebe/config.yml` ablegen.
- Provenienz in `.gewebe/meta.json` dokumentieren (Embedding-Modell, Chunking-Parameter, Taxonomie-Version).

