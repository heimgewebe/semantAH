### 📄 semantAH/crates/indexd/src/lib.rs

**Größe:** 2 KB | **md5:** `e535b6c7568647d77a32ac56f1620e03`

```rust
pub mod store;

use std::{net::SocketAddr, sync::Arc};

use axum::{routing::get, Router};
use tokio::sync::RwLock;
use tokio::{net::TcpListener, signal};
use tracing::{info, Level};
use tracing_subscriber::FmtSubscriber;

#[derive(Debug)]
pub struct AppState {
    pub store: RwLock<store::VectorStore>,
}

impl AppState {
    pub fn new() -> Self {
        Self {
            store: RwLock::new(store::VectorStore::new()),
        }
    }
}

impl Default for AppState {
    fn default() -> Self {
        Self::new()
    }
}

pub use store::{VectorStore, VectorStoreError};

#[derive(Clone, Default)]
pub struct App;

/// Basis-Router (Healthcheck). Zusätzliche Routen werden in `run` via `build_routes` ergänzt.
pub fn router(state: Arc<AppState>) -> Router {
    Router::new()
        .route("/healthz", get(healthz))
        .with_state(state)
}

/// Startet den Server auf 0.0.0.0:8080 und merged die vom Caller gelieferten Routen.
pub async fn run(
    build_routes: impl FnOnce(Arc<AppState>) -> Router + Send + 'static,
) -> anyhow::Result<()> {
    init_tracing();

    let state = Arc::new(AppState::new());
    let router = build_routes(state.clone()).merge(router(state));

    let addr: SocketAddr = "0.0.0.0:8080".parse()?;
    info!(%addr, "starting indexd");

    let listener = TcpListener::bind(addr).await?;
    axum::serve(listener, router)
        .with_graceful_shutdown(shutdown_signal())
        .await?;

    info!("indexd stopped");
    Ok(())
}

fn init_tracing() {
    let subscriber = FmtSubscriber::builder()
        .with_max_level(Level::INFO)
        .with_target(false)
        .finish();
    let _ = tracing::subscriber::set_global_default(subscriber);
}

async fn shutdown_signal() {
    let ctrl_c = async {
        signal::ctrl_c()
            .await
            .expect("failed to install CTRL+C handler");
    };

    #[cfg(unix)]
    let terminate = async {
        signal::unix::signal(signal::unix::SignalKind::terminate())
            .expect("failed to install signal handler")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => {},
        _ = terminate => {},
    }
}

async fn healthz() -> &'static str {
    "ok"
}
```

### 📄 semantAH/crates/indexd/src/main.rs

**Größe:** 4 KB | **md5:** `7354e397594cf31fe16d2986b012770e`

```rust
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
    /// Text wird aktuell nicht genutzt (Embedding wird über `meta.embedding` erwartet),
    /// daher per Rename stillgelegt, um Warnungen zu vermeiden.
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
```

### 📄 semantAH/crates/indexd/src/store.rs

**Größe:** 3 KB | **md5:** `b12f68822032f47cc84967146fc7a707`

```rust
use std::collections::HashMap;

use serde_json::Value;
use thiserror::Error;

const KEY_SEPARATOR: &str = "\u{241F}";

#[derive(Debug, Default)]
pub struct VectorStore {
    pub dims: Option<usize>,
    pub items: HashMap<(String, String), (Vec<f32>, Value)>,
}

impl VectorStore {
    pub fn new() -> Self {
        Self {
            dims: None,
            items: HashMap::new(),
        }
    }

    pub fn upsert(
        &mut self,
        namespace: &str,
        doc_id: &str,
        chunk_id: &str,
        vector: Vec<f32>,
        meta: Value,
    ) -> Result<(), VectorStoreError> {
        if let Some(expected) = self.dims {
            if expected != vector.len() {
                return Err(VectorStoreError::DimensionalityMismatch {
                    expected,
                    actual: vector.len(),
                });
            }
        } else {
            self.dims = Some(vector.len());
        }

        let key = (namespace.to_string(), make_chunk_key(doc_id, chunk_id));
        self.items.insert(key, (vector, meta));
        Ok(())
    }

    pub fn delete_doc(&mut self, namespace: &str, doc_id: &str) {
        let prefix = format!("{doc_id}{KEY_SEPARATOR}");
        self.items
            .retain(|(ns, key), _| !(ns == namespace && key.starts_with(&prefix)));

        if self.items.is_empty() {
            self.dims = None;
        }
    }

    pub fn all_in_namespace<'a>(
        &'a self,
        namespace: &'a str,
    ) -> impl Iterator<Item = (&'a (String, String), &'a (Vec<f32>, Value))> + 'a {
        self.items
            .iter()
            .filter(move |((ns, _), _)| ns == namespace)
    }
}

#[derive(Debug, Error)]
pub enum VectorStoreError {
    #[error("embedding dimensionality mismatch: expected {expected}, got {actual}")]
    DimensionalityMismatch { expected: usize, actual: usize },
}

fn make_chunk_key(doc_id: &str, chunk_id: &str) -> String {
    format!("{doc_id}{KEY_SEPARATOR}{chunk_id}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn upsert_delete_smoke() {
        let mut store = VectorStore::new();
        let meta = Value::Null;
        store
            .upsert("namespace", "doc", "chunk-1", vec![0.1, 0.2], meta.clone())
            .expect("first insert sets dims");
        store
            .upsert("namespace", "doc", "chunk-2", vec![0.3, 0.4], meta)
            .expect("second insert matches dims");

        assert_eq!(store.items.len(), 2);

        store.delete_doc("namespace", "doc");

        assert!(store.items.is_empty(), "store should be empty after delete");
        assert!(
            store.dims.is_none(),
            "dims should reset after deleting all items"
        );
    }
}
```

