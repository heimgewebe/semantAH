use std::sync::Arc;

use axum::{extract::State, http::StatusCode, routing::post, Json, Router};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tracing::info;

use crate::{AppState, VectorStoreError};

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
    pub query: String,
    #[serde(default = "default_k")]
    pub k: u32,
    pub namespace: String,
    #[serde(default)]
    pub filters: Value,
    /// Temporarily required until server-side embeddings are wired in.
    pub embedding: Option<Vec<f32>>,
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

    let mut store = state.store.write().await;

    let mut staged = Vec::with_capacity(chunk_count);
    let mut expected_dim = store.dims;

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
                let err = VectorStoreError::DimensionalityMismatch {
                    expected,
                    actual: vector.len(),
                };
                return Err(bad_request(err.to_string()));
            }
        } else {
            expected_dim = Some(vector.len());
        }

        staged.push((id, vector, Value::Object(meta)));
    }

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
    info!(
        query = %payload.query,
        k = payload.k,
        namespace = %payload.namespace,
        filters = ?payload.filters,
        "received search"
    );

    let k = payload.k as usize;
    let embedding = payload.embedding.ok_or_else(|| {
        bad_request("embedding is required until server-side embeddings are available")
    })?;

    let store = state.store.read().await;
    let scored = store
        .search(&payload.namespace, &embedding, k)
        .map_err(|err| bad_request(err.to_string()))?;

    let results = scored
        .into_iter()
        .map(|(doc_id, chunk_id, score, meta)| {
            let snippet = meta
                .get("snippet")
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

#[cfg(test)]
mod tests {
    use super::*;

    use axum::extract::State;
    use serde_json::json;

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
            query: "hello".into(),
            k: 5,
            namespace: "ns".into(),
            filters: Value::Null,
            embedding: None,
        };

        let result = handle_search(State(state), Json(payload)).await;
        assert!(result.is_err());
    }
}
