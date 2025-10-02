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
{"s":"md:gfk.md","p":"about","o":"topic:Gewaltfreie Kommunikation","w":0.92,"why":["shared:keyphrase:GFK","same:cluster"]}
{"s":"md:verena.md","p":"similar","o":"md:tatjana.md","w":0.81,"why":["cluster:7","quote:'…'"]}
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

