//! Minimal HTTP server stub for the semantic index daemon (indexd).

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    init_tracing();

    let router = Router::new()
        .route("/index/upsert", post(handle_upsert))
        .route("/index/delete", post(handle_delete))
        .route("/index/search", post(handle_search));

    let addr: SocketAddr = "0.0.0.0:8081".parse()?;
    info!(%addr, "starting indexd stub");

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

async fn handle_upsert(Json(payload): Json<UpsertRequest>) -> Json<serde_json::Value> {
    // TODO: wire up embeddings + HNSW persistence.
    let chunk_count = payload.chunks.len();
    info!(
        doc_id = %payload.doc_id,
        namespace = %payload.namespace,
        chunks = chunk_count,
        "received upsert"
    );
    for chunk in &payload.chunks {
        tracing::debug!(
            chunk_id = %chunk.id,
            text_len = chunk.text.chars().count(),
            has_meta = !chunk.meta.is_null(),
            "upsert chunk received"
        );
    }
    Json(serde_json::json!({
        "status": "accepted",
        "chunks": chunk_count,
    }))
}

async fn handle_delete(Json(payload): Json<DeleteRequest>) -> Json<serde_json::Value> {
    info!(
        doc_id = %payload.doc_id,
        namespace = %payload.namespace,
        "received delete"
    );
    Json(serde_json::json!({
        "status": "accepted"
    }))
}

async fn handle_search(Json(payload): Json<SearchRequest>) -> Json<SearchResponse> {
    info!(
        query = %payload.query,
        k = payload.k,
        namespace = %payload.namespace,
        filters = ?payload.filters,
        "received search"
    );
    // Placeholder: return empty result list until index implementation lands.
    Json(SearchResponse {
        results: Vec::new(),
    })
}
