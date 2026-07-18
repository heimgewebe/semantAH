<!--
Quelle: /home/alex/vault-gewebe/coding/semantAH/semantAH brainstorm.md
-->

# semantAH Roadmap

Dieses Dokument überträgt Ideen aus einer historischen Brainstorming-Notiz in mögliche Meilensteine. Es ist kein Ist-Nachweis. Der aktuelle `indexd`-Stand ist in [`indexd-architecture.md`](indexd-architecture.md) dokumentiert.

## Aktueller Abgleich

- Rust-Workspace, Axum-Routen, exakte Suche und JSONL-Start-/Shutdown-Persistenz sind implementiert.
- HNSW, ANN-Aktivierung, Metadatenfilter, `safe_mode`-Kopplung und ein `index_topk20_ms`-Runtime-Gate sind nicht implementiert.
- ANN bleibt von einer separaten evidenzbasierten Aktivierungsschwelle abhängig.

## Historischer Milestone 1 – Grundgerüst
- Rust-Workspace mit `embeddings`-Crate und `indexd`-Crate. Der heutige Store ist exakt-linear; der damals vorgesehene HNSW-Wrapper wurde nicht umgesetzt.
- Persistenz ist heute optional über `INDEXD_DB_PATH` als JSONL-Start-/Shutdown-Snapshot umgesetzt; der damalige HausKI-Pfad ist nicht kanonisch.
- Historische Planung: `safe_mode` und `limits.latency.index_topk20_ms` an einen möglichen ANN-Pfad koppeln; nicht implementiert.
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

