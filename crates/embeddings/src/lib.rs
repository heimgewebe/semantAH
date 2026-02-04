//! Embedder abstractions and implementations for semantAH.

use anyhow::{anyhow, Result};
use async_trait::async_trait;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use tokio::sync::OnceCell;

/// Public trait that every embedder implementation must fulfill.
#[async_trait]
pub trait Embedder: Send + Sync {
    /// Embed a batch of texts and return a vector of embedding vectors.
    async fn embed(&self, texts: &[&str]) -> Result<Vec<Vec<f32>>>;

    /// The dimensionality of the returned embeddings.
    fn dim(&self) -> usize;

    /// Short identifier (e.g. `"ollama"`).
    fn id(&self) -> &'static str;

    /// Return the version or hash of the model.
    async fn version(&self) -> Result<String>;
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
    version_cache: OnceCell<String>,
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
            version_cache: OnceCell::new(),
        }
    }
}

#[derive(Debug, Serialize)]
struct OllamaShowRequest<'a> {
    name: &'a str,
}

#[derive(Debug, Serialize)]
struct OllamaRequest<'a> {
    model: &'a str,
    input: &'a [&'a str],
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
    async fn embed(&self, texts: &[&str]) -> Result<Vec<Vec<f32>>> {
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

        let status = response.status();
        if !status.is_success() {
            let message = response.text().await.unwrap_or_default();
            let detail = if message.trim().is_empty() {
                String::new()
            } else {
                format!(": {}", message)
            };
            return Err(anyhow!("ollama responded with status {}{}", status, detail));
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

    async fn version(&self) -> Result<String> {
        let version = self
            .version_cache
            .get_or_init(|| async {
                // Try /api/show first to get model details
                let response = self
                    .client
                    .post(format!("{}/api/show", self.url))
                    .json(&OllamaShowRequest { name: &self.model })
                    .send()
                    .await;

                if let Ok(resp) = response {
                    if resp.status().is_success() {
                        if let Ok(body) = resp.json::<serde_json::Value>().await {
                            // Check for details.parent_model (often contains the hash/digest concept in some form)
                            // but standard API returns `details` object.
                            // However, `digest` is usually in /api/tags.
                            // Some versions of Ollama return `digest` in /api/show response.
                            if let Some(digest) = body.get("digest").and_then(|s| s.as_str()) {
                                return digest.to_string();
                            }
                        }
                    }
                }

                // Fallback: list all tags and find our model
                let response = self
                    .client
                    .get(format!("{}/api/tags", self.url))
                    .send()
                    .await;

                if let Ok(resp) = response {
                    if resp.status().is_success() {
                        if let Ok(body) = resp.json::<serde_json::Value>().await {
                            if let Some(models) = body.get("models").and_then(|v| v.as_array()) {
                                for model in models {
                                    if let Some(name) = model.get("name").and_then(|s| s.as_str()) {
                                        // Match exact name or name:latest
                                        if name == self.model
                                            || name == format!("{}:latest", self.model)
                                        {
                                            if let Some(digest) =
                                                model.get("digest").and_then(|s| s.as_str())
                                            {
                                                return digest.to_string();
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // If we can't find the hash, return a fallback that indicates checked but unknown
                // This maintains the previous behavior effectively but allows upgrade.
                // Note: We cache this "unknown" result to avoid flapping on transient errors;
                // a service restart is required to refresh the cache.
                format!("{}:unknown", self.model)
            })
            .await;

        Ok(version.clone())
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
