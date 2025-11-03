### 📄 crates/embeddings/src/lib.rs

**Größe:** 6 KB | **md5:** `e6207eb43a0420c114301081342651b1`

```rust
//! Embedder abstractions and implementations for semantAH.

use anyhow::{anyhow, Result};
use async_trait::async_trait;
use reqwest::Client;
use serde::{Deserialize, Serialize};

/// Public trait that every embedder implementation must fulfill.
#[async_trait]
pub trait Embedder: Send + Sync {
    /// Embed a batch of texts and return a vector of embedding vectors.
    async fn embed(&self, texts: &[String]) -> Result<Vec<Vec<f32>>>;

    /// The dimensionality of the returned embeddings.
    fn dim(&self) -> usize;

    /// Short identifier (e.g. `"ollama"`).
    fn id(&self) -> &'static str;
}

/// Configuration for the Ollama embedder backend.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OllamaConfig {
    pub base_url: String,
    pub model: String,
    pub dim: usize,
}

/// Simple HTTP client for the Ollama embeddings endpoint.
#[derive(Clone)]
pub struct OllamaEmbedder {
    client: Client,
    url: String,
    model: String,
    dim: usize,
}

impl OllamaEmbedder {
    /// Build a new embedder from configuration.
    pub fn new(config: OllamaConfig) -> Self {
        let OllamaConfig {
            base_url,
            model,
            dim,
        } = config;
        Self {
            client: Client::new(),
            url: base_url,
            model,
            dim,
        }
    }
}

#[derive(Debug, Serialize)]
struct OllamaRequest<'a> {
    model: &'a str,
    input: &'a [String],
}

#[derive(Debug, Deserialize)]
struct OllamaEmbeddingRow {
    embedding: Vec<f32>,
}

#[derive(Debug, Deserialize)]
struct OllamaResponse {
    embedding: Option<Vec<f32>>,
    embeddings: Option<Vec<OllamaEmbeddingRow>>,
}

impl OllamaResponse {
    fn into_embeddings(self) -> Result<Vec<Vec<f32>>> {
        if let Some(embeddings) = self.embeddings {
            return Ok(embeddings.into_iter().map(|row| row.embedding).collect());
        }

        if let Some(embedding) = self.embedding {
            return Ok(vec![embedding]);
        }

        Err(anyhow!("ollama response did not contain embeddings"))
    }
}

fn validate_embeddings(
    expected_count: usize,
    embeddings: &[Vec<f32>],
    expected_dim: usize,
) -> Result<()> {
    if embeddings.len() != expected_count {
        return Err(anyhow!(
            "ollama returned {} embeddings for {} input texts",
            embeddings.len(),
            expected_count
        ));
    }

    if embeddings.iter().any(|row| row.len() != expected_dim) {
        return Err(anyhow!("unexpected embedding dimensionality"));
    }

    Ok(())
}

#[async_trait]
impl Embedder for OllamaEmbedder {
    async fn embed(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        if texts.is_empty() {
            return Ok(Vec::new());
        }

        let response = self
            .client
            .post(format!("{}/api/embeddings", self.url))
            .json(&OllamaRequest {
                model: &self.model,
                input: texts,
            })
            .send()
            .await?;

        if !response.status().is_success() {
            return Err(anyhow!(
                "ollama responded with status {}",
                response.status()
            ));
        }

        let body: OllamaResponse = response.json().await?;
        let embeddings = body.into_embeddings()?;

        validate_embeddings(texts.len(), &embeddings, self.dim)?;

        Ok(embeddings)
    }

    fn dim(&self) -> usize {
        self.dim
    }

    fn id(&self) -> &'static str {
        "ollama"
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_single_embedding_response() {
        let json = serde_json::json!({
            "embedding": [0.1, 0.2, 0.3],
            "model": "nomic-embed-text",
        });

        let response: OllamaResponse = serde_json::from_value(json).unwrap();
        let embeddings = response.into_embeddings().unwrap();

        assert_eq!(embeddings.len(), 1);
        assert_eq!(embeddings[0], vec![0.1, 0.2, 0.3]);
    }

    #[test]
    fn parses_batch_embedding_response() {
        let json = serde_json::json!({
            "embeddings": [
                { "embedding": [1.0, 2.0], "text": "first" },
                { "embedding": [3.0, 4.0], "text": "second" }
            ],
        });

        let response: OllamaResponse = serde_json::from_value(json).unwrap();
        let embeddings = response.into_embeddings().unwrap();

        assert_eq!(embeddings, vec![vec![1.0, 2.0], vec![3.0, 4.0]]);
    }

    #[tokio::test]
    async fn empty_batch_returns_empty() {
        let embedder = OllamaEmbedder::new(OllamaConfig {
            base_url: "http://localhost:11434".into(),
            model: "dummy".into(),
            dim: 1536,
        });

        let result = embedder.embed(&[]).await.unwrap();
        assert!(result.is_empty());
    }

    #[test]
    fn validate_embeddings_rejects_count_mismatch() {
        let embeddings = vec![vec![1.0, 2.0]];
        let err = validate_embeddings(2, &embeddings, 2).expect_err("expected count mismatch");
        assert!(
            err.to_string()
                .contains("ollama returned 1 embeddings for 2 input texts"),
            "unexpected error message: {}",
            err
        );
    }

    #[test]
    fn validate_embeddings_rejects_dim_mismatch() {
        let embeddings = vec![vec![1.0, 2.0], vec![3.0]];
        let err = validate_embeddings(2, &embeddings, 2).expect_err("expected dim mismatch");
        assert!(
            err.to_string()
                .contains("unexpected embedding dimensionality"),
            "unexpected error message: {}",
            err
        );
    }
}
```

