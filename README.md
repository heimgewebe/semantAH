# semantAH

**semantAH** ist der semantische Index- und Graph-Ableger von [HausKI](https://github.com/alexdermohr/hauski).
Es zerlegt Notizen (z. B. aus Obsidian), erstellt **Embeddings**, baut daraus einen **Index und Wissensgraphen** und schreibt „Related“-Blöcke direkt in die Markdown-Dateien zurück.

- **Einbettung in HausKI:** dient dort als semantische Gedächtnis-Schicht (Memory Layer).
- **Eigenständig nutzbar:** Skript-Pipeline (`tools/`, `Makefile`) oder Rust-Dienst (`/index/upsert`, `/index/search`).
- **Artefakte:** `.gewebe/embeddings.parquet`, `nodes.jsonl`, `edges.jsonl`, Reports.
- **KPIs:** Index-Suche top-k=20 in < 60 ms (p95).
- **Integrationen:** Obsidian Canvas (Auto-Links), systemd-Timer, WGX-Recipes.

Mehr zur Integration: [docs/hauski.md](docs/hauski.md).

SemantAH ist eine lokal laufende Wissensgraph- und Semantik-Pipeline für Obsidian-Vaults. Das Projekt adaptiert die Blaupausen aus `semantAH.md` und `semantAH brainstorm.md` und zielt darauf ab, eine modulare, reproduzierbare Infrastruktur aufzubauen:

- **Rust Workspace** mit eigenständigen Crates für Embeddings-Provider (`embeddings`) und Vektorindex/HTTP-Service (`indexd`).
- **Python-Tooling** zum Erzeugen von Embeddings, Graph-Knoten/Kanten und automatischen Related-Blöcken in Markdown-Notizen.
- **Konfigurierbare Policies** (Cutoffs, Boosts, Safe Mode) sowie Persistenz in `.gewebe/`.
- **Automatisierung** via Makefile, `wgx`-Recipes und optional systemd-Timer.

> ⚠️ Dies ist ein Initialzustand. Viele Komponenten sind noch Platzhalter, damit der Code schrittweise erweitert werden kann. Die README dokumentiert den Aufbau, die Verzeichnisse und nächsten Arbeitsschritte.

## Repository-Layout

```
.
├── Cargo.toml           # Workspace-Manifest
├── README.md            # Dieses Dokument
├── crates/
│   ├── embeddings/      # Embedder-Trait & Ollama-Backend
│   └── indexd/          # HTTP-Service + Vektorindex-Fassade
├── docs/
│   ├── blueprint.md     # Vollständiges Konzept (kopiert aus Vault-Notizen)
│   └── roadmap.md       # Umsetzungsschritte & Fortschritt
├── scripts/
│   ├── build_index.py   # Stub für Index-Lauf
│   ├── build_graph.py   # Stub für Graph-Aufbau
│   └── update_related.py# Stub für Related-Blöcke
├── Makefile             # Tasks (venv, index, graph, related)
└── systemd/
    ├── vault-gewebe.service
    └── vault-gewebe.timer
```

## Quickstart

1. Installiere Rust (>=1.75) und Python (>=3.10).
2. Richte ein virtuelles Python-ENV mit `make venv` ein.
3. Erzeuge die Artefakte in `.gewebe/` (Stub) mit `make all`.
4. Starte den Rust-Dienst zum Testen: `cargo run -p indexd`.

## Export
- Contracts: `contracts/semantics/*.schema.json`
- Daten-Dumps (optional): `.gewebe/out/{nodes.jsonl,edges.jsonl,reports.json}` (JSONL pro Zeile).

## Status

- [x] Workspace scaffolded
- [ ] Embeddings-Berechnung implementiert
- [ ] Vektorindex & Persistenz
- [ ] Obsidian-Plugin/Adapter
- [ ] Tests & Benchmarks

## Veröffentlichungs-Workflow

1. Erstelle ein neues GitHub-Repo: `gh repo create alex/semantAH --public`.
2. Verbinde dein lokales Repo: `git init`, `git remote add origin git@github.com:alex/semantAH.git`.
3. Commit & push: `git add . && git commit -m "Initial commit" && git push -u origin main`.

## Lizenz

MIT – passe gerne an, falls du restriktivere Policies brauchst.

