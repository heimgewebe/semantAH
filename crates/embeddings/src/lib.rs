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
struct OllamaResponse {
    embedding: Option<Vec<f32>>,
    embeddings: Option<Vec<Vec<f32>>>,
}

impl OllamaResponse {
    fn into_embeddings(self) -> Result<Vec<Vec<f32>>> {
        if let Some(embeddings) = self.embeddings {
            return Ok(embeddings);
        }

        if let Some(embedding) = self.embedding {
            return Ok(vec![embedding]);
        }

        Err(anyhow!("ollama response did not contain embeddings"))
    }
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

        if embeddings.iter().any(|row| row.len() != self.dim) {
            return Err(anyhow!("unexpected embedding dimensionality"));
        }

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
            "embeddings": [[1.0, 2.0], [3.0, 4.0]],
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
}
