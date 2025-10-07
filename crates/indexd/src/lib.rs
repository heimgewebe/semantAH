use std::net::SocketAddr;

use axum::{routing::{get, post}, Json, Router};
use serde::{Deserialize, Serialize};
use tokio::{net::TcpListener, signal};
use tracing::{info, Level};
use tracing_subscriber::FmtSubscriber;

#[derive(Clone, Default)]
pub struct AppState;

pub fn router() -> Router {
    Router::new()
        .route("/index/upsert", post(handle_upsert))
        .route("/index/delete", post(handle_delete))
        .route("/index/search", post(handle_search))
        .route("/healthz", get(healthz))
        .with_state(AppState::default())
}

pub async fn run() -> anyhow::Result<()> {
    init_tracing();

    let addr: SocketAddr = "0.0.0.0:8080".parse()?;
    info!(%addr, "starting indexd stub");

    let listener = TcpListener::bind(addr).await?;

    let router = router();
    let service = router.into_make_service();

    axum::serve(listener, service)
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

#[derive(Debug, Deserialize)]
struct UpsertRequest {
    doc_id: String,
    namespace: String,
    chunks: Vec<ChunkPayload>,
}

#[derive(Debug, Deserialize)]
struct ChunkPayload {
    id: String,
    text: String,
    #[serde(default)]
    meta: serde_json::Value,
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
    filters: serde_json::Value,
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

async fn handle_upsert(Json(payload): Json<UpsertRequest>) -> Json<serde_json::Value> {
    info!(doc_id = %payload.doc_id, chunks = payload.chunks.len(), "received upsert");
    Json(serde_json::json!({
        "status": "accepted",
        "chunks": payload.chunks.len(),
    }))
}

async fn handle_delete(Json(payload): Json<DeleteRequest>) -> Json<serde_json::Value> {
    info!(doc_id = %payload.doc_id, "received delete");
    Json(serde_json::json!({
        "status": "accepted"
    }))
}

async fn handle_search(Json(payload): Json<SearchRequest>) -> Json<SearchResponse> {
    info!(query = %payload.query, k = payload.k, "received search");
    Json(SearchResponse {
        results: Vec::new(),
    })
}

async fn healthz() -> &'static str {
    "ok"
}
