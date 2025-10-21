pub mod api;
mod key;
mod persist;
pub mod store;

use std::{net::SocketAddr, sync::Arc};

use axum::{routing::get, Router};
use tokio::sync::RwLock;
use tokio::{net::TcpListener, signal};
use tracing::{info, warn, Level};
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
