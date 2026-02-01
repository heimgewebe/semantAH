use std::sync::Arc;

use axum::{
    extract::State,
    http::StatusCode,
    routing::post,
    Json, Router,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tracing::{debug, info};

use crate::AppState;

/// Custom JSON extractor that returns consistent error format.
///
/// Wraps Axum's Json extractor to ensure all deserialization errors
/// return JSON format `{"error": "..."}` instead of plain text.
pub struct ApiJson<T>(pub T);

#[axum::async_trait]
impl<S, T> axum::extract::FromRequest<S> for ApiJson<T>
where
    T: serde::de::DeserializeOwned,
    S: Send + Sync,
{
    type Rejection = (StatusCode, Json<Value>);

    async fn from_request(
        req: axum::extract::Request,
        state: &S,
    ) -> Result<Self, Self::Rejection> {
        match Json::<T>::from_request(req, state).await {
            Ok(Json(value)) => Ok(ApiJson(value)),
            Err(rejection) => {
                // Convert Axum's rejection to our consistent JSON error format
                // Use status code from rejection for robust classification
                let status = rejection.status();
                let error_message = rejection.body_text();
                
                // Map status codes to appropriate responses
                let (final_status, message) = match status {
                    StatusCode::UNSUPPORTED_MEDIA_TYPE => {
                        // Missing or invalid Content-Type header
                        (
                            status,
                            "Missing or invalid Content-Type header. Expected 'application/json'"
                                .to_string(),
                        )
                    }
                    StatusCode::PAYLOAD_TOO_LARGE => {
                        // Request body too large
                        (status, format!("Request body too large: {}", error_message))
                    }
                    StatusCode::BAD_REQUEST => {
                        // JSON syntax error or other bad request
                        (status, error_message)
                    }
                    StatusCode::UNPROCESSABLE_ENTITY => {
                        // Deserialization/validation error (e.g., wrong type, missing field, invalid enum)
                        (status, error_message)
                    }
                    _ => {
                        // Fallback for any other rejection status
                        (status, error_message)
                    }
                };
                
                let body = json!({
                    "error": message,
                });
                
                Err((final_status, Json(body)))
            }
        }
    }
}

/// Request to insert or update document chunks with embeddings.
///
/// All chunks for a document ID are replaced atomically. If any chunk fails
/// validation, the entire operation is rolled back.
#[derive(Debug, Deserialize)]
pub struct UpsertRequest {
    /// Unique identifier for the document.
    pub doc_id: String,
    /// Logical namespace to isolate this document (e.g., "vault" or "notes").
    pub namespace: String,
    /// List of chunks to be indexed. Each must contain an embedding.
    pub chunks: Vec<ChunkPayload>,
}

/// A single chunk of a document with its embedding and metadata.
#[derive(Debug, Deserialize)]
pub struct ChunkPayload {
    /// Unique identifier for this chunk within the document.
    pub id: String,
    /// Text content (stored for reference but not currently indexed).
    #[serde(rename = "text")]
    _text: String,
    /// Metadata must include an "embedding" array and may include a "snippet" string.
    #[serde(default = "default_meta")]
    pub meta: Value,
}

/// Request to delete all chunks associated with a document.
#[derive(Debug, Deserialize)]
pub struct DeleteRequest {
    /// Document identifier to delete.
    pub doc_id: String,
    /// Namespace where the document is stored.
    pub namespace: String,
}

/// Request to search for similar chunks using vector similarity.
///
/// Embeddings can be provided in three ways (in order of precedence):
/// 1. `query.meta.embedding` - Preferred location
/// 2. `embedding` - Top-level field
/// 3. `meta.embedding` - Legacy location
///
/// If no embedding is provided and an embedder is configured, the query text
/// will be embedded automatically.
#[derive(Debug, Deserialize)]
pub struct SearchRequest {
    /// Query text and optional metadata.
    pub query: QueryPayload,
    /// Maximum number of results to return (default: 10).
    #[serde(default = "default_k")]
    pub k: u32,
    /// Namespace to search within.
    pub namespace: String,
    /// Optional filters to apply (not yet implemented).
    #[serde(default)]
    pub filters: Option<Value>,
    /// Optional top-level embedding array.
    #[serde(default)]
    pub embedding: Option<Vec<f32>>,
    /// Legacy location for embedding. Use `query.meta.embedding` or `embedding` instead.
    #[serde(default)]
    pub meta: Option<Value>,
}

/// Query payload that can be either plain text or text with metadata.
///
/// The untagged serde representation allows clients to send either:
/// - A simple string: `"hello world"`
/// - An object with text and metadata: `{"text": "hello", "meta": {"embedding": [...]}}`
#[derive(Debug, Deserialize)]
#[serde(untagged)]
pub enum QueryPayload {
    /// Plain text query without metadata.
    Text(String),
    /// Query text with optional metadata (including embedding).
    WithMeta {
        text: String,
        #[serde(default = "default_meta")]
        meta: Value,
    },
}

impl QueryPayload {
    /// Extract the text portion of the query regardless of variant.
    fn text(&self) -> &str {
        match self {
            QueryPayload::Text(text) => text,
            QueryPayload::WithMeta { text, .. } => text,
        }
    }
}

/// Response containing search results ordered by similarity score (descending).
#[derive(Debug, Serialize)]
pub struct SearchResponse {
    /// List of matching chunks, ordered by score (highest first).
    pub results: Vec<SearchHit>,
}

/// A single search result representing a matching chunk.
#[derive(Debug, Serialize)]
pub struct SearchHit {
    /// Document identifier.
    pub doc_id: String,
    /// Chunk identifier within the document.
    pub chunk_id: String,
    /// Cosine similarity score (0.0 to 1.0, where 1.0 is perfect match).
    pub score: f32,
    /// Text snippet from the chunk metadata.
    pub snippet: String,
    /// Reserved for future use (e.g., explaining why this result matched).
    pub rationale: Vec<String>,
}

/// Allowed namespace values for embeddings.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Namespace {
    Chronik,
    Osctx,
    Docs,
    Code,
    Insights,
}

impl Namespace {
    /// Returns the string representation of the namespace.
    pub fn as_str(&self) -> &'static str {
        match self {
            Namespace::Chronik => "chronik",
            Namespace::Osctx => "osctx",
            Namespace::Docs => "docs",
            Namespace::Code => "code",
            Namespace::Insights => "insights",
        }
    }
}

impl std::fmt::Display for Namespace {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

/// Request to generate an embedding for text with full provenance metadata.
#[derive(Debug, Deserialize)]
pub struct EmbedTextRequest {
    /// Text content to embed.
    pub text: String,
    /// Logical namespace (chronik, osctx, docs, code, insights).
    pub namespace: Namespace,
    /// Reference to source (event ID, file path, hash, etc.).
    pub source_ref: String,
}

/// Producer constant for all embeddings generated by this service.
const PRODUCER: &str = "semantAH";

/// Response containing a versioned embedding with full provenance.
///
/// Schema-compliant with os.context.text.embed.schema.json
#[derive(Debug, Serialize)]
pub struct EmbedTextResponse {
    /// Unique identifier for this embedding.
    pub embedding_id: String,
    /// Original text that was embedded.
    pub text: String,
    /// Embedding vector (list of floats).
    pub embedding: Vec<f32>,
    /// Model identifier (e.g., 'nomic-embed-text').
    pub embedding_model: String,
    /// Dimensionality of the embedding vector.
    pub embedding_dim: usize,
    /// Model revision or version hash.
    pub model_revision: String,
    /// Timestamp when embedding was generated (ISO-8601).
    pub generated_at: String,
    /// Logical namespace.
    pub namespace: Namespace,
    /// Reference to source.
    pub source_ref: String,
    /// Component that produced this embedding.
    pub producer: &'static str,
    /// Numerical tolerance for reproducibility.
    pub determinism_tolerance: f64,
}

pub fn router(state: Arc<AppState>) -> Router {
    // NOTE: Only API routes here. Base routes (e.g. /healthz) are merged in `indexd::run`
    // (and in Tests explizit), um doppelte Registrierung zu vermeiden.
    Router::new()
        .route("/index/upsert", post(handle_upsert))
        .route("/index/delete", post(handle_delete))
        .route("/index/search", post(handle_search))
        .route("/embed/text", post(handle_embed_text))
        .with_state(state)
}

fn default_k() -> u32 {
    10
}

fn default_meta() -> Value {
    Value::Object(Default::default())
}

async fn handle_upsert(
    State(state): State<Arc<AppState>>,
    ApiJson(payload): ApiJson<UpsertRequest>,
) -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    let chunk_count = payload.chunks.len();
    info!(doc_id = %payload.doc_id, namespace = %payload.namespace, chunks = chunk_count, "received upsert");

    let UpsertRequest {
        doc_id,
        namespace,
        chunks,
    } = payload;

    let initial_dim = {
        let store = state.store.read().await;
        store.dims
    };

    let mut staged = Vec::with_capacity(chunk_count);
    let mut expected_dim = initial_dim;

    for chunk in chunks {
        let ChunkPayload { id, _text: _, meta } = chunk;

        let mut meta = match meta {
            Value::Object(map) => map,
            _ => return Err(bad_request(format!("chunk '{}' meta must be an object", id))),
        };

        let embedding_value = meta
            .remove("embedding")
            .ok_or_else(|| bad_request(format!(
                "chunk '{}' meta must contain an 'embedding' array",
                id
            )))?;

        let vector = parse_embedding(embedding_value)
            .map_err(|err| bad_request(format!("chunk '{}': {}", id, err)))?;

        if let Some(expected) = expected_dim {
            if expected != vector.len() {
                return Err(bad_request(format!(
                    "chunk '{}' embedding dimensionality mismatch: expected {}, got {}",
                    id, expected, vector.len()
                )));
            }
        } else {
            expected_dim = Some(vector.len());
        }

        staged.push((id, vector, Value::Object(meta)));
    }

    let mut store = state.store.write().await;
    if let Some(validated_dim) = expected_dim {
        if let Some(current_dim) = store.dims {
            if current_dim != validated_dim {
                return Err(bad_request(format!(
                    "chunk embedding dimensionality mismatch: expected {current_dim}, got {}",
                    validated_dim
                )));
            }
        }
    }

    store.delete_doc(&namespace, &doc_id);

    for (id, vector, meta) in staged {
        store
            .upsert(&namespace, &doc_id, &id, vector, meta)
            .map_err(|err| bad_request(err.to_string()))?;
    }

    Ok(Json(json!({
        "status": "accepted",
        "chunks": chunk_count,
    })))
}

async fn handle_delete(
    State(state): State<Arc<AppState>>,
    ApiJson(payload): ApiJson<DeleteRequest>,
) -> Json<Value> {
    info!(doc_id = %payload.doc_id, namespace = %payload.namespace, "received delete");

    let mut store = state.store.write().await;
    store.delete_doc(&payload.namespace, &payload.doc_id);

    Json(json!({
        "status": "accepted"
    }))
}

async fn handle_search(
    State(state): State<Arc<AppState>>,
    ApiJson(payload): ApiJson<SearchRequest>,
) -> Result<Json<SearchResponse>, (StatusCode, Json<Value>)> {
    if payload.k == 0 {
        return Err(bad_request("k must be greater than 0"));
    }

    debug!(
        query = %payload.query.text(),
        k = payload.k,
        namespace = %payload.namespace,
        filters = payload
            .filters
            .as_ref()
            .map(|_| "provided")
            .unwrap_or("none"),
        "received search"
    );

    let SearchRequest {
        query,
        k,
        namespace,
        filters,
        embedding,
        meta,
    } = payload;

    let embedder = state.embedder();
    let mut store_dims: Option<usize> = None;

    let (query_text, query_embedding_value) = match query {
        QueryPayload::Text(text) => (text, None),
        QueryPayload::WithMeta { text, meta } => {
            let mut meta_map = match meta {
                Value::Object(map) => map,
                _ => return Err(bad_request("query meta must be an object")),
            };
            let embedding = meta_map.remove("embedding");
            (text, embedding)
        }
    };

    let k = k as usize;
    let filter_value = filters.unwrap_or(Value::Null);

    // Priority: query.meta.embedding > top-level embedding > legacy meta.embedding
    let (embedding, embedding_generated): (Vec<f32>, bool) = if let Some(value) = query_embedding_value {
        (parse_embedding(value).map_err(bad_request)?, false)
    } else if let Some(value) = embedding {
        (value, false)
    } else if let Some(meta) = meta {
        let mut legacy_meta = match meta {
            Value::Object(map) => map,
            _ => return Err(bad_request("legacy meta must be an object")),
        };

        let Some(value) = legacy_meta.remove("embedding") else {
            return Err(bad_request(
                "embedding is required (provide query.meta.embedding, top-level embedding, or legacy meta.embedding)",
            ));
        };

        (parse_embedding(value).map_err(bad_request)?, false)
    } else if let Some(embedder) = embedder {
        if store_dims.is_none() {
            store_dims = state.store.read().await.dims;
        }
        if let Some(expected_dim) = store_dims {
            let embedder_dim = embedder.dim();
            if expected_dim != embedder_dim {
                return Err(server_unavailable(format!(
                    "embedder dimension mismatch: expected {expected_dim}, got {embedder_dim}"
                )));
            }
        }
        let vectors = embedder.embed(std::slice::from_ref(&query_text)).await
            .map_err(|err| server_unavailable(format!("failed to generate embedding: {err}")))?;
        (
            vectors.into_iter().next().ok_or_else(|| {
            server_unavailable("failed to generate embedding: embedder returned no embeddings")
        })?,
            true,
        )
    } else {
        return Err(bad_request(
            "embedding is required (provide query.meta.embedding, top-level embedding, legacy meta.embedding, or configure INDEXD_EMBEDDER_PROVIDER)",
        ));
    };

    let store = state.store.read().await;
    let expected_dim = store_dims.or(store.dims);
    if let Some(expected_dim) = expected_dim {
        if expected_dim != embedding.len() {
            let message = format!(
                "embedding dimensionality mismatch: expected {expected_dim}, got {}",
                embedding.len()
            );
            return Err(if embedding_generated {
                server_unavailable(message)
            } else {
                bad_request(message)
            });
        }
    }
    let scored = store.search(&namespace, &embedding, k, &filter_value);

    let results = scored
        .into_iter()
        .map(|(doc_id, chunk_id, score)| {
            let snippet = store
                .chunk_meta(&namespace, &doc_id, &chunk_id)
                .and_then(|meta| meta.get("snippet"))
                .and_then(|value| value.as_str())
                .unwrap_or_default()
                .to_string();
            SearchHit {
                doc_id,
                chunk_id,
                score,
                snippet,
                rationale: Vec::new(),
            }
        })
        .collect();

    Ok(Json(SearchResponse { results }))
}

async fn handle_embed_text(
    State(state): State<Arc<AppState>>,
    ApiJson(payload): ApiJson<EmbedTextRequest>,
) -> Result<Json<EmbedTextResponse>, (StatusCode, Json<Value>)> {
    let EmbedTextRequest {
        text,
        namespace,
        source_ref,
    } = payload;

    // Validate text is not empty
    if text.trim().is_empty() {
        return Err(bad_request("text cannot be empty"));
    }

    // Validate source_ref is not empty
    if source_ref.trim().is_empty() {
        return Err(bad_request("source_ref cannot be empty"));
    }

    // Get embedder or fail
    let embedder = state
        .embedder()
        .ok_or_else(|| server_unavailable("embedder not configured. Set INDEXD_EMBEDDER_PROVIDER"))?;

    // Generate embedding
    let mut embeddings = embedder
        .embed(std::slice::from_ref(&text))
        .await
        .map_err(|err| server_unavailable(format!("failed to generate embedding: {err}")))?;

    let embedding = embeddings
        .pop()
        .ok_or_else(|| server_unavailable("embedder returned no embeddings"))?;

    // Get model info from embedder
    let embedding_model = embedder.id().to_string();
    let expected_dim = embedder.dim();
    
    // Validate embedding dimension matches embedder specification
    if embedding.len() != expected_dim {
        return Err(server_unavailable(format!(
            "embedder returned vector of dimension {} but specified dimension is {}",
            embedding.len(),
            expected_dim
        )));
    }

    // Generate unique ID
    let embedding_id = format!("embed-{}", uuid::Uuid::new_v4());

    // Get current timestamp
    let now = chrono::Utc::now();
    let generated_at = now.to_rfc3339_opts(chrono::SecondsFormat::Secs, true);

    let embedding_dim = expected_dim;

    // Model revision: Use actual model version/hash from the provider
    // Always include dimension to ensure unique identification (version + shape)
    let version_str = embedder
        .version()
        .await
        .unwrap_or_else(|_| embedding_model.clone());

    let model_revision = format!("{}-{}", version_str, embedding_dim);

    let response = EmbedTextResponse {
        embedding_id,
        text,
        embedding,
        embedding_model,
        embedding_dim,
        model_revision,
        generated_at,
        namespace,
        source_ref,
        producer: PRODUCER,
        determinism_tolerance: 1e-6,
    };

    info!(
        namespace = %response.namespace,
        source_ref = %response.source_ref,
        model = %response.embedding_model,
        dim = response.embedding_dim,
        "generated embedding"
    );

    Ok(Json(response))
}

fn parse_embedding(value: Value) -> Result<Vec<f32>, String> {
    match value {
        Value::Array(values) => {
            if values.is_empty() {
                return Err("embedding array cannot be empty".to_string());
            }
            
            let mut result = Vec::with_capacity(values.len());
            for (i, v) in values.into_iter().enumerate() {
                let num = v.as_f64()
                    .ok_or_else(|| {
                        format!("embedding[{}] must be a number, got {}", i, v)
                    })?;
                result.push(num as f32);
            }
            Ok(result)
        }
        _ => Err("embedding must be an array of numbers".to_string()),
    }
}

fn bad_request(message: impl Into<String>) -> (StatusCode, Json<Value>) {
    let body = json!({
        "error": message.into(),
    });
    (StatusCode::BAD_REQUEST, Json(body))
}

fn server_unavailable(message: impl Into<String>) -> (StatusCode, Json<Value>) {
    let body = json!({
        "error": message.into(),
    });
    // Infrastruktur-/Providerproblem (retryable, surface in Monitoring)
    (StatusCode::SERVICE_UNAVAILABLE, Json(body))
}

#[cfg(test)]
mod tests {
    use super::*;

    use async_trait::async_trait;
    use axum::extract::State;
    use embeddings::Embedder;
    use serde_json::json;

    #[derive(Debug)]
    struct TestEmbedder;

    #[async_trait]
    impl Embedder for TestEmbedder {
        async fn embed(&self, texts: &[String]) -> anyhow::Result<Vec<Vec<f32>>> {
            Ok(texts.iter().map(|_| vec![1.0f32, 0.0]).collect())
        }

        fn dim(&self) -> usize {
            2
        }

        fn id(&self) -> &'static str {
            "test"
        }

        async fn version(&self) -> anyhow::Result<String> {
            Ok("test-version".to_string())
        }
    }

    #[tokio::test]
    async fn upsert_is_atomic_on_failure() {
        let state = Arc::new(AppState::new());

        let payload = UpsertRequest {
            doc_id: "doc".into(),
            namespace: "ns".into(),
            chunks: vec![
                ChunkPayload {
                    id: "chunk-1".into(),
                    _text: "ignored".into(),
                    meta: json!({ "embedding": [0.1, 0.2] }),
                },
                ChunkPayload {
                    id: "chunk-2".into(),
                    _text: "ignored".into(),
                    meta: json!({ "embedding": [0.3] }),
                },
            ],
        };

        let result = handle_upsert(State(state.clone()), ApiJson(payload)).await;
        assert!(
            result.is_err(),
            "upsert should fail on mismatched dimensions"
        );

        let store = state.store.read().await;
        assert!(store.is_empty(), "store must remain empty");
    }

    #[tokio::test]
    async fn search_requires_embedding() {
        let state = Arc::new(AppState::new());
        let payload = SearchRequest {
            query: QueryPayload::Text("hello".into()),
            k: 5,
            namespace: "ns".into(),
            filters: None,
            embedding: None,
            meta: None,
        };

        let result = handle_search(State(state), ApiJson(payload)).await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn search_accepts_top_level_embedding() {
        let state = Arc::new(AppState::new());

        let upsert_payload = UpsertRequest {
            doc_id: "doc".into(),
            namespace: "ns".into(),
            chunks: vec![ChunkPayload {
                id: "chunk-1".into(),
                _text: "ignored".into(),
                meta: json!({ "embedding": [0.1, 0.2] }),
            }],
        };

        let upsert_result = handle_upsert(State(state.clone()), ApiJson(upsert_payload)).await;
        assert!(upsert_result.is_ok(), "upsert should succeed");

        let payload = SearchRequest {
            query: QueryPayload::Text("hello".into()),
            k: 1,
            namespace: "ns".into(),
            filters: None,
            embedding: Some(vec![0.1, 0.2]),
            meta: None,
        };

        let result = handle_search(State(state), ApiJson(payload)).await;
        assert!(result.is_ok(), "search should accept top-level embedding");
    }

    #[tokio::test]
    async fn search_accepts_query_meta_embedding() {
        let state = Arc::new(AppState::new());

        let upsert_payload = UpsertRequest {
            doc_id: "doc".into(),
            namespace: "ns".into(),
            chunks: vec![ChunkPayload {
                id: "chunk-1".into(),
                _text: "ignored".into(),
                meta: json!({ "embedding": [0.1, 0.2] }),
            }],
        };

        let upsert_result = handle_upsert(State(state.clone()), ApiJson(upsert_payload)).await;
        assert!(upsert_result.is_ok(), "upsert should succeed");

        let payload = SearchRequest {
            query: QueryPayload::WithMeta {
                text: "hello".into(),
                meta: json!({ "embedding": [0.1, 0.2] }),
            },
            k: 1,
            namespace: "ns".into(),
            filters: None,
            embedding: None,
            meta: None,
        };

        let result = handle_search(State(state), ApiJson(payload)).await;
        assert!(result.is_ok(), "search should accept query.meta.embedding");
    }

    #[tokio::test]
    async fn search_accepts_legacy_meta_embedding() {
        let state = Arc::new(AppState::new());

        let upsert_payload = UpsertRequest {
            doc_id: "doc".into(),
            namespace: "ns".into(),
            chunks: vec![ChunkPayload {
                id: "chunk-1".into(),
                _text: "ignored".into(),
                meta: json!({ "embedding": [0.1, 0.2] }),
            }],
        };

        let upsert_result = handle_upsert(State(state.clone()), ApiJson(upsert_payload)).await;
        assert!(upsert_result.is_ok(), "upsert should succeed");

        let payload = SearchRequest {
            query: QueryPayload::Text("hello".into()),
            k: 1,
            namespace: "ns".into(),
            filters: None,
            embedding: None,
            meta: Some(json!({ "embedding": [0.1, 0.2] })),
        };

        let result = handle_search(State(state), ApiJson(payload)).await;
        assert!(result.is_ok(), "search should accept legacy meta.embedding");
    }

    #[tokio::test]
    async fn search_generates_embeddings_when_embedder_configured() {
        let embedder: Arc<dyn Embedder> = Arc::new(TestEmbedder);
        let state = Arc::new(AppState::with_embedder(Some(embedder)));

        let upsert_payload = UpsertRequest {
            doc_id: "doc".into(),
            namespace: "ns".into(),
            chunks: vec![ChunkPayload {
                id: "chunk-1".into(),
                _text: "ignored".into(),
                meta: json!({ "embedding": [1.0, 0.0] }),
            }],
        };

        let upsert_result = handle_upsert(State(state.clone()), ApiJson(upsert_payload)).await;
        assert!(upsert_result.is_ok(), "upsert should succeed");

        let payload = SearchRequest {
            query: QueryPayload::Text("hello".into()),
            k: 1,
            namespace: "ns".into(),
            filters: None,
            embedding: None,
            meta: None,
        };

        let result = handle_search(State(state), ApiJson(payload)).await;
        let Json(response) = result.expect("search should succeed when embedder is configured");
        assert_eq!(response.results.len(), 1);
        assert_eq!(response.results[0].doc_id, "doc");
        assert_eq!(response.results[0].chunk_id, "chunk-1");
    }

    #[derive(Debug)]
    struct FailingEmbedder;

    #[async_trait]
    impl Embedder for FailingEmbedder {
        async fn embed(&self, _texts: &[String]) -> anyhow::Result<Vec<Vec<f32>>> {
            Err(anyhow::anyhow!("provider unavailable"))
        }

        fn dim(&self) -> usize {
            2
        }

        fn id(&self) -> &'static str {
            "failing"
        }

        async fn version(&self) -> anyhow::Result<String> {
            Ok("failing-version".to_string())
        }
    }

    #[tokio::test]
    async fn search_returns_503_on_embedder_failure() {
        let embedder: Arc<dyn Embedder> = Arc::new(FailingEmbedder);
        let state = Arc::new(AppState::with_embedder(Some(embedder)));

        let payload = SearchRequest {
            query: QueryPayload::Text("hello".into()),
            k: 1,
            namespace: "ns".into(),
            filters: None,
            embedding: None,
            meta: None,
        };

        let result = handle_search(State(state), ApiJson(payload)).await;
        let (status, body) = result.expect_err("search should fail when embedder returns an error");
        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(
            body.0.get("error")
                .and_then(|v| v.as_str())
                .unwrap_or(""),
            "failed to generate embedding: provider unavailable"
        );
    }

    #[tokio::test]
    async fn search_with_k_zero_is_rejected() {
        let state = Arc::new(AppState::new());
        let payload = SearchRequest {
            query: QueryPayload::Text("hello".into()),
            k: 0,
            namespace: "ns".into(),
            filters: None,
            embedding: Some(vec![0.1, 0.2]),
            meta: None,
        };

        let result = handle_search(State(state), ApiJson(payload)).await;
        assert!(result.is_err(), "search with k=0 should be rejected");
        let (status, _) = result.unwrap_err();
        assert_eq!(status, StatusCode::BAD_REQUEST);
    }

    #[tokio::test]
    async fn search_rejects_mismatched_embedding_dimensions() {
        let state = Arc::new(AppState::new());

        let upsert_payload = UpsertRequest {
            doc_id: "doc".into(),
            namespace: "ns".into(),
            chunks: vec![ChunkPayload {
                id: "chunk-1".into(),
                _text: "ignored".into(),
                meta: json!({ "embedding": [0.1, 0.2] }),
            }],
        };

        let upsert_result = handle_upsert(State(state.clone()), ApiJson(upsert_payload)).await;
        assert!(upsert_result.is_ok(), "upsert should succeed");

        let payload = SearchRequest {
            query: QueryPayload::Text("hello".into()),
            k: 1,
            namespace: "ns".into(),
            filters: None,
            embedding: Some(vec![0.1]),
            meta: None,
        };

        let result = handle_search(State(state), ApiJson(payload)).await;
        let (status, _) = result.expect_err("search should reject dimensionality mismatch");
        assert_eq!(status, StatusCode::BAD_REQUEST);
    }

    #[derive(Debug)]
    struct MismatchedEmbedder;

    #[async_trait]
    impl Embedder for MismatchedEmbedder {
        async fn embed(&self, _texts: &[String]) -> anyhow::Result<Vec<Vec<f32>>> {
            Ok(vec![vec![1.0, 0.0, 0.5]])
        }

        fn dim(&self) -> usize {
            3
        }

        fn id(&self) -> &'static str {
            "mismatch"
        }

        async fn version(&self) -> anyhow::Result<String> {
            Ok("mismatch-version".to_string())
        }
    }

    #[tokio::test]
    async fn search_returns_503_on_generated_embedding_dimension_mismatch() {
        #[derive(Debug)]
        struct WrongVectorEmbedder;

        #[async_trait]
        impl Embedder for WrongVectorEmbedder {
            async fn embed(&self, _texts: &[String]) -> anyhow::Result<Vec<Vec<f32>>> {
                Ok(vec![vec![1.0, 0.0, 0.5]])
            }

            fn dim(&self) -> usize {
                2
            }

            fn id(&self) -> &'static str {
                "wrong-vector"
            }

            async fn version(&self) -> anyhow::Result<String> {
                Ok("wrong-vector-version".to_string())
            }
        }

        let embedder: Arc<dyn Embedder> = Arc::new(WrongVectorEmbedder);
        let state = Arc::new(AppState::with_embedder(Some(embedder)));

        let upsert_payload = UpsertRequest {
            doc_id: "doc".into(),
            namespace: "ns".into(),
            chunks: vec![ChunkPayload {
                id: "chunk-1".into(),
                _text: "ignored".into(),
                meta: json!({ "embedding": [0.1, 0.2] }),
            }],
        };

        let upsert_result = handle_upsert(State(state.clone()), ApiJson(upsert_payload)).await;
        assert!(upsert_result.is_ok(), "upsert should succeed");
        {
            let store = state.store.read().await;
            assert_eq!(store.dims, Some(2));
        }

        let payload = SearchRequest {
            query: QueryPayload::Text("hello".into()),
            k: 1,
            namespace: "ns".into(),
            filters: None,
            embedding: None,
            meta: None,
        };

        let result = handle_search(State(state), ApiJson(payload)).await;
        let (status, _) = result.expect_err("search should fail on embedder/store mismatch");
        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
    }

    #[tokio::test]
    async fn search_returns_503_when_embedder_dim_mismatches_store() {
        let embedder: Arc<dyn Embedder> = Arc::new(MismatchedEmbedder);
        let state = Arc::new(AppState::with_embedder(Some(embedder)));

        let upsert_payload = UpsertRequest {
            doc_id: "doc".into(),
            namespace: "ns".into(),
            chunks: vec![ChunkPayload {
                id: "chunk-1".into(),
                _text: "ignored".into(),
                meta: json!({ "embedding": [0.1, 0.2] }),
            }],
        };

        let upsert_result = handle_upsert(State(state.clone()), ApiJson(upsert_payload)).await;
        assert!(upsert_result.is_ok(), "upsert should succeed");
        {
            let store = state.store.read().await;
            assert_eq!(store.dims, Some(2));
        }

        let payload = SearchRequest {
            query: QueryPayload::Text("hello".into()),
            k: 1,
            namespace: "ns".into(),
            filters: None,
            embedding: None,
            meta: None,
        };

        let result = handle_search(State(state), ApiJson(payload)).await;
        let (status, _) = result.expect_err("search should fail on embedder/store dim mismatch");
        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
    }
}
