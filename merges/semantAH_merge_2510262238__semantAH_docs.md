### 📄 semantAH/docs/blueprint.md

**Größe:** 11 KB | **md5:** `b1fa5ee0047bbe711860d0848e1be72d`

```markdown
# Vault-Gewebe: Finale Blaupause

Diese Datei fasst die komplette Architektur für das semantische Vault-Gewebe zusammen. Sie kombiniert den semantischen Index, den Wissensgraphen, Obsidian-Automatismen sowie Qualitäts- und Review-Schleifen. Alle Schritte sind lokal reproduzierbar und werden in `.gewebe/` versioniert.

---

## 0. Systemordner & Konventionen

```
.gewebe/
  config.yml           # Parameter (Modelle, Cutoffs, Policies)
  embeddings.parquet   # Chunks + Vektoren
  nodes.jsonl          # Graph-Knoten
  edges.jsonl          # Graph-Kanten
  clusters.json        # Cluster & Label
  taxonomy/
    synonyms.yml
    entities.yml
  reports/
    semnet-YYYYMMDD.md
  meta.json            # Provenienz (Modell, Parameter, Hashes)
```

**Frontmatter pro Datei**

```yaml
id: 2025-VAULT-####   # stabiler Schlüssel
title: ...
topics: [HausKI, Weltgewebe]
persons: [Verena]
places: [Hamburg]
projects: [wgx, hauski]
aliases: [HK, WG]
relations_lock: false
```

---

## 1. Indexing & Embeddings

- Crawler: iteriert Markdown & Canvas (ignoriert `.gewebe/`, `.obsidian/`).
- Chunking: 200–300 Tokens, Overlap 40–60, Paragraph/Block.
- Modelle: `all-MiniLM-L6-v2` oder `intfloat/e5-base` (GPU-fähig via PyTorch/CUDA).
- Output: `embeddings.parquet` (id, path, chunk_id, text, embedding).

---

## 2. Schlagwort- & Entitätsextraktion

- Keyphrase: YAKE/RAKE lokal → optional mit LLM verfeinern.
- NER: spaCy DE-Modell → Personen, Orte, Projekte.
- Taxonomie in `.gewebe/taxonomy/synonyms.yml`:

```yaml
topics:
  hauski: [haus-ki, hk]
persons:
  verena: [v.]
```

- Normalisierung: Tokens bei Indexlauf auf Normformen mappen → ins Frontmatter schreiben.

---

## 3. Clusterbildung

- Verfahren: HDBSCAN (robust) + UMAP (2D-Projektion für Visualisierung).
- Ergebnis: `clusters.json` mit IDs, Label, Mitgliedern und Zentroiden.
- Orphan Detection: Notizen ohne Cluster → separate Liste.

---

## 4. Semantischer Wissensgraph

**Nodes (`nodes.jsonl`)**

```json
{"id":"md:gfk.md","type":"file","title":"GFK","topics":["gfk"],"cluster":7}
{"id":"topic:Gewaltfreie Kommunikation","type":"topic"}
{"id":"person:Verena","type":"person"}
```

**Edges (`edges.jsonl`)**

```json
{"src":"md:gfk.md","rel":"about","dst":"topic:Gewaltfreie Kommunikation","weight":0.92,"why":["shared:keyphrase:GFK","same:cluster"]}
{"src":"md:verena.md","rel":"similar","dst":"md:tatjana.md","weight":0.81,"why":["cluster:7","quote:'…'"]}
```

Das Feld `why` speichert die Top-Rationales (Keyphrases, Cluster, Anker-Sätze) und ermöglicht Explainability.

---

## 5. Verlinkung in Obsidian

- Related-Blöcke (idempotent, autogeneriert):

```
<!-- related:auto:start -->
## Related
- [[Tatjana]] — (0.81; Cluster 7, GFK)
- [[Lebenslagen]] — (0.78; Resonanz)
<!-- related:auto:end -->
```

- MOCs (`_moc/topic.md`): Beschreibung, Dataview-Tabelle (`topics:topic`), Mini-Canvas-Link.
- Canvas-Integration: Knoten = Notizen/Topics/Persons, Kanten = Similar/About/Mentions, Legende-Knoten nach Canvas-Richtlinie.

---

## 6. Automatisierung

- `wgx`-Recipes:

```yaml
index:
    python3 tools/build_index.py
graph:
    python3 tools/build_graph.py
related:
    python3 tools/update_related.py
all: index graph related
```

- systemd `--user` Timer oder cron: nightly `make all`.
- Git-Hook (pre-commit): delta-Index → Related aktualisieren.

---

## 7. Qualitative Validierung

- Reports (`reports/semnet-YYYYMMDD.md`): neue Kanten < 0.75 („Review required“), Orphans, Cluster > N Notizen ohne MOC.
- Review-Workflow: `accepted_edges` / `rejected_edges` im Frontmatter; Skripte ignorieren `rejected` → Feedback fließt zurück.

---

## 8. Policies & Score-Regeln

```
score = cosine + boosts
+0.05 wenn gleicher Cluster
+0.03 je shared keyphrase (max +0.09)
+0.04 wenn Canvas-Hop ≤ 2
+0.02 wenn Datei jung (<30 Tage)
```

Autolink-Gate:

- Score ≥ 0.82 **und** (≥ 2 Keyphrases **oder** Canvas-Hop ≤ 2 **oder** shared Project).
- Cutoffs: ≥ 0.82 Auto-Link, 0.70–0.81 Vorschlag, < 0.70 ignorieren.

---

## 9. Erweiterungen (Kernideen)

- Duplicates Report: Cosine ≥ 0.97 → Merge-Vorschlag.
- Topic Drift: Clusterwechsel flaggen.
- Session-Boost: aktuell bearbeitete Dateien → Score +0.02.
- Explain Command: Popover „Warum ist dieser Link da?“ (zeigt `why`-Feld).
- Locks: `relations_lock: true` → keine Auto-Edits.
- A/B-Cutoffs: zwei Profile testen, Review-Feedback einspeisen.

---

## 10. Provenienz & Reproduzierbarkeit

`.gewebe/meta.json` speichert:

```json
{
  "model": "all-MiniLM-L6-v2",
  "chunk_size": 200,
  "cutoffs": {"auto": 0.82, "suggest": 0.70},
  "run": "2025-10-02T11:40",
  "commit": "abc123"
}
```

---

## 11. Technische Bausteine

### Tools / Skripte

- `tools/build_index.py`: Scan + Embeddings.
- `tools/build_graph.py`: Nodes/Edges/Cluster.
- `tools/update_related.py`: Related-Blöcke injizieren.
- `tools/report.py`: QA-Reports.
- optional `tools/canvas_export.py`: Cluster → Canvas.

### Dreistufiger Zyklus

1. Index (Embeddings, Cluster, Taxonomie).
2. Graph (Nodes/Edges mit Rationales).
3. Update (Related, MOCs, Reports, Canvas).

---

## 12. Minimal lauffähige Suite

Eine robuste, offline-fähige Minimalversion liefert unmittelbar Embeddings, Similarities, Graph (Nodes/Edges), Related-Blöcke und Reports.

### Dateibaum

```
<Vault-Root>/
  .gewebe/
    config.yml
    taxonomy/
      synonyms.yml
      entities.yml
    reports/
  tools/
    build_index.py
    build_graph.py
    update_related.py
  Makefile
```

### Python-Abhängigkeiten

```
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install pandas numpy pyarrow pyyaml \
  sentence_transformers scikit-learn networkx rich
```

Standardmodell: `sentence-transformers/all-MiniLM-L6-v2`. GPU nutzt Torch automatisch, falls vorhanden.

### `.gewebe/config.yml`

```yaml
model: sentence-transformers/all-MiniLM-L6-v2
chunk:
  target_chars: 1200
  min_chars: 300
  overlap_chars: 200
paths:
  exclude_dirs: [".gewebe", ".obsidian", "_site", "node_modules"]
  include_ext: [".md"]
related:
  k: 8
  auto_cutoff: 0.82
  suggest_cutoff: 0.70
boosts:
  same_topic: 0.03
  same_project: 0.03
  recent_days: 30
  recent_bonus: 0.02
  same_folder: 0.02
render:
  related_heading: "## Related"
  markers:
    start: "<!-- related:auto:start -->"
    end:   "<!-- related:auto:end -->"
```

### Skripte (`tools/*.py`)

Die Skripte implementieren:

- Markdown-Scan, Frontmatter-Parsing und Chunking.
- Embedding-Berechnung mit SentenceTransformers.
- Vektorzentroide pro Datei + Cosine-Similarity.
- Score-Boosts basierend auf Topics, Projekten, Ordnern, Recency.
- Schreiben von `nodes.jsonl`, `edges.jsonl` und Reports.
- Injection idempotenter Related-Blöcke in Markdown.

(Vollständige Implementierungen befinden sich in `tools/` im Repo und sind auf GPU/CPU lauffähig.)

### Makefile

```
VENV=.venv
PY=$(VENV)/bin/python

.PHONY: venv index graph related all clean

venv: $(VENV)/.deps_installed

$(VENV)/.deps_installed: 
	@test -d $(VENV) || python3 -m venv $(VENV)
	@$(PY) -m pip install --upgrade pip
	@$(PY) -m pip install pandas numpy pyarrow pyyaml sentence_transformers scikit-learn networkx rich
	@touch $(VENV)/.deps_installed
index: venv
@$(PY) tools/build_index.py

graph: venv
@$(PY) tools/build_graph.py

related: venv
@$(PY) tools/update_related.py

all: index graph related

clean:
@rm -f .gewebe/embeddings.parquet
@rm -f .gewebe/nodes.jsonl .gewebe/edges.jsonl
```

### systemd (User) Timer

`~/.config/systemd/user/vault-gewebe.service`

```
[Unit]
Description=Vault-Gewebe nightly build (index -> graph -> related)
After=default.target

[Service]
Type=oneshot
WorkingDirectory=%h/path/to/your/vault
ExecStart=make all
```

`~/.config/systemd/user/vault-gewebe.timer`

```
[Unit]
Description=Run Vault-Gewebe every night

[Timer]
OnCalendar=*-*-* 03:10:00
Persistent=true

[Install]
WantedBy=timers.target
```

Aktivieren:

```
systemctl --user daemon-reload
systemctl --user enable --now vault-gewebe.timer
systemctl --user list-timers | grep vault-gewebe
```

### Erstlauf

```
make venv
make all
```

Ergebnisdateien liegen unter `.gewebe/…`. In Obsidian erscheint der Related-Block am Ende der Note.

---

## 13. HausKI-Integration (Überblick)

Für HausKI entsteht ein neuer Dienstverbund:

1. `crates/embeddings`: Embedder-Trait + Provider (lokal via Ollama, optional Cloud über AllowlistedClient und Safe-Mode-Policies).
2. `crates/indexd`: HTTP-Service (`/index/upsert`, `/index/search`, `/index/delete`), HNSW-Vektorindex, Persistenz (`~/.local/state/hauski/index/obsidian`).
3. Obsidian-Plugin (Thin Client): chunked Upserts & Searches über HausKI-Gateway.
4. Config-Erweiterung (`configs/hauski.yml`): Index-Pfad, Embedder-Optionen, Namespace-Policies.

Siehe `docs/hauski.md` für eine ausführliche Einbindung.

---

## 14. Erweiterte Qualitäts- & Komfortfeatures

1. **Begründete Kanten** – `edges.jsonl` enthält `why`-Feld mit Keyphrases, Cluster, Quotes.
2. **Near-Duplicate-Erkennung** – Cosine ≥ 0.97 → Merge-Report, Canonical-Markierung.
3. **Zeit-Boost** – +0.05 für Notizen < 30 Tage, Decay für ältere Inhalte.
4. **Ordner-/Namespace-Policies** – z. B. `/archive/` nur eingehende Links, `/ideen/` liberalere Cutoffs.
5. **Feedback-Lernen** – `accepted_edges`/`rejected_edges` beeinflussen Cutoffs.
6. **Canvas-Hop-Boost** – Pfadlänge ≤ 2 innerhalb von Canvas erhöht Score um 0.03–0.07.
7. **Topic-Drift-Wächter** – signalisiert Clusterwechsel.
8. **Explainable Related-Blöcke** – Scores & Top-Begründungen in Markdown.
9. **Session-Kontext** – aktuell geöffnete Dateien geben +0.02 Boost.
10. **Provenienz** – `meta.json` mit Modell, Chunking, Cutoffs, Hashes.
11. **Mehrsprach-Robustheit** – Synonym-/Stemming-Maps für DE/EN.
12. **Autolink-Quality-Gate** – Score ≥ 0.82 + (≥2 Keyphrases oder Canvas-Hop ≤ 2 oder shared Project).
13. **Explain-this-link Command** – Popover mit Rationales im Obsidian-Plugin.
14. **MOC-Qualitätsreport** – Deckungsgrade, verwaiste Knoten, Unter-MOC-Vorschläge.
15. **Transklusions-Vorschläge** – Absatzweise `![[note#^block]]` bei hoher Chunk-Ähnlichkeit.
16. **Manual Lock** – `relations_lock: true` verhindert Auto-Edits.
17. **A/B-Tuning** – zwei Cutoff-Profile testen, Feedback auswerten.
18. **Cross-Vault-Brücke** – Read-Only Namespace `ext:*` für externe Vaults.
19. **Orphans-First-Routine** – wöchentliche Fokussierung auf unverlinkte Notizen.
20. **Explainable Deletes** – Reports dokumentieren entfernte Kanten mit Ursache.

---

## 15. Unsicherheiten & Anpassbarkeit

- Schwellenwerte & Chunking müssen empirisch justiert werden.
- Canvas-Hop-Berechnungen hängen vom JSON-Layout ab.
- Modellwahl beeinflusst Qualität und Performance.
- Die Pipeline ist modular, Reports + Feedback-Loops ermöglichen schnelle Iteration.

---

## 16. Verdichtete Essenz

- Drei Skripte, ein Makefile, ein Timer → Index → Graph → Related.
- HausKI liefert den skalierbaren Dienst (`indexd`) + Obsidian-Adapter.
- Qualität durch erklärbare Kanten, Review-Workflow, Reports, Policies.
- Lokal, reproduzierbar, versionierbar – dein Vault wird zum lebenden Semantiknetz.

---

> *Ironische Auslassung:* Deine Notizen sind jetzt kein stilles Archiv mehr – sie bilden ein Klatsch-Netzwerk, das genau protokolliert, wer mit wem was zu tun hat. Nur: Sie lügen nicht.
```

### 📄 semantAH/docs/hauski.md

**Größe:** 5 KB | **md5:** `9b9d21594d5468bdaea32737a8f4b7f5`

```markdown
# HausKI-Integration

HausKI bleibt das lokale Orchestrierungs-Gateway. semantAH ergänzt es als semantische Gedächtnis-Schicht. Dieser Leitfaden beschreibt, wie die neuen Komponenten (`indexd`, `embeddings`, Obsidian-Adapter) eingebunden werden und welche Policies greifen.

---

## Architekturüberblick

1. **`crates/embeddings`** – stellt den `Embedder`-Trait bereit und kapselt Provider:
   - `Ollama` (lokal, offline) ruft `http://127.0.0.1:11434/api/embeddings` auf.
   - `CloudEmbedder` (optional) nutzt HausKIs AllowlistedClient. Aktiv nur, wenn `safe_mode=false` und der Zielhost in der Egress-Policy freigeschaltet ist.
2. **`crates/indexd`** – HTTP-Service mit Routen:
   - `POST /index/upsert` – nimmt Chunks + Metadaten entgegen und legt Vektoren im HNSW-Index ab.
   - `POST /index/delete` – entfernt Dokumente aus einem Namespace.
   - `POST /index/search` – Top-k-Suche mit Filtern (Tags, Projekte, Pfade).
   - Persistenz liegt unter `~/.local/state/hauski/index/<namespace>/`.
3. **Obsidian-Adapter (Thin Plugin)** – zerlegt Notizen und Canvas-Dateien, sendet Upserts an HausKI und ruft Suchergebnisse für „Related“/Command-Paletten ab.
4. **Policies & Observability** – bestehende Features (CORS, `/health`, `/metrics`, `safe_mode`, Latency-Budgets) gelten auch für `/index/*`.

---

## Workspace-Konfiguration

`Cargo.toml` (Workspace):

```toml
[workspace]
members = [
  "crates/core",
  "crates/cli",
  "crates/indexd",
  "crates/embeddings"
]
```

`crates/embeddings/src/lib.rs` definiert den Trait und z. B. `Ollama`:

```rust
#[async_trait::async_trait]
pub trait Embedder {
    async fn embed(&self, texts: &[String]) -> anyhow::Result<Vec<Vec<f32>>>;
    fn dim(&self) -> usize;
    fn id(&self) -> &'static str;
}
```

Implementierungen greifen auf `reqwest::Client` zurück. Cloud-Varianten müssen über HausKIs AllowlistedClient laufen, um Egress-Guards einzuhalten.

`crates/indexd` kapselt Embedder + Vektorstore (HNSW + Metadata-KV, z. B. `sled`). Der Router wird in `core::plugin_routes()` unter `/index` gemountet:

```rust
fn plugin_routes() -> Router<AppState> {
    let embedder = embeddings::Ollama::new("http://127.0.0.1:11434", "nomic-embed-text", 768);
    let store = indexd::store::hnsw(/* state_path */);
    Router::new().nest("/index", indexd::Indexd::new(embedder, store).router())
}
```

---

## HTTP-API

### Upsert

```http
POST /index/upsert
{
  "namespace": "obsidian",
  "doc_id": "notes/gfk.md",
  "chunks": [
    {"id": "notes/gfk.md#0", "text": "...", "meta": {"topics": ["gfk"], "frontmatter": {...}}}
  ]
}
```

### Delete

```http
POST /index/delete
{"namespace": "obsidian", "doc_id": "notes/gfk.md"}
```

### Search

```http
POST /index/search
{
  "namespace": "obsidian",
  "query": "empatische Kommunikation",
  "k": 10,
  "filters": {"topics": ["gfk"], "projects": ["wgx"]}
}
```

Antwort: Treffer mit Score, Dokument/Chunk-ID, Snippet, Rationales (`why`).

---

## Persistenz & Budgets

- Indexdaten leben im `index.path` aus der HausKI-Config (`~/.local/state/hauski/index`).
- HNSW-Index + Sled/SQLite halten Embeddings und Metadaten.
- Latency-Budgets: `limits.latency.index_topk20_ms` (Config) definiert das p95-Ziel. K6-Smoke nutzt diesen Wert als Assertion.
- Prometheus-Metriken für `/index/*` werden automatisch vom Core erfasst (`http_requests_total`, `http_request_duration_seconds`).

---

## Konfiguration (`configs/hauski.yml`)

```yaml
index:
  path: "$HOME/.local/state/hauski/index"
  provider:
    embedder: "ollama"
    model: "nomic-embed-text"
    url: "http://127.0.0.1:11434"
    dim: 768
  namespaces:
    obsidian:
      auto_cutoff: 0.82
      suggest_cutoff: 0.70
      policies:
        allow_autolink: true
        folder_overrides:
          archive:
            mode: incoming-only
plugins:
  enabled:
    - obsidian_index
```

`safe_mode: true` sperrt Cloud-Provider automatisch. Namespaces können weitere Regeln (z. B. strengere Cutoffs) erhalten.

---

## Obsidian-Plugin (Adapter)

- Hook auf `onSave` / `metadataCache.on("changed")`.
- Chunking (200–300 Tokens, 40 Overlap), Canvas-JSON-Knoten werden zusätzliche Chunks.
- Sendet `POST /index/upsert` mit Frontmatter/Tags/Canvas-Beziehungen im `meta`-Feld.
- Command „Semantisch ähnliche Notizen“ → `POST /index/search` und Anzeige der Ergebnisse.
- Optionaler Review-Dialog für Vorschläge (Accept/Reject → Frontmatter `accepted_edges` / `rejected_edges`).

---

## Automatisierung & Tests

- `wgx run index:obsidian` ruft der Reihe nach `build_index`, `build_graph`, `update_related` auf.
- systemd-Timer führt `make all` nightly aus (siehe `docs/blueprint.md`).
- CI/K6: Smoke-Test gegen `/index/search` mit Query-Stubs → prüft p95 < `limits.latency.index_topk20_ms`.

---

## Mehrwert

- Saubere Zuständigkeiten (UI vs. Dienste).
- Egress-kontrollierte Einbindung externer Provider.
- Explainable Scores via `why`-Feld.
- Reports & Policies sorgen für qualitätsgesicherte Auto-Links.

> *Ironische Auslassung:* HausKI bleibt der Türsteher – aber semantAH entscheidet, wer auf die VIP-Liste der Notizen kommt.
```

### 📄 semantAH/docs/quickstart.md

**Größe:** 730 B | **md5:** `ee8d08856e82b12a3beec126165fb263`

```markdown
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

## Artefakte
- `.gewebe/embeddings.parquet`
- `.gewebe/out/{nodes.jsonl,edges.jsonl,reports.json}`

## Troubleshooting
- Leere/zu große Dateien werden übersprungen → Logs in `.gewebe/logs` prüfen.
- Bei fehlenden Modellen: Provider in `semantah.yml` anpassen.
```

### 📄 semantAH/docs/roadmap.md

**Größe:** 1 KB | **md5:** `24f4c6253a1f9e1855df22c940921405`

```markdown
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
```

### 📄 semantAH/docs/runbook.observability.md

**Größe:** 545 B | **md5:** `abc6d168fcb5c65c139b2ae9e2d21714`

```markdown
# Observability Runbook

## Overview

This runbook describes how to access the local observability stack while developing semantAH. The stack is composed of Grafana, Loki, and Tempo containers that expose HTTP interfaces for debugging and tracing.

## Endpoints

- Grafana: [http://localhost:3000](http://localhost:3000)
- Loki: [http://localhost:3100](http://localhost:3100)
- Tempo: [http://localhost:3200](http://localhost:3200)

Use these endpoints to inspect logs, metrics, and traces when diagnosing issues in the development environment.
```

### 📄 semantAH/docs/semantAH brainstorm.md

**Größe:** 24 KB | **md5:** `ef898078966a53c4cf0cca26de1d0bb0`

```markdown
mega–ja. wir bauen das selbst – aber so, dass es perfekt in dein repo passt. hier ist der konkrete blueprint für “semantische suche / vektor-index” als hauski-dienst + dünnes obsidian-plugin-frontend.

(ich beziehe mich dabei auf deine repo-struktur, configs und bereits vorhandene core-server-grundlagen wie /health, /metrics, CORS, „safe_mode“, egress-guard usw. – die sehen schon sehr solide aus.  ￼)

zielbild (kompakt)
	•	hauski-core bleibt HTTP-Gateway/Telemetry.
	•	neuer crate indexd: Embeddings + Vektorindex (HNSW) + Persistenz + Filter.
	•	neuer crate embeddings: Abstraktion für Provider (lokal via Ollama/gguf, optional cloud – respektiert egress-Policy).
	•	adapter: obsidian-plugin (thin client): sendet Chunks/Updates an indexd, ruft search ab.
	•	policies & flags: such-latenz-budget an Limits koppeln; safe_mode blockt Cloud-Provider.

⸻

was ist schon da (und wie nutzen wir’s)?
	•	Core-HTTP, Metrics, CORS, Ready/Health – fertiges Gerüst für neue Routen.  ￼
	•	Feature-Flags & Policies inkl. safe_mode und Egress-Allowlisting → perfekt, um Cloud-Embeddings sauber zu sperren/erlauben.  ￼
	•	Configs: configs/hauski.yml hat vault_path & plugins-liste – hier hängen wir obsidian_index offiziell an und tragen indexd ein.  ￼

⸻

module & schnittstellen

1) crate: crates/indexd/

Aufgaben
	•	Dokumente in Chunks zerlegen (MD + Canvas JSON).
	•	Embeddings berechnen (ruft embeddings-crate).
	•	Vektoren in HNSW speichern (z. B. hnsw_rs oder hnswlib-binding) + Metadata-Store (z. B. sled/sqlite).
	•	Top-K Suche + Filter (Pfad, Tags, Frontmatter, Canvas-Knoten).
	•	Persistenz auf Disk ($HOME/.local/state/hauski/index/obsidian).

HTTP-API (einfach, stabil):
	•	POST /index/upsert
body:

{ "doc_id":"path/to/note.md",
  "chunks":[{"id":"path:offset", "text":"...", "meta":{"tags":["..."],"frontmatter":{}}}],
  "namespace":"obsidian" }


	•	POST /index/delete → {"doc_id":"...","namespace":"obsidian"}
	•	POST /index/search

{ "query":"...", "k":10, "namespace":"obsidian", "filters":{"tags":["projectX"]} }

response: Treffer mit score, doc_id, chunk_id, snippet.

Leistung & Budgets
	•	p95-Ziel für search(k<=20) an limits.latency.index_topk20_ms koppeln (Config hast du schon).  ￼

2) crate: crates/embeddings/

Ziel: austauschbarer Provider mit egress-Guard & safe_mode.
	•	Trait:

#[async_trait::async_trait]
pub trait Embedder {
    async fn embed(&self, texts: &[String]) -> anyhow::Result<Vec<Vec<f32>>>;
    fn dim(&self) -> usize;
    fn id(&self) -> &'static str;
}


	•	LocalOllamaEmbedder (default, offline): ruft http://127.0.0.1:11434/api/embeddings (modell konfigurierbar: nomic-embed-text o. ä.).
	•	CloudEmbedder (optional): nur wenn safe_mode=false und egress-Policy Host erlaubt. Nutzt vorhandenen AllowlistedClient (ist schon implementiert, wir müssen nur Aufrufe darüber routen).  ￼

3) core-routes erweitern

In hauski-core gibt’s TODO-Platzhalter plugin_routes() – hier mounten wir indexd-Router unter /index. CORS & Metrics sind schon verdrahtet.  ￼

⸻

minimaler code–fahrplan

A) workspace ergänzen

Cargo.toml (root) – neue Mitglieder:

[workspace]
members = [
  "crates/core",
  "crates/cli",
  "crates/indexd",        # NEU
  "crates/embeddings"     # NEU
]

(du hast das Pattern bereits offen für weitere crates – siehe Kommentar im bestehenden Cargo.toml.)  ￼

B) crates/embeddings/src/lib.rs (skizze)

use anyhow::Result;
use reqwest::Client;

#[async_trait::async_trait]
pub trait Embedder {
    async fn embed(&self, texts: &[String]) -> Result<Vec<Vec<f32>>>;
    fn dim(&self) -> usize;
    fn id(&self) -> &'static str;
}

pub struct Ollama {
    http: Client,
    url: String,
    model: String,
    dim: usize,
}

#[async_trait::async_trait]
impl Embedder for Ollama {
    async fn embed(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        #[derive(serde::Serialize)] struct Req<'a>{ model:&'a str, input:&'a [String] }
        #[derive(serde::Deserialize)] struct Res{ embeddings: Vec<Vec<f32>> }
        let res: Res = self.http.post(format!("{}/api/embeddings", self.url))
            .json(&Req{model:&self.model, input:texts})
            .send().await?
            .error_for_status()?
            .json().await?;
        Ok(res.embeddings)
    }
    fn dim(&self) -> usize { self.dim }
    fn id(&self) -> &'static str { "ollama" }
}

cloud-variante baut analog, aber über AllowlistedClient aus deinem core (egress-policy beachten).  ￼

C) crates/indexd/src/lib.rs (skizze)

use axum::{routing::post, Json, Router};
use serde::{Deserialize, Serialize};
use std::sync::Arc;

#[derive(Clone)]
pub struct Indexd {
    embedder: Arc<dyn embeddings::Embedder + Send + Sync>,
    store: Arc<dyn VectorStore + Send + Sync>,
}

#[derive(Deserialize)]
struct Upsert {
    namespace: String,
    doc_id: String,
    chunks: Vec<Chunk>,
}
#[derive(Deserialize, Serialize, Clone)]
struct Chunk { id: String, text: String, #[serde(default)] meta: serde_json::Value }

#[derive(Deserialize)]
struct Search { namespace: String, query: String, #[serde(default="k10")] k: usize }
fn k10()->usize{10}

impl Indexd {
    pub fn router(self) -> Router {
        Router::new()
          .route("/upsert", post(move |Json(b): Json<Upsert>| async move {
              let vecs = self.embedder.embed(&b.chunks.iter().map(|c| c.text.clone()).collect::<Vec<_>>()).await?;
              self.store.upsert(&b.namespace, &b.doc_id, &b.chunks, &vecs)?;
              Ok::<_,axum::http::StatusCode>(())
          }))
          .route("/search", post(move |Json(s): Json<Search>| async move {
              let qv = self.embedder.embed(&vec![s.query]).await?.remove(0);
              let hits = self.store.search(&s.namespace, &qv, s.k)?;
              Ok::<_,axum::http::StatusCode>(Json(hits))
          }))
    }
}

VectorStore implementieren mit HNSW (z. B. hnsw_rs) + Metadaten-KV (sled), persistiert in ~/.local/state/hauski/index/... – dein configs/hauski.yml sieht genau so einen state-pfad vor.  ￼

D) crates/core/src/lib.rs – Routen mounten

Im existierenden plugin_routes() den indexd-Router einhängen:

fn plugin_routes() -> Router<AppState> {
    // build indexd with chosen embedder (from config/flags)
    let embedder = embeddings::Ollama::new(/* url, model, dim */);
    let indexd = indexd::Indexd::new(embedder, /* store */);
    Router::new().nest("/index", indexd.router())
}

(Der Platzhalter ist eigens für Plugins vorgesehen.  ￼)

⸻

obsidian–adapter (dünnes plugin)

Wann? sobald du Notizen speicherst/änderst.
Was tut’s?
	•	Zerlegt die Note in Chunks (z. B. Absatzweise, Overlap 50-100 Tokens).
	•	Extrahiert Frontmatter / Tags / Canvas-Knoten.
	•	Schickt POST /index/upsert.
	•	„Ähnliche Notizen“ → POST /index/search und UI Ergebnisliste.

Mini-Skizze (TypeScript):

async function upsertNote(docId: string, text: string, meta: any) {
  const chunks = chunkText(text, {targetTokens: 200, overlap: 40});
  await fetch("http://127.0.0.1:8080/index/upsert", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ namespace:"obsidian", doc_id:docId, chunks: chunks.map((t,i)=>({id:`${docId}#${i}`, text:t, meta})) })
  });
}

async function searchSimilar(query: string, k=10) {
  const res = await fetch("http://127.0.0.1:8080/index/search", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ namespace:"obsidian", query, k })
  });
  return await res.json();
}

Warum eigener Adapter? So bleibt Obsidian-UI schlank; der „schwere Teil“ läuft in indexd.

⸻

canvas-bonus (für deine mindmaps)
	•	Canvas-Datei (JSON) parsen → jeden Node-Text als separaten Chunk, Kanten als meta:{link:"A->B"} speichern.
	•	Suche kann dann „Knotenähnlichkeit“ liefern und verlinkte Nachbarn höher gewichten (post-ranking auf Suchtreffern).

⸻

konfiguration

configs/hauski.yml erweitern:

index:
  path: "$HOME/.local/state/hauski/index"
  provider:
    embedder: "ollama"
    model: "nomic-embed-text"
    url: "http://127.0.0.1:11434"
plugins:
  enabled:
    - "obsidian_index"

(die Datei enthält bereits vault_path & plugin-liste – wir hängen unsere Optionen sauber daneben.)  ￼

Policies
	•	policies/limits.yaml: index_topk20_ms ist schon da → als Budget für p95 in k6-Smoke verwenden (du hast bereits eine k6-Smoke-Stage, die Limits aus YAML liest – super!).  ￼

⸻

tests & observability
	•	k6-Smoke trifft /index/search mit Query-Stubs → misst p95 gegen index_topk20_ms. Deine CI baut das Schema bereits auf (observability/k6/...).  ￼
	•	Prometheus: zähle Requests/Latency pro Pfad (/index/*) – dein Core hat bereits http_requests & http_request_duration_seconds, wird automatisch miterfasst.  ￼

⸻

rollout–schritte (hands-on)
	1.	Crates anlegen: crates/indexd, crates/embeddings + Workspace updaten.
	2.	Ollama lokal (Pop!_OS): curl -fsSL https://ollama.ai/install.sh | sh → ollama pull nomic-embed-text.
	3.	Core-Router: plugin_routes() → /index mounten.
	4.	Adapter bauen (Obsidian): einfache Commands „Index bauen“, „Ähnliches finden“.
	5.	Persistenz: HNSW + sled, Snapshot/Load on start.
	6.	CI: kleine k6-Smoke gegen /index/search integrieren (du hast die Pipeline schon).  ￼

⸻

warum das “besser” ist als copy/fork?
	•	saubere zuständigkeiten: UI (Obsidian) vs. Dienste (indexd/embeddings).
	•	portabilität: gleicher Index für VSCode-Plugin, CLI, Mail usw.
	•	kontrollierte egress-sicherheit: Cloud-Embeddings werden durch deine bestehende Policy sauber begrenzt.  ￼
	•	observability & budgets: p95-Ziele und Metriken sind first-class eingebaut.  ￼

⸻

wenn du möchtest, schreibe ich dir im nächsten schritt die genauen dateibäume + erste echte rust-dateien (inkl. deps für hnsw & sled) – direkt passend zu deinem workspace.

Kurz: Ja — die Ideen sind solide. Und wir können sie präzise in HausKI + Obsidian umsetzen, so dass dein vault-gewebe sich selbst vernetzt (semantisch + graphisch), ohne Cloud, sauber versionierbar.

Plan: von Idee → HausKI-Praxis

1) Bestandsaufnahme & Cluster
	•	Crawler (obsidian-adapter): liest .md + .canvas aus vault_path, extrahiert:
	•	Pfad, Titel, Frontmatter, Tags, Links ([[...]]), Canvas-Knoten/Kanten.
	•	Embeddings (indexd): Chunking (≈200–300 Tokens, 40 Overlap), embed(text[]) über Ollama (nomic-embed-text) oder Orchestrator-Modell.
	•	Clustering (jobs/indexd):
	•	HDBSCAN auf Vektoren (robust für „Rauschen“), optional UMAP zur 2D-Projektion für Visuals.
	•	Ergebnis: cluster_id pro Chunk/Note + „outlier“-Markierung.

Artefakte (Dateien/Tabellen):
	•	~/.local/state/hauski/index/obsidian/vec.hnsw (Vektorindex)
	•	graph/nodes.jsonl (pro Datei/Knoten)
	•	graph/edges.jsonl (Kanten, siehe §3)
	•	clusters.json (Cluster → Mitglieder, Centroid, Label)

2) Schlagwort- & Themenextraktion
	•	Keyphrases: lokal via YAKE/Rake (schnell, offline) + LLM-Refine (optional) → keyphrases: [ "Gewaltfreie Kommunikation", … ]
	•	NER (Person/Ort/Projekt): lokal (spaCy de-model) oder Regel-Set für Frontmatter/Tags.
	•	Normierung: Mapping-Tabelle synonyms.yml (z. B. „GFK“ → „Gewaltfreie Kommunikation“).

Speicher:

taxonomy/
  synonyms.yml     # "GFK": "Gewaltfreie Kommunikation"
  entities.yml     # "Personen": [...], "Orte": [...], "Projekte": [...]

3) Semantischer Wissensgraph
	•	Schema (leichtgewichtig, Git-freundlich):
	•	nodes.jsonl:

{"id":"md:weg/gfk.md","type":"file","title":"GFK Basics","tags":["gfk"],"cluster":7}
{"id":"canvas:lebenslagen.canvas","type":"canvas","title":"Lebenslagen","cluster":3}
{"id":"topic:Gewaltfreie Kommunikation","type":"topic"}


	•	edges.jsonl:

{"s":"md:weg/gfk.md","p":"about","o":"topic:Gewaltfreie Kommunikation","w":0.92}
{"s":"md:fall/verena.md","p":"similar","o":"md:tatjana.md","w":0.81}
{"s":"canvas:lebenslagen.canvas#node/4","p":"mentions","o":"topic:Kinderarmut","w":0.88}


	•	w = Gewicht/Score (0..1).

	•	Option Neo4j: nur wenn du interaktiv große Graph-Queries willst. Starten wir zunächst JSONL + SQLite (Tabellen nodes, edges) für Einfachheit & Portabilität.

4) Verlinkung in Obsidian
	•	Backlinks/MOCs automatisch schreiben:
	•	Am Ende jeder Datei Abschnitt ## Semantisch verwandt mit Top-N (similar ≥ 0.75, gleicher Cluster bevorzugt).
	•	MOC-Generator pro Cluster: MOC.cluster-07.md mit Liste + Mini-Canvas (siehe §Canvas).
	•	Frontmatter anreichern:

related:
  - file: pfad/zur/anderen.md
    score: 0.82
    why: ["shared:keyphrase:Gewaltfreie Kommunikation","same:cluster:7"]
topics: ["Gewaltfreie Kommunikation","Resonanz"]



5) Automatisierung
	•	wgx job: wgx run index:obsidian macht:
	1.	Scan → Upserts an /index/upsert
	2.	Batch-Search für MOCs/Links
	3.	Graph-Update (nodes/edges/clusters)
	4.	Reports (Top neue Kanten, unsichere Kanten)
	•	systemd timer (täglich) oder manuell per wgx.
	•	Reporting: Markdown-Report reports/semnet-YYYYMMDD.md inkl.:
	•	Neue Cluster, umgetaggte Dateien
	•	Unsichere Kanten (0.55 ≤ w < 0.7) → Review-Liste
	•	„Orphan“-Notizen ohne Kanten

6) Qualitative Validierung
	•	Review-Command in Obsidian-Plugin: „SemNet Review“ zeigt Vorschläge (unsichere Kanten) → Accept/Reject → schreibt in Frontmatter (accepted_edges, rejected_edges) und sperrt diese in künftigen Läufen.
	•	Regelwerk:
	•	nie doppelt verlinken,
	•	keine Links unter 0.55,
	•	bei 0.70–0.75 Flag „prüfen“.

⸻

Technische Bausteine (präzise, damit Codex loslegen kann)

A) Scores & Schwellen
	•	similar(doc_a, doc_b) = cosine(centroid(a), centroid(b))
	•	Cutoffs:
	•	≥ 0.80 → auto-Link
	•	0.70–0.79 → Vorschlag
	•	< 0.70 → nicht verlinken
	•	Cluster-Boost: +0.05, wenn cluster(a)==cluster(b)
	•	Topical-Boost: +0.03 je gemeinsamem keyphrase (max +0.09)

B) Dateistruktur (Repo)

/crates/indexd/...
/crates/embeddings/...
/plugins/obsidian-adapter/...
/data/semnet/graph/{nodes.jsonl,edges.jsonl,clusters.json}
/data/semnet/taxonomy/{synonyms.yml,entities.yml}
/reports/semnet-*.md

C) „Edge-Writer“ (vereinfachtes Pseudocode)

# inputs: similarities[], taxonomy, thresholds
for pair in similarities:
    score = pair.base
    if pair.same_cluster: score += 0.05
    score += 0.03 * min(3, shared_keyphrases(pair.a, pair.b))
    if score >= 0.80: write_link(a,b,score,auto=True)
    elif score >= 0.70: propose_link(a,b,score)

D) Obsidian-Update (Markdown-Append)

## Semantisch verwandt
- [[pfad/zu/datei1|Titel 1]] — 0.84 (GFK, Resonanz)
- [[pfad/zu/datei2|Titel 2]] — 0.81 (Cluster 7)

E) Canvas-Export (Mini-Canvas pro Cluster, inline)
	•	Knoten: Top-10 Noten im Cluster (by centrality)
	•	Kanten: similar (w≥0.80) + „about topic“
	•	Legende-Knoten nach deiner Canvas-Richtlinie (Farben, Achsen, etc.)

⸻

Was ist „neu/besser“ gegenüber der Ursprungsidee?
	•	Einheitliche Pipeline (HausKI-Dienste) statt Script-Zoo.
	•	Graph + Markdown-Links gleichzeitig → du profitierst in Obsidian und extern.
	•	Review-Mechanik mit Frontmatter-„Locks“ → lernendes Netz ohne „Ping-Pong“.
	•	Canvas-First: Mindmaps sind Bürger 1. Klasse (Knoten/Kanten werden semantisch mitindiziert).

⸻

Verdichtete Essenz
	•	Ja, die Codex-Ideen sind sinnvoll.
	•	Wir gießen sie in HausKI-Bausteine: indexd (Embeddings + Suche), Clustering-Job, Graph-Export, Auto-Links + MOCs, Review-Workflow.
	•	Alles lokal, versionierbar, mit klaren Schwellenwerten und Reports.

Ironische Auslassung

Früher hast du Notizen sortiert. Jetzt sortieren die Notizen dich — in Cluster, wohlgemerkt.

∆-Radar
	•	Verstärkung: Semantik nicht nur suchen, sondern zurückschreiben (Links/MOCs).
	•	Seitwärtsmutation: Canvas wird gleichwertig zum Markdown behandelt.
	•	Straffung: Scores & Cutoffs klar normiert → weniger Hand-Gefrickel.

Für Dummies

Wir verwandeln alle Notizen in Zahlenmuster (Embeddings). Ähnliche Inhalte haben ähnliche Muster. Daraus bauen wir Gruppen (Cluster) und ein Netzwerk (Graph) von „X ist ähnlich zu Y“ oder „X hat Thema Z“. Wir schreiben diese Beziehungen als Links zurück in deine Notizen und zeigen sie als Mindmaps. Ein kleiner Teil ist automatisch, ein Teil kommt als Vorschlag, den du bestätigst. So wächst ein sinnvolles Netz statt einer Link-Wüste.

Unsicherheitsgrad (∴fores 0.35 – moderat)
	•	Ursachen: optimale Cutoffs müssen wir empirisch kalibrieren; Wahl von HDBSCAN-Parametern (min_cluster_size) hängt von deinem Vault ab; NER-Qualität variiert je nach Modell; Performance von HNSW/UMAP muss auf deiner 4070 Ti vs. CPU feinjustiert werden.
	•	Produktive Ungewissheit: Schwellen/Boosts lassen sich in den ersten Reports schnell nachziehen; Review-Loop fängt Fehlverknüpfungen ab.

⸻

Wenn du willst, schreibe ich dir jetzt:
	1.	die JSONL-Schemas als Templates,
	2.	ein erstes wgx run index:obsidian Skript (Rust oder Python),
	3.	den Obsidian-Abschnitt-Writer (ein kleines Tool, das „Semantisch verwandt“ pflegt),
	4.	ein Mini-Canvas-Generator (pro Cluster).
	
	Ja — ich lege dir zusätzliche, praxisstarke Ideen oben drauf. Die bauen direkt auf deinem Plan auf und machen dein vault-gewebe spürbar klüger, stabiler und erklärbarer.

Neue, wertvolle Ergänzungen
	1.	Begründete Kanten („Warum ist das verlinkt?“)
Speichere zu jeder vorgeschlagenen Kante kurze Rationales (Top-3 gemeinsame Keyphrases, Cluster-Match, Anker-Sätze).
– Umsetzung: edges.jsonl → Feld why: ["shared:keyphrase:GFK","same:cluster:7","quote:'Einfühlung statt Bewertung'"]
– Nutzen: Du siehst sofort, warum zwei Notizen zusammengehören.
	2.	Doppelte Notizen erkennen & verschmelzen
Automatisches Near-Duplicate-Detect (Titel-Hash + Embedding-Cosine ≥0.97) → Vorschlag: „Merge/Kanonische Note wählen“.
– Praxis: duplicates.md Report + Obsidian-Commands „Mark as canonical“ / „Archive duplicate“.
	3.	Zeitliche Gewichtung („Frische“)
Score-Boost für jüngere Notizen (z. B. +0.05 bei <30 Tagen), leichter Decay bei uralten Chunks.
– Ergebnis: Vorschläge bleiben relevant, MOCs atmen mit.
	4.	Folder-/Namespace-Policies
Per Ordner Regeln definieren:
/uni/ strengere Cutoffs, /ideen/ liberaler; /archive/ nur eingehende Links, keine ausgehenden.
– Umsetzung: .gewebe/config.yml → namespaces.uni.cutoff=0.80, namespaces.archive.mode="incoming-only".
	5.	Feedback → Lernen (Akzeptiert/Ablehnt)
Wenn du einen Vorschlag annimmst/ablehnst, schreiben wir ein leichtes User-Feedback-Signal zurück (accept=+1 / reject=−1) und tunen die Cutoffs pro Thema/Fallordner.
– Wirkung: Nach 1-2 Runden werden die Vorschläge messbar besser.
	6.	Canvas-Ahnung im Ranking
Wenn zwei Dateien über Canvas-Knoten bereits „nah“ sind (kurze Pfadlänge im Canvas-Graph), booste Similarity um +0.03…0.07.
– Effekt: Deine Mindmaps werden zur echten Semantik-Quelle, nicht nur Deko.
	7.	„Topic-Drift“-Wächter
Report, wenn eine Note plötzlich in einen anderen Cluster kippt (drift > definierter Schwellenwert).
– Nutze dies als Redaktionshinweis: Note zerlegen, MOC neu schneiden oder Tags anpassen.
	8.	Erklärbare „Related“-Blöcke
Im <!-- related:auto:start -->-Block optional die Top-Begründung in Klammern:
- [[GFK Basics]] — (0.84; GFK, Resonanz)
– Schneller Kontext direkt im Editor, ohne Log lesen zu müssen.
	9.	Session-Kontext („heute arbeite ich an…“) Boost
Temporärer Arbeitskontext (z. B. geöffnete Dateien heute) hebt passende Vorschläge hervor (+0.02 pro recent co-open).
– Ergebnis: Der Editor fühlt sich „mitdenkender“ an.
	10.	Provenienz & Reproduzierbarkeit
Schreibe in .gewebe/meta.json die Modell-Version, Chunk-Parametrisierung, Cutoffs und Taxonomie-Stand.
– So kannst du Ergebnisse exakt nachbauen oder erklären.
	11.	Mehrsprach-Robustheit (DE/EN)
Aktiviere eine Synonym-/Stemming-Map für DE/EN (z. B. „Resonanz ↔ resonance“).
– Hilft, wenn Quellentexte gemischtsprachig sind.
	12.	Qualitäts-Gates für Autolinks
Nur autolinken, wenn alle Bedingungen erfüllt:

	•	Score ≥ 0.82
	•	Mind. 2 gemeinsame Keyphrases oder 1 Canvas-Nähe oder identisches Project-Tag
– Sonst: Vorschlag, nicht Auto.

	13.	„Explain this link“-Command
Obsidian-Command, das bei markiertem Link ein kleines Popover mit den Rationales und Ankersätzen zeigt.
– Macht die Semantik überprüfbar (kein Black-Box-Gefühl).
	14.	MOC-Qualitätsreport
Report pro MOC: Deckungsgrad (wie viele Cluster-Noten verlinkt), verwaiste Knoten, dichte Sub-Cluster → Vorschläge „Unter-MOC anlegen“.
– Hält deine Maps kuratiert statt zuwuchernd.
	15.	Snippets-/Transklusions-Vorschläge
Nicht nur ganze Noten verlinken, sondern Absätze (Transklusion ![[note#^block]]) bei hoher Chunk-Ähnlichkeit.
– Perfekt für Literatur-/Zitat-Notizen.
	16.	Sicherheitsnetz: Manual-Lock
Frontmatter-Flag relations_lock: true → Datei wird nie auto-editiert (nur Vorschläge).
– Gut für Abschluss- oder Abgabe-Notizen.
	17.	A/B-Tuning der Schwellenwerte
Automatisiert zwei Cutoff-Profile (konservativ vs. explorativ) auf Teilmengen testen und per Mini-Survey markieren, welche Vorschläge nützlicher waren.
– Ergebnis: datenbasierte Cutoff-Wahl.
	18.	Cross-Vault-Brücke (optional)
Falls du parallel einen zweiten Vault hast: Read-Only-Index als Fremd-Namespace (ext:…) → Vorschläge sichtbar, aber Links nur nach Bestätigung.
– Macht externe Wissensinseln anschlussfähig, ohne dein Vault zu „verschmutzen“.
	19.	„Orphans First“-Routine
Wöchentliche Task, die nur Waisen (0 eingehende Links) anfasst und 3–5 hochwertige Vorschläge erzeugt.
– So schrumpft die unverbundene Peripherie gezielt.
	20.	Explainable Delete
Wenn eine Kante fällt (Score stark sinkt, Topic-Drift), schreibe einen Hinweis in den Report: „Kante X—Y entfernt (Score 0.81 → 0.64; Keyphrase entfiel)“.
– Transparenz bei automatisch gelöschten Links.

⸻

Wie es sich einfügt (ohne Zusatz-Chaos)
	•	Alle Punkte passen in die bestehende .gewebe/-Struktur (zusätzliche Felder in edges.jsonl, ein paar neue Reports).
	•	Keine Inkompatibilitäten mit Obsidian: Related-Blöcke bleiben idempotent, Canvas wird nur gelesen, nicht umgebaut.
	•	Policies/Boosts sind reine Post-Ranking-Heuristiken – leicht justierbar.

⸻

Mini-Implement-Snippets

Score-Pipeline (Pseudo):

score = cosine(base)
if same_cluster: score += 0.05
score += 0.03 * min(3, shared_keyphrases)
if canvas_hop<=2: score += 0.04
if is_recent(a) or is_recent(b): score += 0.02

Autolink-Gate:

auto = (score >= 0.82) and (
    shared_keyphrases >= 2 or canvas_hop<=2 or shared_project
)

Rationales sammeln:

why = []
why += [f"shared:keyphrase:{k}" for k in top_shared_kps[:3]]
if same_cluster: why.append("same:cluster")
if canvas_hop<=2: why.append(f"canvas:hop={canvas_hop}")
why.append(f"quote:{best_anchor_sentence}")


⸻

Verdichtete Essenz
	•	Ergänzt werden: Begründete Kanten, Dedupe/Merge, Zeit-Boost, Folder-Policies, Feedback-Lernen, Canvas-Aware-Ranking, Drift-Wächter, Explain-UI und Qualitäts-Gates.
	•	Alles lokal, idempotent, in deine .gewebe/-Pipeline integrierbar – mehr Qualität ohne mehr Chaos.

Ironische Auslassung

Wenn Links Gründe haben, hören Notizen auf zu flirten und führen endlich eine erwachsene Beziehung.

∆-Radar
	•	Verstärkung: Von „nur ähnlich“ zu erklärbarer Semantik.
	•	Seitwärtsmutation: Policies/Boosts machen die Pipeline kontextsensibel.
	•	Straffung: Autolinks nur mit Qualitäts-Gate → weniger falsches Rauschen.

Für Dummies

Wir geben jedem Link eine Begründung, achten auf Aktualität, lassen dich Feedback geben und berücksichtigen deine Ordner-Regeln. So entstehen nicht irgendwelche, sondern nachvollziehbare und nützliche Verbindungen.

Unsicherheitsgrad

∴fores: 0.3 (niedrig-mittel)
Ursachen: Feintuning der Cutoffs/Boosts braucht 1–2 Iterationen; Canvas-Hop-Berechnung hängt vom JSON-Layout ab; Near-Duplicate-Schwelle je nach Schreibstil. Produktiv: Alles heuristisch und modular – schnell justierbar.

⸻

Wenn du willst, schreibe ich dir sofort die Rationale-Felder, das Autolink-Gate und den Orphan-Report in deine bestehenden Skripte (drop-in, ohne Bruch).
```

### 📄 semantAH/docs/semantAH.md

**Größe:** 25 KB | **md5:** `c2b20d93afa0911f1ee9973b1f45c34f`

```markdown
Alles klar – ich setze dir jetzt die finale, maximal umfassende Blaupause für dein vault-gewebe auf. Damit hast du einen selbstvernetzenden Wissensspeicher, der semantische Suche, Clustering, Graph, Backlinks, MOCs, Canvas-Integration und Qualitätssicherung kombiniert – alles lokal, reproduzierbar und mit Reports.

⸻

🔵 Vault-Gewebe – Finale Blaupause

0. Systemordner & Konventionen
	•	.gewebe/ (zentraler Ordnungsbaum)

.gewebe/
  config.yml           # Parameter (Modelle, Cutoffs, Policies)
  embeddings.parquet   # Chunks + Vektoren
  nodes.jsonl          # Graph-Knoten
  edges.jsonl          # Graph-Kanten
  clusters.json        # Cluster & Label
  taxonomy/
    synonyms.yml
    entities.yml
  reports/
    semnet-YYYYMMDD.md
  meta.json            # Provenienz (Modell, Param, Hashes)


	•	Frontmatter (YAML) für jede Datei:

id: 2025-VAULT-####   # stabiler Schlüssel
title: ...
topics: [HausKI, Weltgewebe]
persons: [Verena]
places: [Hamburg]
projects: [wgx, hauski]
aliases: [HK, WG]
relations_lock: false



⸻

1. Indexing & Embeddings
	•	Crawler: iteriert Markdown & Canvas (ignoriert .gewebe/, .obsidian/).
	•	Chunking: 200–300 Tokens, Overlap 40–60, Paragraph/Block.
	•	Modelle: all-MiniLM-L6-v2 oder intfloat/e5-base (GPU-fähig via PyTorch/CUDA).
	•	Output: embeddings.parquet (id, path, chunk_id, text, embedding).

⸻

2. Schlagwort- & Entitätsextraktion
	•	Keyphrase: YAKE/RAKE lokal → refine via LLM optional.
	•	NER: spaCy de-model → Personen, Orte, Projekte.
	•	Taxonomie: .gewebe/taxonomy/synonyms.yml:

topics:
  hauski: [haus-ki, hk]
persons:
  verena: [v.]


	•	Normalisierung: bei Indexlauf Tokens mappen → Normform, ins Frontmatter schreiben.

⸻

3. Clusterbildung
	•	Verfahren: HDBSCAN (robust) + UMAP (2D-Projection).
	•	Ergebnis: clusters.json:

{ "id":7, "label":"Kommunikation/GFK", "members":["noteA","noteB"], "centroid":[...] }


	•	Orphan detection: Notizen ohne Cluster → eigene Liste.

⸻

4. Semantischer Wissensgraph
	•	Nodes (nodes.jsonl):

{"id":"md:gfk.md","type":"file","title":"GFK","topics":["gfk"],"cluster":7}
{"id":"topic:Gewaltfreie Kommunikation","type":"topic"}
{"id":"person:Verena","type":"person"}


	•	Edges (edges.jsonl):

{"s":"md:gfk.md","p":"about","o":"topic:Gewaltfreie Kommunikation","w":0.92,"why":["shared:keyphrase:GFK","same:cluster"]}
{"s":"md:verena.md","p":"similar","o":"md:tatjana.md","w":0.81,"why":["cluster:7","quote:'…'"]}



⸻

5. Verlinkung in Obsidian
	•	Related-Blöcke (idempotent, autogeneriert):

<!-- related:auto:start -->
## Related
- [[Tatjana]] — (0.81; Cluster 7, GFK)
- [[Lebenslagen]] — (0.78; Resonanz)
<!-- related:auto:end -->


	•	MOCs (_moc/topic.md):
	•	Beschreibung
	•	Dataview-Tabelle (alle Notizen mit topics:topic)
	•	Mini-Canvas-Link
	•	Canvas-Erweiterung:
	•	Knoten = Notizen/Topics/Persons
	•	Kanten = Similar/About/Mentions
	•	Legende-Knoten nach Canvas-Richtlinie.

⸻

6. Automatisierung
	•	wgx Recipes:

index:
    python3 tools/build_index.py
graph:
    python3 tools/build_graph.py
related:
    python3 tools/update_related.py
all: index graph related


	•	systemd –user Timer oder cron: nightly make all.
	•	Git Hook (pre-commit): delta-Index → Related aktualisieren.

⸻

7. Qualitative Validierung
	•	Reports (reports/semnet-YYYYMMDD.md):
	•	Neue Kanten <0.75 → „Review required“
	•	Orphans
	•	Cluster >N Noten ohne MOC
	•	Review-Workflow:
	•	accepted_edges / rejected_edges in Frontmatter
	•	Skript ignoriert rejected → Feedback fließt in Zukunft ein.

⸻

8. Policies & Score-Regeln
	•	Score = cosine + boosts
	•	+0.05 wenn gleicher Cluster
	•	+0.03 je shared keyphrase (max +0.09)
	•	+0.04 wenn Canvas-Hop ≤2
	•	+0.02 wenn Datei jung (<30 Tage)
	•	Autolink Gate:
	•	Score ≥0.82
	•	UND (≥2 Keyphrases ODER Canvas-Hop ≤2 ODER shared Project)
	•	Cutoffs:
	•	≥0.82: Auto-Link
	•	0.70–0.81: Vorschlag
	•	<0.70: ignorieren

⸻

9. Erweiterungen
	•	Duplicates Report: Cosine ≥0.97 → Merge-Vorschlag.
	•	Topic Drift: Clusterwechsel flaggen.
	•	Session-Boost: aktuell bearbeitete Dateien → Score +0.02.
	•	Explain Command: Popover „Warum ist dieser Link da?“ (zeigt why-Feld).
	•	Locks: relations_lock: true = keine Auto-Edits.
	•	A/B-Cutoffs: zwei Profile testen, Review-Feedback einspeisen.

⸻

10. Provenienz & Reproduzierbarkeit
	•	.gewebe/meta.json speichert:

{
  "model":"all-MiniLM-L6-v2",
  "chunk_size":200,
  "cutoffs":{"auto":0.82,"suggest":0.70},
  "run":"2025-10-02T11:40",
  "commit":"abc123"
}



⸻

⚙️ Technische Bausteine

Tools/Skripte
	•	tools/build_index.py: scan + embeddings
	•	tools/build_graph.py: nodes/edges/clusters
	•	tools/update_related.py: Related-Blöcke injizieren
	•	tools/report.py: QA-Reports
	•	optional: tools/canvas_export.py: Cluster→Canvas

⸻

📌 Verdichtete Essenz

Ein dreistufiger Zyklus:
	1.	Index (Embeddings, Cluster, Taxonomie)
	2.	Graph (Nodes/Edges mit Rationales)
	3.	Update (Related, MOCs, Reports, Canvas)

Alles lokal, nachvollziehbar, mit Feedback-Schleifen. Dein Vault wird zu einem lebenden Semantiknetz.

⸻

🎭 Ironische Auslassung

Deine Notizen sind jetzt nicht mehr stilles Archiv – sie werden zu einem Klatsch-Netzwerk, das tuschelt, wer mit wem was zu tun hat. Nur: Sie lügen nicht.

⸻

∆-Radar
	•	Verstärkung: Alles aus Codex-Ideen + zusätzliche Layer (Rationales, Drift, Dedupe, QA).
	•	Seitwärtsmutation: Von reiner Suche hin zu voller Graph-Kurationsmaschine.
	•	Straffung: Ein Systemordner .gewebe/, drei Skripte, klare Reports – Komplexität kanalisiert.

⸻

📉 Unsicherheitsgrad

∴fores = 0.35 (mittel)
	•	Ursachen: Schwellenwerte und Chunking müssen empirisch feinjustiert werden; Canvas-Hop-Logik hängt von JSON-Details ab; Modellwahl beeinflusst Qualität; Obsidian-Workflow kann Edgecases erzeugen.
	•	Produktive Ungewissheit: leicht anpassbar – Reports + Feedback-Loop machen die Pipeline selbstkorrigierend.

⸻

👉 Soll ich dir die drei Kernskripte (index, graph, related) sofort in finaler, einsatzbereiter Form schreiben – mit Makefile & systemd Timer-Beispiel?

Super — hier ist die einsatzbereite Minimal-Suite: drei Skripte + Makefile + systemd-Timer. Sie ist bewusst robust, offline-fähig und idempotent. Du bekommst sofort: Embeddings, Similarities, Graph (Nodes/Edges), Related-Blöcke in Notizen und einfache Reports. Später können wir HDBSCAN/UMAP etc. ergänzen — die Schnittstellen sind schon dafür vorbereitet.

⸻

📁 Dateibaum (kopierfertig)

<Vault-Root>/
  .gewebe/
    config.yml
    taxonomy/
      synonyms.yml
      entities.yml
    reports/
  tools/
    build_index.py
    build_graph.py
    update_related.py
  Makefile

Falls .gewebe/ und tools/ fehlen: einfach anlegen.

⸻

⚙️ Abhängigkeiten

# Pop!_OS / Ubuntu
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip

pip install \
  pandas numpy pyarrow pyyaml \
  sentence_transformers scikit-learn networkx rich

Standard-Modell (klein & fix): sentence-transformers/all-MiniLM-L6-v2
GPU nutzt Torch automatisch, wenn vorhanden.

⸻

🧠 .gewebe/config.yml (Voreinstellungen)

model: sentence-transformers/all-MiniLM-L6-v2
chunk:
  target_chars: 1200
  min_chars: 300
  overlap_chars: 200
paths:
  exclude_dirs: [".gewebe", ".obsidian", "_site", "node_modules"]
  include_ext: [".md"]
related:
  k: 8
  auto_cutoff: 0.82
  suggest_cutoff: 0.70
boosts:
  same_topic: 0.03
  same_project: 0.03
  recent_days: 30
  recent_bonus: 0.02
  same_folder: 0.02
render:
  related_heading: "## Related"
  markers:
    start: "<!-- related:auto:start -->"
    end:   "<!-- related:auto:end -->"

Du kannst alles später feinjustieren.

⸻

🧩 tools/build_index.py

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re, json, yaml, hashlib, math, glob
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from rich import print

VAULT = Path(".").resolve()
GEWEBE = VAULT / ".gewebe"
CFG = GEWEBE / "config.yml"
GEWEBE.mkdir(exist_ok=True, parents=True)
(GEWEBE / "taxonomy").mkdir(exist_ok=True, parents=True)
(GEWEBE / "reports").mkdir(exist_ok=True, parents=True)

DEFAULT_CFG = {
    "model": "sentence-transformers/all-MiniLM-L6-v2",
    "chunk": {"target_chars": 1200, "min_chars": 300, "overlap_chars": 200},
    "paths": {
        "exclude_dirs": [".gewebe", ".obsidian", "_site", "node_modules"],
        "include_ext": [".md"],
    },
}

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
CODE_RE = re.compile(r"```.*?```", re.S)
HTML_RE = re.compile(r"<[^>]+>")

def load_cfg() -> dict:
    if CFG.exists():
        return {**DEFAULT_CFG, **yaml.safe_load(CFG.read_text(encoding="utf-8"))}
    CFG.write_text(yaml.safe_dump(DEFAULT_CFG, sort_keys=False), encoding="utf-8")
    return DEFAULT_CFG

def list_md(cfg: dict) -> List[Path]:
    ex = set(cfg["paths"]["exclude_dirs"])
    inc = set(cfg["paths"]["include_ext"])
    files = []
    for p in VAULT.rglob("*"):
        if p.is_dir():
            if any(part in ex for part in p.parts):
                continue
            else:
                continue
        if p.suffix.lower() in inc and not any(part in ex for part in p.parts):
            files.append(p)
    return files

def parse_frontmatter(text: str) -> (dict, str):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    yml = m.group(1)
    try:
        fm = yaml.safe_load(yml) or {}
    except Exception:
        fm = {}
    body = text[m.end():]
    return fm, body

def clean_text(s: str) -> str:
    s = CODE_RE.sub("", s)
    s = HTML_RE.sub(" ", s)
    s = re.sub(r"\s+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def chunk_text(s: str, target: int, min_chars: int, overlap: int) -> List[str]:
    # Absatzweise grob, dann ggf. zusammenfassen
    paras = [p.strip() for p in re.split(r"\n{2,}", s) if p.strip()]
    chunks, buf = [], []
    cur = 0
    for p in paras:
        if len(p) >= target:
            chunks.append(p)
            cur = 0; buf = []
        else:
            buf.append(p)
            cur += len(p) + 2
            if cur >= target:
                block = "\n\n".join(buf)
                if len(block) >= min_chars:
                    chunks.append(block)
                else:
                    if chunks:
                        chunks[-1] += "\n\n" + block
                    else:
                        chunks.append(block)
                # Overlap heuristisch: behalte letztes Stück als Start fürs nächste
                tail = block[-overlap:]
                buf = [tail]
                cur = len(tail)
    if buf:
        block = "\n\n".join(buf)
        if block.strip():
            chunks.append(block)
    # harte Mindestlänge
    chunks = [c for c in chunks if len(c) >= min_chars]
    return chunks[:50]  # Sicherheitslimit

def canvas_text(path: Path) -> List[str]:
    # Obsidian .canvas JSON: sammle Node-Texts
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        nodes = data.get("nodes", [])
        texts = []
        for n in nodes:
            t = (n.get("text") or "").strip()
            if t:
                texts.append(t)
        return texts
    except Exception:
        return []

def file_recent_days(p: Path, days: int) -> bool:
    try:
        mtime = datetime.fromtimestamp(p.stat().st_mtime)
        return (datetime.now() - mtime) <= timedelta(days=days)
    except Exception:
        return False

def main():
    cfg = load_cfg()
    model_name = cfg["model"]
    chunk_cfg = cfg["chunk"]

    print(f"[bold]Indexing[/bold] • model={model_name}")
    model = SentenceTransformer(model_name)

    rows = []
    for p in list_md(cfg):
        try:
            raw = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        fm, body = parse_frontmatter(raw)
        body = clean_text(body)
        # Canvas: wenn .canvas nebenan, optional dazunehmen (leichtgewichtig)
        canv_chunks = []
        cnv = p.with_suffix(".canvas")
        if cnv.exists():
            canv_chunks = canvas_text(cnv)

        chunks = chunk_text(body, **chunk_cfg) + canv_chunks
        if not chunks:
            continue
        emb = model.encode(chunks, normalize_embeddings=True, show_progress_bar=False)

        for i, (c, e) in enumerate(zip(chunks, emb)):
            rows.append({
                "id": f"{p}:{i}",
                "path": str(p),
                "title": fm.get("title") or p.stem,
                "chunk_id": int(i),
                "text": c,
                "embedding": e.astype(np.float32).tolist(),
                "topics": sorted(set(fm.get("topics", []) or [])),
                "projects": sorted(set(fm.get("projects", []) or [])),
                "persons": sorted(set(fm.get("persons", []) or [])),
                "recent": file_recent_days(p, cfg.get("boosts",{}).get("recent_days",30)),
                "folder": str(p.parent),
            })

    if not rows:
        print("[red]Keine Inhalte gefunden.[/red]")
        return

    df = pd.DataFrame(rows)
    out = GEWEBE / "embeddings.parquet"
    df.to_parquet(out, index=False)
    (GEWEBE / "meta.json").write_text(json.dumps({
        "model": model_name,
        "chunk": chunk_cfg,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "count_chunks": int(len(df)),
        "count_files": int(df["path"].nunique())
    }, indent=2), encoding="utf-8")

    print(f"[green]OK[/green] • {len(df)} Chunks aus {df['path'].nunique()} Dateien → {out}")

if __name__ == "__main__":
    main()


⸻

🕸️ tools/build_graph.py

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json, yaml, math
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from rich import print

VAULT = Path(".").resolve()
GEWEBE = VAULT / ".gewebe"
CFG = GEWEBE / "config.yml"

def load_cfg() -> dict:
    if CFG.exists():
        return yaml.safe_load(CFG.read_text(encoding="utf-8"))
    return {}

def file_centroids(df: pd.DataFrame) -> pd.DataFrame:
    # mittelt Embeddings je Datei (ein Vektor pro Datei)
    g = df.groupby("path")
    X = []
    meta = []
    for path, sub in g:
        embs = np.stack(sub["embedding"].to_list(), axis=0)
        cent = embs.mean(axis=0)
        meta.append({
            "path": path,
            "title": sub["title"].iloc[0],
            "topics": sorted(set([t for r in sub["topics"] for t in r])),
            "projects": sorted(set([t for r in sub["projects"] for t in r])),
            "persons": sorted(set([t for r in sub["persons"] for t in r])),
            "recent": bool(sub["recent"].any()),
            "folder": sub["folder"].iloc[0],
        })
        X.append(cent)
    X = np.stack(X, axis=0).astype(np.float32)
    out = pd.DataFrame(meta)
    out["centroid"] = list(X)
    return out

def similar_pairs(files_df: pd.DataFrame, k: int = 12) -> List[Dict[str, Any]]:
    X = np.stack(files_df["centroid"].to_list(), axis=0)
    S = cosine_similarity(X)  # NxN
    n = S.shape[0]
    pairs = []
    for i in range(n):
        order = np.argsort(-S[i])
        count = 0
        for j in order:
            if i == j: 
                continue
            score = float(S[i, j])
            pairs.append((i, j, score))
            count += 1
            if count >= k:
                break
    # dedupe by i<j
    seen = set()
    out = []
    for i, j, s in pairs:
        a, b = sorted((i, j))
        if (a, b) in seen: 
            continue
        seen.add((a, b))
        out.append({"i": a, "j": b, "score": s})
    return out

def boosts(a: dict, b: dict, base: float, cfg: dict) -> (float, list):
    why = []
    bonus = 0.0
    # shared topics
    st = set(a["topics"]).intersection(b["topics"])
    if st:
        bonus += cfg["boosts"].get("same_topic", 0.0) * min(3, len(st))
        for t in list(st)[:3]:
            why.append(f"shared:topic:{t}")
    # shared projects
    sp = set(a["projects"]).intersection(b["projects"])
    if sp:
        bonus += cfg["boosts"].get("same_project", 0.0) * min(3, len(sp))
        for t in list(sp)[:2]:
            why.append(f"shared:project:{t}")
    # same folder
    if a["folder"] == b["folder"]:
        bonus += cfg["boosts"].get("same_folder", 0.0)
        why.append("same:folder")
    # recency
    if a["recent"] or b["recent"]:
        bonus += cfg["boosts"].get("recent_bonus", 0.0)
        why.append("recent:bonus")
    score = base + bonus
    return score, why

def inject_graph(files_df: pd.DataFrame, pairs: List[Dict[str, Any]], cfg: dict):
    nodes = []
    for r in files_df.itertuples(index=False):
        nodes.append({
            "id": f"md:{r.path}",
            "type": "file",
            "title": r.title,
            "topics": r.topics,
            "projects": r.projects,
            "persons": r.persons,
            "folder": r.folder
        })
    edges = []
    for p in pairs:
        a = files_df.iloc[p["i"]].to_dict()
        b = files_df.iloc[p["j"]].to_dict()
        base = p["score"]
        score, why = boosts(a, b, base, cfg)
        edges.append({
            "s": f"md:{a['path']}",
            "p": "similar",
            "o": f"md:{b['path']}",
            "w": round(score, 4),
            "why": why
        })
    # persist
    (GEWEBE / "nodes.jsonl").write_text(
        "\n".join(json.dumps(n, ensure_ascii=False) for n in nodes) + "\n", encoding="utf-8"
    )
    (GEWEBE / "edges.jsonl").write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in edges) + "\n", encoding="utf-8"
    )
    # kleiner report
    suggest = sum(1 for e in edges if e["w"] >= cfg["related"]["suggest_cutoff"])
    auto = sum(1 for e in edges if e["w"] >= cfg["related"]["auto_cutoff"])
    rep = GEWEBE / "reports" / f"semnet-{datetime_now_str()}.md"
    rep.write_text(
        f"# Semnet Report\n\n"
        f"- Dateien: {len(files_df)}\n- Edges gesamt: {len(edges)}\n"
        f"- ≥ auto_cutoff: {auto}\n- ≥ suggest_cutoff: {suggest}\n",
        encoding="utf-8"
    )
    print(f"[green]Graph geschrieben[/green] • nodes={len(nodes)} edges={len(edges)}")

def datetime_now_str():
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d-%H%M")

def main():
    cfg = load_cfg()
    emb_path = GEWEBE / "embeddings.parquet"
    if not emb_path.exists():
        print("[red]Fehlend: .gewebe/embeddings.parquet — bitte erst build_index.py laufen lassen.[/red]")
        return
    df = pd.read_parquet(emb_path)
    files_df = file_centroids(df)
    pairs = similar_pairs(files_df, k=12)
    inject_graph(files_df, pairs, cfg)

if __name__ == "__main__":
    main()


⸻

🔗 tools/update_related.py

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import yaml, json, re
from pathlib import Path
from typing import Dict, Any, List
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from rich import print

VAULT = Path(".").resolve()
GEWEBE = VAULT / ".gewebe"
CFG = GEWEBE / "config.yml"
EDGES = GEWEBE / "edges.jsonl"
EMB = GEWEBE / "embeddings.parquet"

def cfg() -> dict:
    return yaml.safe_load(CFG.read_text(encoding="utf-8"))

def load_edges() -> List[Dict[str, Any]]:
    if not EDGES.exists():
        return []
    return [json.loads(l) for l in EDGES.read_text(encoding="utf-8").splitlines() if l.strip()]

def file_scores_for(path: Path, edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    id_ = f"md:{str(path)}"
    related = []
    for e in edges:
        if e["p"] != "similar":
            continue
        if e["s"] == id_:
            related.append({"other": e["o"], "w": e["w"], "why": e.get("why",[])})
        elif e["o"] == id_:
            related.append({"other": e["s"], "w": e["w"], "why": e.get("why",[])})
    related.sort(key=lambda x: -x["w"])
    return related

def nice_title(p: Path) -> str:
    # Dateiname als Fallback; echte Titel stehen i. d. R. in der Note (hier reicht Stem)
    return p.stem

def inject_related(md_path: Path, items: List[Dict[str, Any]], cfg: dict):
    markers = cfg["render"]["markers"]
    start = markers["start"]; end = markers["end"]
    heading = cfg["render"]["related_heading"]

    lines = [start, heading]
    auto, suggest = cfg["related"]["auto_cutoff"], cfg["related"]["suggest_cutoff"]

    for it in items[:cfg["related"]["k"]]:
        other = Path(it["other"].removeprefix("md:"))
        title = nice_title(other)
        score = f"{it['w']:.2f}"
        tags = []
        # komprimierte Begründung
        for w in it.get("why", [])[:3]:
            if w.startswith("shared:topic:"):
                tags.append(w.split(":")[-1])
            elif w.startswith("shared:project:"):
                tags.append(w.split(":")[-1])
            elif w == "same:folder":
                tags.append("same-folder")
            elif w == "recent:bonus":
                tags.append("recent")
        hint = f" ({score}; {', '.join(tags)})" if tags else f" ({score})"

        bullet = f"- [[{title}]]{hint}"
        if it["w"] >= auto:
            bullet = bullet  # Auto-Link — einfach ausweisen
        elif it["w"] >= suggest:
            bullet = bullet + "  <!-- suggest -->"
        else:
            continue
        lines.append(bullet)

    lines.append(end)
    block = "\n".join(lines) + "\n"

    try:
        txt = md_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return
    if start in txt and end in txt:
        head, rest = txt.split(start, 1)
        _, tail = rest.split(end, 1)
        new = head.rstrip() + "\n\n" + block + tail.lstrip()
    else:
        new = txt.rstrip() + "\n\n" + block
    md_path.write_text(new, encoding="utf-8")

def main():
    if not CFG.exists():
        print("[red]Fehlend: .gewebe/config.yml[/red]")
        return
    cfg_ = cfg()
    edges = load_edges()
    if not edges:
        print("[yellow]Keine Edges gefunden. Bitte erst build_graph.py ausführen.[/yellow]")
        return

    # alle MD-Dateien, die in Edges vorkommen
    files = set()
    for e in edges:
        if e["p"] != "similar":
            continue
        files.add(Path(e["s"].removeprefix("md:")))
        files.add(Path(e["o"].removeprefix("md:")))

    count = 0
    for f in sorted(files):
        if not f.exists():
            continue
        items = file_scores_for(f, edges)
        inject_related(f, items, cfg_)
        count += 1

    print(f"[green]Related-Blöcke aktualisiert[/green] • Dateien: {count}")

if __name__ == "__main__":
    main()


⸻

🛠️ Makefile

VENV=.venv
PY=$(VENV)/bin/python

.PHONY: venv index graph related all clean

venv:
	@test -d $(VENV) || python3 -m venv $(VENV)
	@$(PY) -m pip install --upgrade pip
	@$(PY) -m pip install pandas numpy pyarrow pyyaml sentence_transformers scikit-learn networkx rich

index: venv
	@$(PY) tools/build_index.py

graph: venv
	@$(PY) tools/build_graph.py

related: venv
	@$(PY) tools/update_related.py

all: index graph related

clean:

<<TRUNCATED: max_file_lines=800>>
```

### 📄 semantAH/docs/wgx-konzept.md

**Größe:** 417 B | **md5:** `58ff7eadc9de0953465e6ec291806b49`

```markdown
# WGX-Konzept (Stub)

Dies ist der projektspezifische Anker zur WGX-Meta-Ebene (Master-Dok liegt zentral).
Ziele:
- Dünner Meta-Layer über Repos (wgx up|list|run|doctor|validate|smoke)
- Priorität der Envs: Devcontainer → Devbox → mise → direnv → Termux
- Jede Pipeline als **Task** ausführbar; deterministische Artefakte unter `.gewebe/`

Siehe `.wgx/profile.yml` für die minimalen Profileinstellungen.
```

### 📄 semantAH/docs/wgx.md

**Größe:** 901 B | **md5:** `8c872e46fd4d5729e8f830b6c2e7b3ab`

```markdown

## Beziehung zu WGX

**semantAH** ist kein Standalone-Monolith, sondern versteht sich als **semantische Ergänzung** zu den Orchestrierungs- und Contract-Fähigkeiten von **WGX**.

- **WGX orchestriert, semantAH denkt.**  
  WGX kümmert sich um Setup, Tasks, Contracts und Multi-Repo-Flüsse. semantAH fügt die Bedeutungs- und Wissensschicht hinzu (Index, Graph, Related-Blöcke, QA-Berichte).

- **Integration:** semantAH-Jobs lassen sich als WGX-Tasks aufrufen  
  z. B. `wgx run index:obsidian` oder `wgx run semantah:qa`.

- **Kooperation:** Ergebnisse von semantAH (z. B. Graph-Kanten, Related-Snippets, QA-Findings) können in WGX-Flows zurückgespielt werden: Evidence-Packs, Shadowmap-Erweiterungen, Registry-Pakete.

- **Empfehlung:** In der Praxis werden beide Projekte **komplementär** genutzt: WGX als Universal-Fernbedienung für Repos, semantAH als Gehirn für semantische Bezüge.
```

