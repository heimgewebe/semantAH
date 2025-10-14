//! Minimal HTTP server stub for the semantic index daemon (indexd).

use std::sync::Arc;

use axum::{extract::State, http::StatusCode, routing::post, Json, Router};
use indexd::{AppState, VectorStoreError};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tracing::info;

#[derive(Debug, Deserialize)]
struct UpsertRequest {
    doc_id: String,
    namespace: String,
    chunks: Vec<ChunkPayload>,
}

#[derive(Debug, Deserialize)]
struct ChunkPayload {
    id: String,
    /// Text wird aktuell nicht genutzt (Embedding wird über `meta.embedding` erwartet),
    /// daher per Rename stillgelegt, um Warnungen zu vermeiden.
    #[serde(rename = "text")]
    _text: String,
    #[serde(default = "default_meta")]
    meta: Value,
}

#[derive(Debug, Deserialize)]
struct DeleteRequest {
    doc_id: String,
    namespace: String,
}

#[derive(Debug, Deserialize)]
struct SearchRequest {
    query: String,
    #[serde(default = "default_k")]
    k: u32,
    namespace: String,
    #[serde(default)]
    filters: Value,
}

#[derive(Debug, Serialize)]
struct SearchResponse {
    results: Vec<SearchHit>,
}

#[derive(Debug, Serialize)]
struct SearchHit {
    doc_id: String,
    chunk_id: String,
    score: f32,
    snippet: String,
    rationale: Vec<String>,
}

fn default_k() -> u32 {
    10
}

fn default_meta() -> Value {
    Value::Object(Default::default())
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    indexd::run(|state| {
        Router::new()
            .route("/index/upsert", post(handle_upsert))
            .route("/index/delete", post(handle_delete))
            .route("/index/search", post(handle_search))
            .with_state(state)
    })
    .await
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

async fn handle_search(Json(payload): Json<SearchRequest>) -> Json<SearchResponse> {
    info!(
        query = %payload.query,
        k = payload.k,
        namespace = %payload.namespace,
        filters = ?payload.filters,
        "received search"
    );

    // Placeholder: Noch keine Ähnlichkeitssuche – leere Trefferliste.
    Json(SearchResponse {
        results: Vec::new(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    use axum::{extract::State, Json};
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
        assert!(
            store.items.is_empty(),
            "store should remain empty when a chunk fails"
        );
        assert!(store.dims.is_none(), "dims should not be set on failure");
    }

    #[test]
    fn chunk_payload_defaults_meta_to_object() {
        let payload: ChunkPayload = serde_json::from_value(json!({
            "id": "chunk-1",
            "text": "ignored",
        }))
        .expect("payload should deserialize");

        match payload.meta {
            Value::Object(map) => assert!(map.is_empty(), "meta should default to empty object"),
            other => panic!("unexpected meta value: {other:?}"),
        }
    }
}
