# semantAH

[![CI](https://github.com/heimgewebe/semantAH/actions/workflows/ci.yml/badge.svg)](https://github.com/heimgewebe/semantAH/actions/workflows/ci.yml)
[![codecov](https://img.shields.io/codecov/c/github/heimgewebe/semantAH/main?style=flat-square)](https://codecov.io/gh/heimgewebe/semantAH)

> Automatisierte Coverage- und Testintegration:
> Der Badge aktualisiert sich nach jedem Merge-Job (Codecov Upload). Mindest-Thresholds siehe `codecov.yml`; Uploads sind nur aktiv, wenn `CODECOV_UPLOAD=true` gesetzt ist.

**semantAH** ist der semantische Index- und Graph-Ableger von [HausKI](https://github.com/heimgewebe/hausKI).
Es zerlegt Notizen (z. B. aus Obsidian), erstellt **Embeddings**, baut daraus einen **Index und Wissensgraphen** und schreibt „Related“-Blöcke direkt in die Markdown-Dateien zurück.

- **Einbettung in HausKI:** dient dort als semantische Gedächtnis-Schicht (Memory Layer).
- **Eigenständig nutzbar:** Skript-Pipeline (`tools/`, `Makefile`) oder Rust-Dienst (`/index/*`).
- **Artefakte:** `.gewebe/embeddings.parquet`, `nodes.jsonl`, `edges.jsonl`, Reports.
- **KPIs:** Index-Suche top-k=20 in < 60 ms (p95).
- **Integrationen:** Obsidian Canvas (Auto-Links), systemd-Timer, WGX-Recipes.

Mehr zur Integration: [docs/hauski.md](docs/hauski.md). Ergänzend:
- Embeddings: siehe [`docs/embeddings.md`](docs/embeddings.md)
- Namespaces: siehe [`docs/namespaces.md`](docs/namespaces.md)

SemantAH ist eine lokal laufende Wissensgraph- und Semantik-Pipeline für Obsidian-Vaults. Das Projekt adaptiert die Blaupausen aus `semantAH.md` und `semantAH brainstorm.md` und zielt darauf ab, eine modulare, reproduzierbare Infrastruktur aufzubauen:

- **Rust Workspace** mit eigenständigen Crates für Embeddings-Provider (`embeddings`) und Vektorindex/HTTP-Service (`indexd`).
- **Python-Tooling** zum Erzeugen von Embeddings, Graph-Knoten/Kanten und automatischen Related-Blöcken in Markdown-Notizen (siehe `tools/`).
- **Konfigurierbare Policies** (Cutoffs, Boosts, Safe Mode) sowie Persistenz in `.gewebe/`.
- **Automatisierung** via Makefile, `wgx`-Recipes und optional systemd-Timer.

> ⚠️ Dies ist ein Initialzustand. Viele Komponenten sind noch Platzhalter, damit der Code schrittweise erweitert werden kann. Die README dokumentiert den Aufbau, die Verzeichnisse und nächsten Arbeitsschritte.
> Eine Übersicht zu Config, API und Betrieb findest du ergänzend in:
> - [`docs/config-reference.md`](docs/config-reference.md)
> - [`docs/indexd-api.md`](docs/indexd-api.md)
> - [`docs/runbook.observability.md`](docs/runbook.observability.md)
> - [`docs/runbooks/semantics-intake.md`](docs/runbooks/semantics-intake.md)

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
│   ├── config-reference.md # Parametertabelle für semantah.yml
│   ├── indexd-api.md    # HTTP-Referenz für den Rust-Dienst
│   └── roadmap.md       # Umsetzungsschritte & Fortschritt
├── tools/
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
   - `make push-index` (schiebt vorhandene Embeddings zu indexd)
   - `make demo` (Mini-Demo auf Basis der Example-Konfig)
5. **Chronik-Insights exportieren (read-only)**
   - `uv run cli/ingest_chronik.py chronik/data/aussen.jsonl`
   - Ergebnis: `vault/.gewebe/insights/today.json` (≤ 10 KB)
   - Validierung: `npx -y ajv-cli@5 validate -s contracts/insights.schema.json -d vault/.gewebe/insights/today.json`
   - Shortcut: `make insights-today`
6. **Service testen**
   - `cargo run -p indexd`

7. **Observatory Report (MVP)**
   - `python scripts/observatory_mvp.py`
   - Erzeugt JSON-Report in `data/observatory/` (Schema: metarepo `observatory.report.schema.json`)

### Tests & Coverage (Python)

Lokal kannst du die Test-Extras mit `uv` aktivieren:

```bash
uv sync -E test
uv run pytest
```

Oder bequem per `make`:

```bash
# Unit-Tests (ohne @integration)
make test
# Coverage-Report unter ./reports/
make coverage
# Integration-Tests (mit @integration)
make test-integration
```

> ℹ️ Setze `HYPOTHESIS_PROFILE=ci`, um lokal das deterministische Hypothesis-Profil der CI zu nutzen.

Rust-Shortcuts:

```bash
# Tests (alle Crates)
make test-rust

# Lint (Clippy, bricht bei Warnungen ab)
make lint-rust

# Coverage (cargo llvm-cov; erzeugt LCOV bzw. HTML)
make cov-rust         # -> reports/rust-lcov.info
make cov-rust-html    # -> reports/llvm-cov/index.html
```

### Beispiele: Index & Suche

Upsert

```bash
curl -sS localhost:8080/index/upsert \
  -H 'content-type: application/json' \
  -d '{
    "doc_id":"note-1",
    "namespace":"vault",
    "chunks":[{"id":"c1","text":"Hello world","meta":{"embedding":[0.1,0.2,0.3],"snippet":"Hello world"}}]
  }'
```

Search (berechnet Embedding optional serverseitig)

```bash
curl -sS localhost:8080/index/search \
  -H 'content-type: application/json' \
  -d '{
    "query":{
      "text":"hello",
      "meta":{
        "embedding":[0.1,0.2,0.3]
      }
    },
    "k":5,
    "namespace":"vault"
  }'

# Legacy-Unterstützung:
# Alternativ darf `embedding` auf Top-Level oder (rückwärtskompatibel)
# im Top-Level `meta.embedding` stehen. Falls mehrere vorhanden sind, gewinnt
# der Wert aus `query.meta.embedding`.
# Embeddings werden als Liste von Floats (`f32`) erwartet.
#
# Server-seitige Embeddings:
# Setze `INDEXD_EMBEDDER_PROVIDER=ollama` (optional: `INDEXD_EMBEDDER_MODEL`,
# `INDEXD_EMBEDDER_BASE_URL`, `INDEXD_EMBEDDER_DIM`). Ohne explizites
# Embedding im Request wird der Query-Text dann über den hinterlegten Provider
# eingebettet.
```

### Persistenz (optional)

indexd kann den In-Memory-Index als JSONL persistieren:

```bash
export INDEXD_DB_PATH=".gewebe/indexd/store.jsonl"
cargo run -p indexd
```

## Export

- Contracts: `contracts/semantics/*.schema.json`, `contracts/insights.schema.json`
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

Eine minimale Beispiel-Konfiguration findest du in `examples/semantah.example.yml`. Die Datei ist aktuell ein **Platzhalter** – die angebundenen Skripte und Dienste nutzen die Konfiguration noch nicht, sondern arbeiten mit fest kodierten Pfaden und Standardwerten.

Alle Felder sowie ihren Status (aktiv vs. geplant) beschreibt [docs/config-reference.md](docs/config-reference.md).

## Beispiel-Workflow

```bash
cp examples/semantah.example.yml semantah.yml
make venv        # oder: uv sync
make all         # embeddings → index → graph → related (Stub-Skripte)
cargo run -p indexd
```

Der Dienst dokumentiert seine Routen in [docs/indexd-api.md](docs/indexd-api.md); die Python-Schritte sind in `tools/` beschrieben.

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

## Organismus-Kontext

Dieses Repository ist Teil des **Heimgewebe-Organismus**.

Die übergeordnete Architektur, Achsen, Rollen und Contracts sind zentral beschrieben im  
👉 [`metarepo/docs/heimgewebe-organismus.md`](https://github.com/heimgewebe/metarepo/blob/main/docs/heimgewebe-organismus.md)  
sowie im Zielbild  
👉 [`metarepo/docs/heimgewebe-zielbild.md`](https://github.com/heimgewebe/metarepo/blob/main/docs/heimgewebe-zielbild.md).

Alle Rollen-Definitionen, Datenflüsse und Contract-Zuordnungen dieses Repos
sind dort verankert.
