# Konfigurationsreferenz (`semantah.yml`)

`semantah.yml` dient als zentrale Drehscheibe für die Pipeline-Konfiguration. Die Datei ist aktuell ein **Platzhalter** – die angebundenen Skripte und Dienste nutzen die Konfiguration noch nicht, sondern arbeiten mit fest kodierten Pfaden und Standardwerten.

Die folgende Tabelle dokumentiert das Zielschema und den aktuellen Implementierungsstatus.

| Feld | Typ | Beschreibung | Standard | Status |
| --- | --- | --- | --- | --- |
| `vault_path` | Pfad | Stamm des Obsidian-Vaults, aus dem Markdown-Dateien gelesen werden. | – (Pflichtfeld) | Stub (Skripte verwenden derzeit Beispielpfade) |
| `out_dir` | Pfad | Zielverzeichnis für Artefakte wie Embeddings, Graph und Reports. | `.gewebe` | Stub (Skripte schreiben hartkodiert nach `.gewebe/`) |
| `embedder.provider` | String | Kennung des Embedding-Providers (`ollama`, `openai`, …). | `ollama` | Stub |
| `embedder.model` | String | Modellname/Identifier, der an den Provider übergeben wird. | `nomic-embed-text` | Stub |
| `embedder.base_url` | URL | Optional: überschreibt die Basis-URL für lokale Provider (z. B. `http://localhost:11434`). | `http://localhost:11434` | Stub |
| `index.top_k` | Integer | Anzahl Treffer, die bei Suchen (`/index/search`) zurückgegeben werden. | `20` | Stub (HTTP-Stub verwendet Payload `k`) |
| `index.persist_path` | Pfad | Ablageort für den persistenten Index. | – | geplant |
| `graph.cutoffs.min_cooccur` | Integer | Minimale Co-Vorkommnisse zweier Notizen, um eine Kante zu erzeugen. | `2` | Stub |
| `graph.cutoffs.min_weight` | Float | Mindestgewicht für gewichtete Kanten. | `0.15` | Stub |
| `graph.cutoffs.min_similarity` | Float | Alternative Metrik, falls Similarity-Schwelle verwendet wird. | deaktiviert | Stub |
| `related.write_back` | Bool | Schreibt Related-Blöcke in Markdown-Dateien. | `false` | Stub (Skript akzeptiert später diesen Schalter) |
| `related.block_heading` | String | Überschrift des Related-Blocks. | `Related` | geplant |
| `telemetry.enabled` | Bool | Aktiviert OpenTelemetry-Export für `indexd` und Pipeline-Skripte. | `false` | geplant |
| `telemetry.endpoint` | URL | Ziel-Endpunkt für OTLP-Export (`http://localhost:4317`). | `http://localhost:4317` | geplant |
| `alerts.latency.index_topk20_ms` | Integer | Schwellwert in Millisekunden für Benachrichtigungen aus der Observability-Stack. | `60` | geplant |

## Beispielkonfiguration
```yaml
vault_path: /home/user/Vaults/knowledge
out_dir: .gewebe
embedder:
  provider: ollama
  model: nomic-embed-text
  base_url: http://localhost:11434
index:
  top_k: 20
  persist_path: ~/.local/state/semantah/index
graph:
  cutoffs:
    min_cooccur: 2
    min_weight: 0.15
related:
  write_back: true
  block_heading: "Ähnliche Notizen"
telemetry:
  enabled: false
alerts:
  latency:
    index_topk20_ms: 75
```

Nutze `examples/semantah.example.yml` als Ausgangspunkt und erweitere die Datei entsprechend deiner Umgebung. Pflichtfelder sollten im CI/Deployment validiert werden, bevor die Pipeline gestartet wird.
