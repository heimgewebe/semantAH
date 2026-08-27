//! Embedder abstractions and implementations for semantAH.

use anyhow::{anyhow, Result};
use async_trait::async_trait;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::{future::Future, sync::Arc, time::Duration, time::Instant};
use tokio::sync::Mutex;

const UNKNOWN_VERSION_RETRY_BACKOFF: Duration = Duration::from_secs(30);

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
    version_cache: Arc<Mutex<VersionCache>>,
}

enum VersionCache {
    Empty,
    Unknown { retry_after: Instant },
    Digest(String),
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
            version_cache: Arc::new(Mutex::new(VersionCache::Empty)),
        }
    }

    async fn fetch_version_digest(&self) -> Option<String> {
        // Try /api/show first to get model details.
        let response = self
            .client
            .post(format!("{}/api/show", self.url))
            .json(&OllamaShowRequest { name: &self.model })
            .send()
            .await;

        if let Ok(resp) = response {
            if resp.status().is_success() {
                if let Ok(body) = resp.json::<serde_json::Value>().await {
                    // Some Ollama versions return the digest directly from /api/show.
                    if let Some(digest) = body.get("digest").and_then(|s| s.as_str()) {
                        return Some(digest.to_string());
                    }
                }
            }
        }

        // Fallback: list all tags and find our model.
        let response = self
            .client
            .get(format!("{}/api/tags", self.url))
            .send()
            .await;

        if let Ok(resp) = response {
            if resp.status().is_success() {
                if let Ok(body) = resp.json::<serde_json::Value>().await {
                    if let Some(models) = body.get("models").and_then(|v| v.as_array()) {
                        let latest_model = format!("{}:latest", self.model);
                        for model in models {
                            if let Some(name) = model.get("name").and_then(|s| s.as_str()) {
                                if name == self.model || name == latest_model {
                                    if let Some(digest) =
                                        model.get("digest").and_then(|s| s.as_str())
                                    {
                                        return Some(digest.to_string());
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        None
    }

    async fn resolve_version<F, Fut>(&self, fetch_digest: F) -> String
    where
        F: FnOnce() -> Fut,
        Fut: Future<Output = Option<String>>,
    {
        // Keep the lock while querying so concurrent callers cannot trigger duplicate retries.
        let mut cache = self.version_cache.lock().await;
        match &*cache {
            VersionCache::Digest(digest) => return digest.clone(),
            VersionCache::Unknown { retry_after } if Instant::now() < *retry_after => {
                return format!("{}:unknown", self.model);
            }
            VersionCache::Empty | VersionCache::Unknown { .. } => {}
        }

        if let Some(digest) = fetch_digest().await {
            *cache = VersionCache::Digest(digest.clone());
            return digest;
        }

        *cache = VersionCache::Unknown {
            retry_after: Instant::now() + UNKNOWN_VERSION_RETRY_BACKOFF,
        };
        format!("{}:unknown", self.model)
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
            .post(format!("{}/api/embed", self.url))
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
        Ok(self.resolve_version(|| self.fetch_version_digest()).await)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};

    fn test_embedder() -> OllamaEmbedder {
        OllamaEmbedder::new(OllamaConfig {
            base_url: "http://localhost:11434".to_string(),
            model: "nomic-embed-text".to_string(),
            dim: 768,
        })
    }

    async fn expire_unknown_backoff(embedder: &OllamaEmbedder) {
        let mut cache = embedder.version_cache.lock().await;
        match &mut *cache {
            VersionCache::Unknown { retry_after } => {
                *retry_after = Instant::now()
                    .checked_sub(Duration::from_secs(1))
                    .expect("test instant should support subtracting one second");
            }
            VersionCache::Empty => panic!("expected an unknown version, cache was empty"),
            VersionCache::Digest(digest) => {
                panic!("expected an unknown version, cache held {digest}")
            }
        }
    }

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
                [1.0, 2.0],
                [3.0, 4.0]
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

    #[tokio::test]
    async fn unknown_version_recovers_to_digest_after_backoff() {
        let embedder = test_embedder();
        let provider_checks = AtomicUsize::new(0);

        assert_eq!(
            embedder
                .resolve_version(|| async {
                    provider_checks.fetch_add(1, Ordering::SeqCst);
                    None
                })
                .await,
            "nomic-embed-text:unknown"
        );
        assert_eq!(provider_checks.load(Ordering::SeqCst), 1);

        expire_unknown_backoff(&embedder).await;

        assert_eq!(
            embedder
                .resolve_version(|| async {
                    provider_checks.fetch_add(1, Ordering::SeqCst);
                    Some("sha256:recovered".to_string())
                })
                .await,
            "sha256:recovered"
        );
        assert_eq!(provider_checks.load(Ordering::SeqCst), 2);
    }

    #[tokio::test]
    async fn unknown_version_backoff_suppresses_repeated_provider_queries() {
        let embedder = test_embedder();
        let provider_checks = AtomicUsize::new(0);

        assert_eq!(
            embedder
                .resolve_version(|| async {
                    provider_checks.fetch_add(1, Ordering::SeqCst);
                    None
                })
                .await,
            "nomic-embed-text:unknown"
        );
        for _ in 0..5 {
            assert_eq!(
                embedder
                    .resolve_version(|| async {
                        provider_checks.fetch_add(1, Ordering::SeqCst);
                        None
                    })
                    .await,
                "nomic-embed-text:unknown"
            );
        }

        assert_eq!(provider_checks.load(Ordering::SeqCst), 1);
    }

    #[tokio::test]
    async fn successful_version_digest_remains_cached() {
        let embedder = test_embedder();
        let provider_checks = AtomicUsize::new(0);

        assert_eq!(
            embedder
                .resolve_version(|| async {
                    provider_checks.fetch_add(1, Ordering::SeqCst);
                    Some("sha256:stable".to_string())
                })
                .await,
            "sha256:stable"
        );
        assert_eq!(
            embedder
                .resolve_version(|| async {
                    provider_checks.fetch_add(1, Ordering::SeqCst);
                    Some("sha256:changed".to_string())
                })
                .await,
            "sha256:stable"
        );
        assert_eq!(provider_checks.load(Ordering::SeqCst), 1);
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
