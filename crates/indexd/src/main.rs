//! Minimal HTTP server stub for the semantic index daemon (indexd).

use std::sync::Arc;

use axum::{extract::State, http::StatusCode, routing::post, Json, Router};
use indexd::AppState;
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
    #[serde(rename = "text")]
    _text: String,
    #[serde(default)]
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
    #[serde(rename = "namespace")]
    _namespace: String,
    #[serde(default, rename = "filters")]
    _filters: Value,
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
    info!(doc_id = %payload.doc_id, chunks = chunk_count, "received upsert");

    let UpsertRequest {
        doc_id,
        namespace,
        chunks,
    } = payload;

    let mut store = state.store.write().await;

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

        store
            .upsert(&namespace, &doc_id, &id, vector, Value::Object(meta))
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
    info!(doc_id = %payload.doc_id, "received delete");

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
    info!(query = %payload.query, k = payload.k, "received search");
    // Placeholder: return empty result list until index implementation lands.
    Json(SearchResponse {
        results: Vec::new(),
    })
}
