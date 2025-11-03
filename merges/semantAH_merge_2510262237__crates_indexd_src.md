### 📄 crates/indexd/src/api.rs

**Größe:** 13 KB | **md5:** `443d5392039e6806d5ec1683d76caa91`

```rust
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
        let vectors = embedder
            .embed(&[query_text_owned.clone()])
            .await
            .map_err(|err| bad_request(format!("failed to generate embedding: {err}")))?;
        vectors.into_iter().next().ok_or_else(|| {
            bad_request("failed to generate embedding: embedder returned no embeddings")
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
}
```

### 📄 crates/indexd/src/key.rs

**Größe:** 418 B | **md5:** `a23af333eca438abe1b3928e874f1fbf`

```rust
pub(crate) const KEY_SEPARATOR: &str = "\u{241F}";

pub(crate) fn make_chunk_key(doc_id: &str, chunk_id: &str) -> String {
    format!("{doc_id}{KEY_SEPARATOR}{chunk_id}")
}

pub(crate) fn split_chunk_key(key: &str) -> (String, String) {
    match key.split_once(KEY_SEPARATOR) {
        Some((doc_id, chunk_id)) => (doc_id.to_string(), chunk_id.to_string()),
        None => (key.to_string(), String::new()),
    }
}
```

### 📄 crates/indexd/src/lib.rs

**Größe:** 5 KB | **md5:** `7a8a493f5846815035adc2dbab23186a`

```rust
pub mod api;
mod key;
mod persist;
pub mod store;

use std::{env, net::SocketAddr, sync::Arc};

use axum::{routing::get, Router};
use embeddings::{Embedder, OllamaConfig, OllamaEmbedder};
use tokio::sync::RwLock;
use tokio::{net::TcpListener, signal};
use tracing::{info, warn, Level};
use tracing_subscriber::FmtSubscriber;

pub struct AppState {
    pub store: RwLock<store::VectorStore>,
    embedder: Option<Arc<dyn Embedder>>,
}

impl std::fmt::Debug for AppState {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("AppState")
            .field("store", &"VectorStore")
            .field(
                "embedder",
                &self
                    .embedder
                    .as_ref()
                    .map(|embedder| embedder.id())
                    .unwrap_or("none"),
            )
            .finish()
    }
}

impl AppState {
    pub fn new() -> Self {
        Self::with_embedder(None)
    }

    pub fn with_embedder(embedder: Option<Arc<dyn Embedder>>) -> Self {
        Self {
            store: RwLock::new(store::VectorStore::new()),
            embedder,
        }
    }

    pub fn embedder(&self) -> Option<Arc<dyn Embedder>> {
        self.embedder.as_ref().map(Arc::clone)
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

    let embedder = maybe_init_embedder()?;
    let state = Arc::new(AppState::with_embedder(embedder));
    persist::maybe_load_from_env(&state).await?;

    let router = build_routes(state.clone()).merge(router(state.clone()));

    let addr: SocketAddr = "0.0.0.0:8080".parse()?;
    info!(%addr, "starting indexd");

    let listener = TcpListener::bind(addr).await?;
    axum::serve(listener, router)
        .with_graceful_shutdown(shutdown_signal())
        .await?;

    if let Err(err) = persist::maybe_save_from_env(&state).await {
        warn!(error = %err, "failed to persist vector store on shutdown");
    }

    info!("indexd stopped");
    Ok(())
}

fn maybe_init_embedder() -> anyhow::Result<Option<Arc<dyn Embedder>>> {
    match env::var("INDEXD_EMBEDDER_PROVIDER") {
        Ok(provider) => {
            let provider = provider.trim();
            match provider {
                "ollama" => {
                    let base_url = env::var("INDEXD_EMBEDDER_BASE_URL")
                        .unwrap_or_else(|_| "http://127.0.0.1:11434".to_string());
                    let model = env::var("INDEXD_EMBEDDER_MODEL")
                        .unwrap_or_else(|_| "nomic-embed-text".to_string());
                    let dim = env::var("INDEXD_EMBEDDER_DIM")
                        .ok()
                        .and_then(|value| value.parse::<usize>().ok())
                        .unwrap_or(1536);

                    info!(
                        provider = provider,
                        model = %model,
                        base_url = %base_url,
                        dim,
                        "configured embedder"
                    );
                    let embedder = OllamaEmbedder::new(OllamaConfig {
                        base_url,
                        model,
                        dim,
                    });
                    let embedder: Arc<dyn Embedder> = Arc::new(embedder);
                    Ok(Some(embedder))
                }
                other => {
                    anyhow::bail!("unsupported embedder provider: {other}");
                }
            }
        }
        Err(env::VarError::NotPresent) => Ok(None),
        Err(err) => Err(err.into()),
    }
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

### 📄 crates/indexd/src/main.rs

**Größe:** 180 B | **md5:** `5ea9039b1f3e051ead1655fd74517224`

```rust
//! Minimal HTTP server stub for the semantic index daemon (indexd).

use indexd::api;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    indexd::run(api::router).await
}
```

### 📄 crates/indexd/src/persist.rs

**Größe:** 5 KB | **md5:** `7842e8b41a11bb96041b1562ba3d488f`

```rust
use std::env;
use std::fs::{self, File};
use std::io::{BufRead, BufReader, BufWriter, Write};
use std::path::{Path, PathBuf};
use std::sync::Arc;

use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio::task;
use tracing::{info, warn};

use crate::{key::split_chunk_key, AppState};

const ENV_DB_PATH: &str = "INDEXD_DB_PATH";

#[derive(Debug, Serialize, Deserialize)]
struct RowOwned {
    namespace: String,
    doc_id: String,
    chunk_id: String,
    embedding: Vec<f32>,
    meta: Value,
}

pub async fn maybe_load_from_env(state: &Arc<AppState>) -> anyhow::Result<()> {
    let Some(path) = env::var_os(ENV_DB_PATH).map(PathBuf::from) else {
        return Ok(());
    };

    if !path.exists() {
        return Ok(());
    }

    let path_clone = path.clone();
    let items = task::spawn_blocking(move || read_jsonl(&path_clone)).await??;

    let mut store = state.store.write().await;
    let mut dims: Option<usize> = store.dims;
    let mut skipped = 0usize;

    for row in items {
        if let Some(expected) = dims {
            if expected != row.embedding.len() {
                warn!(
                    chunk_id = %row.chunk_id,
                    "skip row with mismatched dims: expected {expected}, got {}",
                    row.embedding.len()
                );
                skipped += 1;
                continue;
            }
        } else {
            dims = Some(row.embedding.len());
        }

        let RowOwned {
            namespace,
            doc_id,
            chunk_id,
            embedding,
            meta,
        } = row;

        if let Err(err) = store.upsert(&namespace, &doc_id, &chunk_id, embedding, meta) {
            warn!(chunk_id = %chunk_id, error = %err, "failed to upsert row from persistence");
            skipped += 1;
        }
    }

    info!(
        path = %path.display(),
        count = store.items.len(),
        skipped,
        "loaded vector store"
    );
    Ok(())
}

pub async fn maybe_save_from_env(state: &Arc<AppState>) -> anyhow::Result<()> {
    let Some(path) = env::var_os(ENV_DB_PATH).map(PathBuf::from) else {
        return Ok(());
    };

    let store = state.store.read().await;
    let mut rows = Vec::with_capacity(store.items.len());

    for ((namespace, key), (embedding, meta)) in store.items.iter() {
        let (doc_id, chunk_id) = split_chunk_key(key);
        rows.push(RowOwned {
            namespace: namespace.clone(),
            doc_id,
            chunk_id,
            embedding: embedding.clone(),
            meta: meta.clone(),
        });
    }

    let row_count = rows.len();
    let path_clone = path.clone();
    task::spawn_blocking(move || write_jsonl_atomic(&path_clone, &rows)).await??;

    info!(path = %path.display(), count = row_count, "saved vector store");
    Ok(())
}

fn read_jsonl(path: &Path) -> anyhow::Result<Vec<RowOwned>> {
    let file = File::open(path)?;
    let reader = BufReader::new(file);
    let mut rows = Vec::new();

    for line in reader.lines() {
        let line = line?;
        if line.trim().is_empty() {
            continue;
        }

        let row: RowOwned = serde_json::from_str(&line)?;
        rows.push(row);
    }

    Ok(rows)
}

fn write_jsonl_atomic(path: &Path, rows: &[RowOwned]) -> anyhow::Result<()> {
    if let Some(dir) = path.parent() {
        fs::create_dir_all(dir)?;
    }

    let tmp = path.with_extension("tmp");
    {
        let file = File::create(&tmp)?;
        let mut writer = BufWriter::new(file);

        for row in rows {
            serde_json::to_writer(&mut writer, row)?;
            writer.write_all(b"\n")?;
        }

        writer.flush()?;
    }

    #[cfg(windows)]
    if path.exists() {
        fs::remove_file(path)?;
    }

    fs::rename(tmp, path)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn jsonl_roundtrip() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("store.jsonl");

        let rows = vec![
            RowOwned {
                namespace: "ns".into(),
                doc_id: "d1".into(),
                chunk_id: "c1".into(),
                embedding: vec![0.1, 0.2],
                meta: serde_json::json!({"snippet": "hello"}),
            },
            RowOwned {
                namespace: "ns".into(),
                doc_id: "d2".into(),
                chunk_id: "c2".into(),
                embedding: vec![0.3, 0.4],
                meta: Value::Null,
            },
        ];

        write_jsonl_atomic(&path, &rows).unwrap();
        let back = read_jsonl(&path).unwrap();

        assert_eq!(rows.len(), back.len());
        assert_eq!(rows[0].doc_id, back[0].doc_id);
        assert_eq!(rows[0].embedding, back[0].embedding);
    }
}
```

### 📄 crates/indexd/src/store.rs

**Größe:** 5 KB | **md5:** `097c42cfce91d9d73d28e54c269bdb1b`

```rust
use std::cmp::Ordering;
use std::collections::HashMap;

use serde_json::Value;
use thiserror::Error;

use crate::key::{make_chunk_key, split_chunk_key, KEY_SEPARATOR};

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

    /// Executes a cosine-similarity search over all items in the namespace and
    /// returns the top-k matches sorted descending by score.
    pub fn search(
        &self,
        namespace: &str,
        query: &[f32],
        k: usize,
        _filters: &Value,
    ) -> Vec<(String, String, f32)> {
        let Some(expected) = self.dims else {
            return Vec::new();
        };

        if expected != query.len() {
            tracing::warn!(
                expected = expected,
                actual = query.len(),
                "vector dimensionality mismatch in search; returning no results"
            );
            return Vec::new();
        }

        let mut scored: Vec<(String, String, f32)> = self
            .all_in_namespace(namespace)
            .filter_map(|((_, key), (embedding, _meta))| {
                if embedding.len() != query.len() {
                    return None;
                }

                let score = cosine(query, embedding);
                let (doc_id, chunk_id) = split_chunk_key(key);
                Some((doc_id, chunk_id, score))
            })
            .collect();

        scored.sort_by(|a, b| b.2.partial_cmp(&a.2).unwrap_or(Ordering::Equal));
        if scored.len() > k {
            scored.truncate(k);
        }

        scored
    }

    pub fn chunk_meta(&self, namespace: &str, doc_id: &str, chunk_id: &str) -> Option<&Value> {
        let key = (namespace.to_string(), make_chunk_key(doc_id, chunk_id));
        self.items.get(&key).map(|(_, meta)| meta)
    }
}

#[derive(Debug, Error)]
pub enum VectorStoreError {
    #[error("embedding dimensionality mismatch: expected {expected}, got {actual}")]
    DimensionalityMismatch { expected: usize, actual: usize },
}

fn dot(a: &[f32], b: &[f32]) -> f32 {
    a.iter().zip(b.iter()).map(|(x, y)| x * y).sum()
}

fn l2_norm(vector: &[f32]) -> f32 {
    vector.iter().map(|x| x * x).sum::<f32>().sqrt()
}

fn cosine(a: &[f32], b: &[f32]) -> f32 {
    let denom = l2_norm(a) * l2_norm(b);
    if denom == 0.0 {
        return 0.0;
    }
    dot(a, b) / denom
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

    #[test]
    fn search_returns_ordered_hits() {
        let mut store = VectorStore::new();
        store
            .upsert("ns", "doc-a", "c1", vec![1.0, 0.0], Value::Null)
            .unwrap();
        store
            .upsert("ns", "doc-b", "c2", vec![0.0, 1.0], Value::Null)
            .unwrap();

        let results = store.search("ns", &[1.0, 0.0], 2, &Value::Null);
        assert_eq!(results.len(), 2);
        assert_eq!(results[0].0, "doc-a");
        assert_eq!(results[0].1, "c1");
        assert!(results[0].2 > results[1].2);
    }
}
```

