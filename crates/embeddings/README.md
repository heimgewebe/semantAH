# `embeddings` crate

Die `embeddings`-Crate bündelt sämtliche Embedder-Abstraktionen für semantAH. Sie stellt einen `Embedder`-Trait bereit und enthält aktuell eine Implementierung für [Ollama](https://ollama.ai/).

## Aufbau
- `Embedder`-Trait (`src/lib.rs`): definiert asynchrone Batch-Einbettung, Dimensionsabfrage und eine ID des Providers.
- `OllamaEmbedder`: schlanker HTTP-Client, der das Ollama-Embeddings-API (`/api/embeddings`) anspricht.
- Hilfsfunktionen zur Validierung von Antwortformat und Dimensionalität.

## Nutzung
```rust
use embeddings::{Embedder, OllamaConfig, OllamaEmbedder};

# async fn example() -> anyhow::Result<()> {
let embedder = OllamaEmbedder::new(OllamaConfig {
    base_url: "http://localhost:11434".into(),
    model: "nomic-embed-text".into(),
    dim: 768,
});

let vectors = embedder.embed(&["Notiz A".to_string(), "Notiz B".to_string()]).await?;
assert_eq!(vectors.len(), 2);
# Ok(())
# }
```

## Fehlerbehandlung
- Responses ohne Embeddings lösen einen `anyhow::Error` mit einer sprechenden Meldung aus.
- Dimensionalitätskonflikte werden früh erkannt (`unexpected embedding dimensionality`).

## Tests
- JSON-Parsing von Einzel-/Batch-Antworten.
- Sicherstellung, dass leere Batches keine Requests erzeugen.
- Validierung auf fehlerhafte Dimensionalität.

Für weitere Backend-Implementierungen kann der Trait erweitert und via Feature-Gates integriert werden.
