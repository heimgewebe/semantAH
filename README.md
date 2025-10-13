# semantAH

**semantAH** ist der semantische Index- und Graph-Ableger von [HausKI](https://github.com/heimgewebe/hausKI).
Es zerlegt Notizen (z. B. aus Obsidian), erstellt **Embeddings**, baut daraus einen **Index und Wissensgraphen** und schreibt „Related“-Blöcke direkt in die Markdown-Dateien zurück.

- **Einbettung in HausKI:** dient dort als semantische Gedächtnis-Schicht (Memory Layer).
- **Eigenständig nutzbar:** Skript-Pipeline (`tools/`, `Makefile`) oder Rust-Dienst (`/index/upsert`, `/index/search`).
- **Artefakte:** `.gewebe/embeddings.parquet`, `nodes.jsonl`, `edges.jsonl`, Reports.
- **KPIs:** Index-Suche top-k=20 in < 60 ms (p95).
- **Integrationen:** Obsidian Canvas (Auto-Links), systemd-Timer, WGX-Recipes.

Mehr zur Integration: [docs/hauski.md](docs/hauski.md).

SemantAH ist eine lokal laufende Wissensgraph- und Semantik-Pipeline für Obsidian-Vaults. Das Projekt adaptiert die Blaupausen aus `semantAH.md` und `semantAH brainstorm.md` und zielt darauf ab, eine modulare, reproduzierbare Infrastruktur aufzubauen:

- **Rust Workspace** mit eigenständigen Crates für Embeddings-Provider (`embeddings`) und Vektorindex/HTTP-Service (`indexd`).
- **Python-Tooling (aktuell Stubs)** zum Erzeugen von Embeddings, Graph-Knoten/Kanten und automatischen Related-Blöcken in Markdown-Notizen.
- **Konfigurierbare Policies** (Cutoffs, Boosts, Safe Mode) sowie Persistenz in `.gewebe/`.
- **Automatisierung** via Makefile, `wgx`-Recipes und optional systemd-Timer.

> ⚠️ **Dies ist ein Initialzustand.** Die Python-Skripte sind aktuell nur Platzhalter (Stubs), die leere Artefakte erzeugen. Die Kernlogik wird schrittweise in Rust implementiert. Die README dokumentiert den Ziel-Aufbau und die nächsten Schritte.

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

Für ein ausführliches Step-by-Step siehe **docs/quickstart.md**. Kurzform:

1. **Rust & Python bereitstellen**
   - Rust ≥ 1.75 (rustup), Python ≥ 3.10
   - Optional: `uv` für schnelles Python-Lock/Env
2. **Python-Env & Tools**
   - `make venv` (oder `uv sync`)
3. **Beispielkonfiguration**
   - `cp examples/semantah.example.yml semantah.yml` → Pfade anpassen
4. **Pipeline laufen lassen**
   - `make all` (erstellt `.gewebe/`-Artefakte)
   - `make demo` (Mini-Demo auf Basis der Example-Konfig)
5. **Service testen**
   - `cargo run -p indexd`

## Export

- Contracts: `contracts/semantics/*.schema.json`
- Daten-Dumps (optional): `.gewebe/out/{nodes.jsonl,edges.jsonl,reports.json}` (JSONL pro Zeile).

## Status

Aktuell implementiert/geplant (beweglich):

- Workspace scaffolded ✅
- Embeddings-Berechnung (Python, Provider-wahl) 🚧
- Vektorindex & Persistenz (Rust-Dienst) 🚧
- Obsidian-Adapter / Related-Writer 🚧
- Tests & Benchmarks 🚧 (siehe „Roadmap“)

## Veröffentlichungs-Workflow

1. Erstelle ein neues GitHub-Repo: `gh repo create heimgewebe/semantAH --public`.
2. Verbinde dein lokales Repo: `git init`, `git remote add origin git@github.com:heimgewebe/semantAH.git`.
3. Commit & push: `git add . && git commit -m "Initial commit" && git push -u origin main`.

## Lizenz

MIT – passe gerne an, falls du restriktivere Policies brauchst.

---

## Konfiguration

Eine minimale Beispiel-Konfiguration findest du in `examples/semantah.example.yml`. Wichtige Felder:

- `vault_path`: Pfad zum Obsidian-Vault
- `out_dir`: Zielverzeichnis für Artefakte (`.gewebe/`)
- `embedder.provider`: z. B. `ollama` (lokal) oder `openai` (remote)
- `index.top_k`: Anzahl Rückgabekandidaten pro Suche
- `graph.cutoffs`: Grenzwerte für Kantenbildung
- `related.write_back`: Related-Blöcke in MD-Dateien aktualisieren (true/false)

## Beispiel-Workflow

```bash
cp examples/semantah.example.yml semantah.yml
make venv        # oder: uv sync
make all         # embeddings → index → graph → related
cargo run -p indexd
```

## Troubleshooting (kurz)
- **Leere Notizen / Binärdateien** → werden übersprungen, Logs prüfen (`.gewebe/logs`)
- **Keine Embeddings** → Provider/Key prüfen, Netz oder lokales Modell
- **Langsame Läufe** → `index.top_k` reduzieren, Batch-Größen erhöhen, nur geänderte Dateien pro Lauf verarbeiten

## FAQ
- **Wie starte ich ohne Obsidian?** → Einfach einen Ordner mit Markdown-Dateien nutzen.
- **Kann ich Remote-LLMs verwenden?**  
  Ja, setze `embedder.provider` auf `openai` und hinterlege deinen Key via Env-Var `OPENAI_API_KEY`.  
  Beispiel-Konfiguration:
  ```yaml
  embedder:
    provider: openai
- **Wie baue ich nur den Graphen neu?** → `make graph` nach vorhandenem `.gewebe/embeddings.parquet`.

## WGX-Integration (Stub)
Siehe `docs/wgx-konzept.md` und `.wgx/profile.yml`. Ziel: reproduzierbare Orchestrierung (devcontainer/Devbox/mise/direnv bevorzugt).
