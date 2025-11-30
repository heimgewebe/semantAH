pub mod api;
mod key;
pub mod persist;
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
        match signal::ctrl_c().await {
            Ok(()) => info!("received CTRL+C signal"),
            Err(err) => warn!("failed to listen for CTRL+C signal: {}", err),
        }
    };

    #[cfg(unix)]
    let terminate = async {
        match signal::unix::signal(signal::unix::SignalKind::terminate()) {
            Ok(mut stream) => {
                stream.recv().await;
                info!("received SIGTERM signal");
            }
            Err(err) => warn!("failed to listen for SIGTERM signal: {}", err),
        }
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
