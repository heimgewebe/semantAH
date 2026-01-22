# SemantAH: Umfassende Optimierungsstrategie und Architektur-Analyse

Dieses Dokument vereint die technische Architektur-Analyse mit den semantischen Optimierungsstrategien, um *semantAH* zu einem robusten, leistungsfähigen und „verständigen“ Wissens-Organ im Heimgewebe-Organismus zu entwickeln.

## 1. Überblick über den aktuellen Stand

Das Projekt *semantAH* dient als semantische Index- und Graph-Pipeline für Obsidian-Notizsammlungen. Die Software zerlegt Notizen in Chunks, erzeugt daraus Embeddings, baut einen Vektorindex und Wissensgraphen auf und bettet anschließend „Related“-Blöcke direkt in Markdown-Dateien ein.

Das Repository ist als Rust-Workspace organisiert und besteht aus zwei Haupt-Crates (`embeddings` und `indexd`) sowie Python-Skripten zur Pipeline-Steuerung. Derzeit handelt es sich um einen Initialzustand: Die Python-Skripte in `tools/` sind teilweise noch Stubs, und die vollständige Pipeline ist skizziert. `docs/blueprint.md` beschreibt eine detaillierte Blaupause der geplanten Funktionen – vom Chunking über Schlagwort- und Entitätserkennung bis zur Graph-Generierung.

## 1a. Contracts, Artefakte und Heimgewebe-Einordnung

semantAH ist im Heimgewebe kein „Feature-Sammler“, sondern ein **Semantik- und Beobachtungsorgan**.
Wahrheit entsteht ausschließlich über explizite Artefakte mit klaren Contracts.

### Produzierte Artefakte (Output)

| Artefakt | Zweck | Konsumenten |
|--------|------|-------------|
| `knowledge.observatory.v1.json` | Metriken, Drift, Coverage, Qualität | leitstand, hausKI, heimlern |
| `insights.daily.v1.json` | Verdichtete semantische Auffälligkeiten | heimgeist |
| `edges.semantic.v1.jsonl` | Semantische Kanten inkl. `why` | leitstand, Obsidian-Tools |
| `nodes.semantic.v1.jsonl` | Knoten (Files, Topics, Persons, Projects) | leitstand |
| `semantah.meta.v1.json` | Provenienz (Modelle, Parameter, Hashes) | CI/WGX, Review |

### Konsumierte Artefakte (Input)

| Artefakt | Herkunft | Zweck |
|--------|---------|-------|
| `os.context.state.v1` | mitschreiber | Session- und Arbeitskontext |
| `policy.decisions.v1` | hausKI | Cutoff-Profile, Gates |
| `policy.feedback.v1` | heimlern | Lernrückkopplung |
| externe Events | chronik | Zeitliche Einordnung |

### Contract-Regel (bindend)

- **Kein Artefakt ohne Schema**
- **Kein Schema ohne Owner**
- **Keine impliziten Entscheidungen in semantAH**

Alle Schema-Definitionen liegen kanonisch im `metarepo/contracts/`.

## 2. Architektur und Codequalität

### Rust-Teil

*   **Crate `embeddings`:** Definiert das `Embedder`-Trait mit asynchroner `embed`-Methode. Die vorhandene Ollama-Implementation ist modular und testgetrieben, validiert Dimensions-Mismatchs und verarbeitet Batches. Einschränkungen sind die Beschränkung auf Ollama und rudimentäre Fehlerbehandlung.
*   **Crate `indexd`:** Implementiert einen Axum-HTTP-Service (Upsert, Delete, Search, Embed Text). Die API validiert JSON-Payloads und nutzt einen in-memory `VectorStore`. Die Suche erfolgt linear über normalisierte Vektoren (Cosinus-Ähnlichkeit). Es fehlen Persistenz und Approximate-Nearest-Neighbour-Indizes (ANN).

### Python-Teil

*   **Tools (`build_index.py`, `build_graph.py`, `update_related.py`):** Aktuell teilweise Platzhalter, die Dummy-Dateien erzeugen. Die Blaupause sieht eine umfangreiche Pipeline vor (SentenceTransformers, Keyphrase-Extraktion, HDBSCAN-Cluster, Policy-basierte Kanten).

## 3. Technische Optimierungspotentiale

### 3.1 Robuste Embedding-Schicht

*   **Mehrere Provider:** Neben Ollama sollten Provider wie `sentence-transformers` (via FFI), OpenAI oder HuggingFace integriert werden. Ein Feature-Flag-System und Umgebungsvariablen für API-Keys erhöhen die Flexibilität.
*   **Batching & Caching:** Standardmäßiges Batching und Caching (z. B. LRU-Cache) vermeiden redundante Berechnungen.
*   **Konfiguration:** Zentrale `semantah.yml` für Modellname, Dimensionen und Provider-URLs.

### 3.2 Leistungsfähiger Vektorindex

*   **ANN-Algorithmen:** Integration von HNSWlib oder Faiss (via `hnsw_rs` o.ä.) für logarithmische Skalierbarkeit statt linearer Suche.
*   **Persistenz:** Speichern des Index als JSONL oder Binärformat (z. B. `.gewebe/indexd/store.jsonl`) mit asynchronem Laden/Speichern und optionalem Write-Ahead-Log.
*   **Parallelisierung:** Sharding nach Namespaces oder Hash-Bereichen für Multi-Core-Nutzung.
*   **Trennung von Logik & Index:** Filter- und Ranking-Logiken (Zeit-Boosts, Tags) sollten strukturell vom reinen Index getrennt sein.

### 3.3 API und Service-Design

*   **Status-Endpunkte:** Metriken wie Indexgröße und Aktualisierungszeitpunkt für Monitoring (Prometheus/OpenTelemetry).
*   **Fehler- & Rate-Handling:** Klare Trennung von 4xx/5xx Fehlern, deterministische `error_code`s und Rate-Limiting für teure Endpunkte.
*   **Authentifizierung:** Optionale API-Keys pro Namespace (`chronik`, `osctx`, `docs`, `code`, `insights`) und Read-Only-Modi für externe Vaults.

### 3.4 Vollständige Python-Pipeline

*   **Chunking:** Rekursives Parsen von Markdown und Frontmatter, Zerlegung in Token-Chunks gemäß Blaupause.
*   **Graph-Generierung:** HDBSCAN-Cluster, UMAP-Projektionen und Score-Berechnung für Kanten.
*   **Idempotenz:** Sicherstellen, dass „Related“-Blöcke in Markdown erkannt und sauber ersetzt werden (konfigurierbare Marker).
*   **Performanz:** Nutzung von `concurrent.futures` oder `multiprocessing` für paralleles Chunking.

### 3.5 Tests, CI und Qualität

*   **Testabdeckung:** Ausbau der Python-Tests (Parsing, Graph-Pipeline) und Integration-Tests gegen `indexd`.
*   **Linting:** Strikte Regeln für `ruff` (Python) und `clippy` (Rust).
*   **Benchmarks:** Automatisierte Performance-Tests in der CI (z. B. Suche top-k=20 < 60ms).

### 3.6 Dokumentation & DX

*   **Sync:** Regelmäßiger Abgleich von `docs/` mit dem Entwicklungsstand.
*   **Quickstart:** Erweiterung um reale Beispiele, Hardware-Anforderungen und FAQs.
*   **Contributing:** Guidelines für Code-Style und Review-Prozesse.

### 3.7 Sicherheit & Compliance

*   **Datenschutz:** Lokale Verarbeitung für sensible Daten, verschlüsselte Persistenz, Safe-Mode-Policies für externe Provider.

---

## 4. Semantische Optimierung und Feature-Ausbau

Neben der technischen Basis muss semantAH inhaltlich „verständiger“ werden. Dies erfordert gezielte Maßnahmen bei Embeddings, Ranking und Metadaten.

### 4.1 Bessere Embeddings und Chunking

*   **Modellwahl:** Upgrade von `nomic-embed-text` auf leistungsfähigere Modelle wie `sentence-transformers/all-MiniLM-L6-v2`. Wichtig: Versionierung der Modell-Revisionen in Provenienzdaten.
*   **Chunk-Größe:** Blöcke von 200–300 Tokens (ca. 1200 Zeichen) mit 40–60 Tokens (ca. 200 Zeichen) Überlappung bieten optimalen Kontext ohne Verwässerung.
*   **Normalisierung:** Zwingende L2-Normalisierung der Vektoren vor dem Persistieren für direkte Kosinus-Ähnlichkeit.

### 4.2 Formale Gate-Regeln für Auto-Linking

Auto-Links sind nur zulässig, wenn **mehrere unabhängige Kriterien** erfüllt sind.

#### Basisformel

```
score = cosine_similarity + boosts
```

#### Boosts (konfigurierbar)
- +0.05 gleicher Cluster
- +0.03 je Keyphrase (max +0.09)
- +0.04 Canvas-Hop ≤ 2
- +0.02 Recency (< 30 Tage, gedeckelt)

#### Hard Gates (alle erforderlich)
- `score >= auto_cutoff`
- mindestens **eines**:
  - Keyphrases ≥ 2
  - Canvas-Hop ≤ 2
  - shared project
- `relations_lock != true`
- Zielkante nicht in `rejected_edges`

#### Hard Blocks (überschreiben alles)
- Cosine ≥ 0.97 → **kein Auto-Link**, nur Duplicate-Report
- Namespace-Policy = read-only
- Manuell gelöschte Kante (Explizitverbot)

#### Ergebnisstufen
| Score | Aktion |
|------|--------|
| ≥ auto_cutoff + Gates | Auto-Link |
| suggest_cutoff–auto_cutoff | Vorschlag (Review) |
| < suggest_cutoff | Ignorieren |

Alle Grenzwerte sind in `.gewebe/config.yml` versioniert und A/B-testfähig.

### 4.3 Synonyme, Entitäten und Taxonomie

*   **Frontmatter:** Nutzung von Feldern wie `topics`, `persons`, `places`, `projects`.
*   **Taxonomie:** Zentrale Dateien (`.gewebe/taxonomy/synonyms.yml`, `entities.yml`) zum Zusammenführen unterschiedlicher Schreibweisen (z. B. `hauski` ↦ `haus-ki`).
*   **Extraktion:** Einsatz von YAKE/RAKE und spaCy (NER) zur Begründung von Graph-Kanten (`about`, `similar`).

### 4a. Ebenentrennung: Beobachtung, Entscheidung, Lernen

Zur Wahrung der Heimgewebe-Integrität gelten folgende Rollen strikt:

### semantAH (Beobachtung)
- berechnet Embeddings, Ähnlichkeiten, Cluster, Kanten
- erzeugt **beschreibende Artefakte**
- trifft **keine autonomen Entscheidungen**
- passt keine Cutoffs selbstständig an

### hausKI (Entscheidung)
- wertet semantAH-Artefakte aus
- entscheidet über:
  - aktive Cutoff-Profile
  - Auto-Link-Freigaben
  - Safe-Mode-Umschaltungen
- publiziert `policy.decisions.v1`

### heimlern (Lernen)
- analysiert Accept/Reject-Feedback
- erkennt systematische Fehlannahmen
- erzeugt `policy.feedback.v1`

**Grundregel:**
semantAH misst. hausKI entscheidet. heimlern lernt.
Alles andere gilt als Architekturdrift.

### 4.4 Feedback-Loop implementieren

semantAH soll sich selbst optimieren:
1.  **Messen:** Metriken wie Coverage, Graph-Dichte und „verwaiste Knoten“ als Snapshot speichern.
2.  **Bewerten:** Policies (`policy/feedback-loop.v1.yml`) definieren Schwellwerte (OK/Warnung/Kritisch).
3.  **Tunen:** Automatische Anpassung von Cutoffs oder Boosts basierend auf den Messwerten durch HausKI-Komponenten.

### 4.5 Knowledge Observatory nutzen

Das Observatory liefert objektive Daten zur Bewertung:
*   **Gaps & Drift:** Erkennung leerer Namespaces und Überwachung von Modellwechseln (`model_revision`).
*   **Provenienz:** Sicherstellen, dass jeder Embedding-Request gültige `source_ref` und `producer` Daten enthält.

### 4.6 Qualitätssicherung und Erweiterungen

*   **Duplicate-Detection:** Warnung bei Cosine-Similarity ≥ 0.97 (Near-Duplicate).
*   **Explainability:** `why`-Felder in Kanten speichern (z. B. „shared keyphrase“, „same cluster“), abrufbar via „Explain-this-link“ in Obsidian.
*   **Session-Context:** Recency-Boost (+0.02) für aktive Dateien und `relations_lock: true` im Frontmatter zum Schutz vor Auto-Edits.
*   **Observability:** Grafana/Loki/Tempo zur Überwachung von Durchsatz und Latenzen.

## 5. Zusammenfassung

semantAH lässt sich nicht mit einem einzelnen Parameter „schneller“ machen. Es wird zu einem verständigen Organ, wenn **technische Robustheit** (ANN-Index, parallele Pipeline, Persistenz) mit **semantischer Intelligenz** (hochwertige Embeddings, differenzierte Ranking-Regeln, Metadaten-Nutzung) und **selbstkorrigierenden Mechanismen** (Feedback-Loop, Observatory, QA) kombiniert wird.

Durch die Umsetzung der hier beschriebenen Maßnahmen entsteht eine Architektur, die kontextreiche, nachvollziehbare Beziehungen erstellt, skalierbar bleibt und sich kontinuierlich an den wachsenden Wissensbestand anpasst.
