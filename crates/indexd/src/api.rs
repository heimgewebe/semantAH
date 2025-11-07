use std::sync::Arc;

use axum::{extract::State, http::StatusCode, routing::post, Json, Router};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tracing::{debug, info};

use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct UpsertRequest {
    pub doc_id: String,
    pub namespace: String,
    pub chunks: Vec<ChunkPayload>,
}

#[derive(Debug, Deserialize)]
pub struct ChunkPayload {
    pub id: String,
    #[serde(rename = "text")]
    _text: String,
    #[serde(default = "default_meta")]
    pub meta: Value,
}

#[derive(Debug, Deserialize)]
pub struct DeleteRequest {
    pub doc_id: String,
    pub namespace: String,
}

#[derive(Debug, Deserialize)]
pub struct SearchRequest {
    /// TODO(server-side-embeddings): replace client-provided vectors with generated embeddings.
    pub query: QueryPayload,
    #[serde(default = "default_k")]
    pub k: u32,
    pub namespace: String,
    #[serde(default)]
    pub filters: Option<Value>,
    /// Optional top-level embedding payload until server-side embeddings are available.
    #[serde(default)]
    pub embedding: Option<Value>,
    /// Legacy fallback: support former top-level `meta.embedding`
    /// (kept optional to remain backward compatible).
    #[serde(default)]
    pub meta: Option<Value>,
}

#[derive(Debug, Deserialize)]
#[serde(untagged)]
pub enum QueryPayload {
    Text(String),
    WithMeta {
        text: String,
        #[serde(default = "default_meta")]
        meta: Value,
    },
}

impl QueryPayload {
    fn text(&self) -> &str {
        match self {
            QueryPayload::Text(text) => text,
            QueryPayload::WithMeta { text, .. } => text,
        }
    }
}

#[derive(Debug, Serialize)]
pub struct SearchResponse {
    pub results: Vec<SearchHit>,
}

#[derive(Debug, Serialize)]
pub struct SearchHit {
    pub doc_id: String,
    pub chunk_id: String,
    pub score: f32,
    pub snippet: String,
    pub rationale: Vec<String>,
}

pub fn router(state: Arc<AppState>) -> Router {
    // NOTE: Only API routes here. Base routes (e.g. /healthz) are merged in `indexd::run`
    // (and in Tests explizit), um doppelte Registrierung zu vermeiden.
    Router::new()
        .route("/index/upsert", post(handle_upsert))
        .route("/index/delete", post(handle_delete))
        .route("/index/search", post(handle_search))
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
    Json(payload): Json<UpsertRequest>,
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
            _ => return Err(bad_request("chunk meta must be an object")),
        };

        let embedding_value = meta
            .remove("embedding")
            .ok_or_else(|| bad_request("chunk meta must contain an embedding array"))?;

        let vector = parse_embedding(embedding_value).map_err(bad_request)?;

        if let Some(expected) = expected_dim {
            if expected != vector.len() {
                return Err(bad_request(format!(
                    "chunk embedding dimensionality mismatch: expected {expected}, got {}",
                    vector.len()
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
    Json(payload): Json<DeleteRequest>,
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
    Json(payload): Json<SearchRequest>,
) -> Result<Json<SearchResponse>, (StatusCode, Json<Value>)> {
    if payload.k == 0 {
        return Err(bad_request("k must be greater than 0"));
    }

    let query_text_owned = payload.query.text().to_owned();
    let query_text = &query_text_owned;

    debug!(
        query = %query_text,
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

    let query_embedding_value = match query {
        QueryPayload::Text(_) => None,
        QueryPayload::WithMeta { meta, .. } => {
            let mut meta_map = match meta {
                Value::Object(map) => map,
                _ => return Err(bad_request("query meta must be an object")),
            };
            meta_map.remove("embedding")
        }
    };

    let k = k as usize;
    let filter_value = filters.unwrap_or(Value::Null);

    // Priority: query.meta.embedding > top-level embedding > legacy meta.embedding
    let embedding: Vec<f32> = if let Some(value) = query_embedding_value {
        parse_embedding(value).map_err(bad_request)?
    } else if let Some(value) = embedding {
        parse_embedding(value).map_err(bad_request)?
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

        parse_embedding(value).map_err(bad_request)?
    } else if let Some(embedder) = embedder {
        let vectors = embedder.embed(&[query_text_owned.clone()]).await
            .map_err(|err| server_unavailable(format!("failed to generate embedding: {err}")))?;
        vectors.into_iter().next().ok_or_else(|| {
            server_unavailable("failed to generate embedding: embedder returned no embeddings")
        })?
    } else {
        return Err(bad_request(
            "embedding is required (provide query.meta.embedding, top-level embedding, legacy meta.embedding, or configure INDEXD_EMBEDDER_PROVIDER)",
        ));
    };

    let store = state.store.read().await;
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

fn parse_embedding(value: Value) -> Result<Vec<f32>, String> {
    match value {
        Value::Array(values) => values
            .into_iter()
            .map(|v| {
                v.as_f64()
                    .map(|num| num as f32)
                    .ok_or_else(|| "embedding must be an array of numbers".to_string())
            })
            .collect(),
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

        let result = handle_upsert(State(state.clone()), Json(payload)).await;
        assert!(
            result.is_err(),
            "upsert should fail on mismatched dimensions"
        );

        let store = state.store.read().await;
        assert!(store.items.is_empty(), "store must remain empty");
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

        let result = handle_search(State(state), Json(payload)).await;
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

        let upsert_result = handle_upsert(State(state.clone()), Json(upsert_payload)).await;
        assert!(upsert_result.is_ok(), "upsert should succeed");

        let payload = SearchRequest {
            query: QueryPayload::Text("hello".into()),
            k: 1,
            namespace: "ns".into(),
            filters: None,
            embedding: Some(json!([0.1, 0.2])),
            meta: None,
        };

        let result = handle_search(State(state), Json(payload)).await;
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

        let upsert_result = handle_upsert(State(state.clone()), Json(upsert_payload)).await;
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

        let result = handle_search(State(state), Json(payload)).await;
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

        let upsert_result = handle_upsert(State(state.clone()), Json(upsert_payload)).await;
        assert!(upsert_result.is_ok(), "upsert should succeed");

        let payload = SearchRequest {
            query: QueryPayload::Text("hello".into()),
            k: 1,
            namespace: "ns".into(),
            filters: None,
            embedding: None,
            meta: Some(json!({ "embedding": [0.1, 0.2] })),
        };

        let result = handle_search(State(state), Json(payload)).await;
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

        let upsert_result = handle_upsert(State(state.clone()), Json(upsert_payload)).await;
        assert!(upsert_result.is_ok(), "upsert should succeed");

        let payload = SearchRequest {
            query: QueryPayload::Text("hello".into()),
            k: 1,
            namespace: "ns".into(),
            filters: None,
            embedding: None,
            meta: None,
        };

        let result = handle_search(State(state), Json(payload)).await;
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

        let result = handle_search(State(state), Json(payload)).await;
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
            embedding: Some(json!([0.1, 0.2])),
            meta: None,
        };

        let result = handle_search(State(state), Json(payload)).await;
        assert!(result.is_err(), "search with k=0 should be rejected");
        let (status, _) = result.unwrap_err();
        assert_eq!(status, StatusCode::BAD_REQUEST);
    }
}
