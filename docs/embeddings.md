# Embeddings

Die aktuelle Embedding-Schicht besteht aus zwei getrennten Ebenen:

- `crates/embeddings` definiert den `Embedder`-Trait und den implementierten Ollama-Backendpfad.
- `indexd` nutzt einen optionalen Embedder für serverseitige Texteinbettung und hält
  normalisierte Vektoren im `VectorStore`.

Historische System- und Vault-Blaupausen sind keine Quelle für den heutigen Implementierungsstand.
Maßgeblich sind der aktuelle Code sowie
[`indexd-architecture.md`](indexd-architecture.md),
[`indexd-api.md`](indexd-api.md) und
[`config-reference.md`](config-reference.md).

## Provider und Laufzeitkonfiguration

Der `Embedder`-Trait in `crates/embeddings/src/lib.rs` definiert Batch-Einbettung,
Dimension, Provider-ID und Modellversion. Implementiert ist derzeit `OllamaEmbedder`.

Für `indexd` wird der optionale serverseitige Embedder über Umgebungsvariablen
konfiguriert:

- `INDEXD_EMBEDDER_PROVIDER=ollama`
- `INDEXD_EMBEDDER_BASE_URL` (Standard: `http://127.0.0.1:11434`)
- `INDEXD_EMBEDDER_MODEL` (Standard: `nomic-embed-text`)
- `INDEXD_EMBEDDER_DIM` (Standard: `768`)

Andere Provider sind im aktuellen `indexd`-Pfad nicht implementiert. Die Felder
`embedder.*` in `semantah.yml` sind weiterhin Ziel-/Stub-Konfiguration und werden
nicht als Laufzeitquelle von `indexd` verwendet; siehe
[`config-reference.md`](config-reference.md).

## Dimensionen und Normalisierung

Die konfigurierte Embedder-Dimension muss zu den erzeugten Vektoren passen.
Der `VectorStore` setzt bei der ersten Einfügung die erwartete Dimension und weist
spätere Vektoren mit abweichender Dimension zurück.

Gespeicherte Vektoren werden beim Upsert auf Einheitslänge normalisiert. Query-Vektoren
werden vor dem Ranking ebenfalls normalisiert. Die aktuelle Suche ist eine exakte
Cosinus-Suche innerhalb eines Namespace; Details stehen in
[`indexd-architecture.md`](indexd-architecture.md).

Die Python-Datei `tools/build_index.py` ist derzeit nur ein Stub. Sie erzeugt eine
Platzhalterdatei unter `.gewebe/embeddings.parquet` und belegt keine produktive
Sentence-Transformers-Pipeline.

## Artefakte und Persistenz

Es gibt aktuell zwei unterschiedliche Speicherpfade, die nicht verwechselt werden dürfen:

1. **Pipeline-Artefakt:** `tools/build_index.py` bzw. nachgelagerte Tools verwenden
   `.gewebe/embeddings.parquet` als Pipeline-/Übergabepfad. `scripts/push_index.py`
   kann daraus Batches für `indexd` bilden.
2. **indexd-Persistenz:** Wenn `INDEXD_DB_PATH` gesetzt ist, lädt `indexd` beim Start
   einen JSONL-Snapshot und schreibt den Store beim geordneten Shutdown atomar zurück.
   Das ist keine kontinuierliche Durability- oder Datenbankgarantie.

Namespaces werden im `VectorStore` logisch getrennt. Der persistierte JSONL-Datensatz
enthält `namespace`, `doc_id`, `chunk_id`, `embedding` und `meta`; siehe
[`indexd-architecture.md`](indexd-architecture.md).

## Aktuelle Datenpfade

### Vorberechnete Embeddings

1. Ein Producer erzeugt Embeddings oder ein Pipeline-Artefakt.
2. `scripts/push_index.py` gruppiert vorhandene Daten nach Namespace und Dokument.
3. `POST /index/upsert` übergibt Chunks und Embeddings an `indexd`.
4. `VectorStore` prüft die Dimension und normalisiert die Vektoren vor der Ablage.

### Serverseitige Texteinbettung

Wenn der Ollama-Embedder für `indexd` konfiguriert ist:

1. `POST /embed/text` erzeugt ein versioniertes Embedding mit Provenienz.
2. Die zulässigen Namespaces und das Antwortformat sind in
   [`indexd-api.md`](indexd-api.md) dokumentiert.
3. Suche kann bei fehlendem explizitem Query-Vektor ebenfalls den konfigurierten
   Server-Embedder verwenden.

Damit bleiben Implementierungsstand, Konfigurationsstatus und Persistenzgrenzen
voneinander getrennt und gegen aktuelle Primärquellen prüfbar.
