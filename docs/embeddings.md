# Embeddings

Die Embedding-Schicht übersetzt Notiz-Chunks in normalisierte Vektoren, die vom Indexdienst
(`indexd`) und den Graph-Builders weiterverarbeitet werden. Dieses Dokument fasst die
Derivation (Provider & Dimension), die Normalisierung und die Persistenzpfade zusammen.

## Provider & Konfiguration

| Provider                | Transport                                   | Konfiguration                       | Status |
|------------------------|----------------------------------------------|-------------------------------------|--------|
| `ollama` (Default)     | HTTP gegen einen lokalen Ollama-Dienst (`/api/embeddings`). | `semantah.yml` → `embedder.provider: ollama`, `embedder.model: nomic-embed-text` (oder anderes Ollama-Embedding-Modell). | Implementiert |
| `openai` (geplant)     | HTTPS gegen das OpenAI Embeddings-API.       | `semantah.yml` → `embedder.provider: openai`, plus API-Key via Environment. | Konzeptphase |

- Weitere Provider werden über das `crates/embeddings`-Crate abstrahiert; jeder Provider
  implementiert denselben `Embedder`-Trait (siehe `docs/semantAH brainstorm.md`).
- Die Konfiguration befindet sich zentral in `semantah.yml`. Für den lokalen Betrieb genügt
  es, den Ollama-Endpunkt laufen zu lassen und ggf. das Modell anzupassen.

```yaml
embedder:
  provider: ollama
  model: nomic-embed-text
```

## Dimensionen & Normalisierung

- Die Dimensionen der Vektoren richten sich nach dem gewählten Modell. Das
  Standardmodell `nomic-embed-text` liefert heute typischerweise
  768-dimensionale Vektoren; bei einem Modellwechsel passt sich die Dimension
  entsprechend an.
- Vor der Persistenz erfolgt eine L2-Normalisierung, damit der Index eine
  Cosine-Similarity-Suche direkt auf den gespeicherten Vektoren durchführen kann. Die
  aktuelle Python-Pipeline ruft `sentence-transformers` mit
  `normalize_embeddings=True` auf und erzeugt so Einheitsvektoren (siehe
  Abschnitt „Embedding-Pipeline" in `docs/semantAH.md`).

## Persistenzpfade

- Embeddings werden als Parquet-Datei unter `.gewebe/embeddings.parquet`
  abgelegt. Die Datei enthält pro Zeile `id`, `path`, `chunk_id`, `text` und den
  zugehörigen Vektor (siehe Abschnitt „Dateiaufbau“ in `docs/semantAH.md`).
- Der Pfad ist über `semantah.yml → out_dir` konfigurierbar. Standard ist `.gewebe` im
  Projektverzeichnis (`semantah.yml`, Abschnitt „Allgemeine Einstellungen“).
- Pro Namespace kann eine separate Datei geschrieben werden (z. B. `.gewebe/vault/embeddings.parquet`).
  Die geplanten Rust-Dienste spiegeln diese Struktur wider, indem sie pro Namespace eigene
  Buckets anlegen (siehe `docs/hauski.md`, Abschnitt „Persistenz“).

## Lifecycle

1. Die Obsidian-Adapter zerlegen Notizen in Chunks.
2. Der Embeddings-Dienst fragt den konfigurierten Provider an und erhält die Rohvektoren.
3. Die Rohvektoren werden normalisiert und in `.gewebe/…/embeddings.parquet` persistiert.
4. `indexd` liest dieselben Dateien ein bzw. erhält Embeddings über die API und legt sie
   namespacesepariert ab (siehe `docs/semantAH.md`, Abschnitt „Indexdienst“ sowie
   `docs/indexd-api.md`, Abschnitt „Embeddings-Endpunkte“).

Damit ist nachvollziehbar, welcher Provider genutzt wird, welche Vektorlänge entsteht und wo
die Daten auf der Platte liegen.
