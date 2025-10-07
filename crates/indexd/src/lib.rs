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

pub fn router(state: Arc<AppState>) -> Router {
    Router::new()
        .route("/healthz", get(healthz))
        .with_state(state)
}

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
