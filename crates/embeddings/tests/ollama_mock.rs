use std::net::SocketAddr;

use anyhow::Result;
use axum::{http::StatusCode, routing::post, Json, Router};
use serde_json::json;
use tokio::net::TcpListener;

use embeddings::{Embedder, OllamaConfig, OllamaEmbedder};

/// Minimaler Mock für /api/embeddings:
/// Ignoriert den Request-Body und liefert für jede Eingabe
/// einen Vektor der Länge 2 zurück.
async fn mock_embeddings(Json(_body): Json<serde_json::Value>) -> Json<serde_json::Value> {
    // Rückgabe-Form im Mehrfachfall: "embeddings": [[...], [...]]
    // Wir geben zwei Vektoren zurück, um Mehrfacheingaben zu testen.
    Json(json!({
        "embeddings": [
            { "embedding": [1.0, 0.0] },
            { "embedding": [0.0, 1.0] }
        ]
    }))
}

/// Minimaler Mock für eine Einzeleingabe.
async fn mock_single_embedding(Json(_body): Json<serde_json::Value>) -> Json<serde_json::Value> {
    Json(json!({
        "embeddings": [
            { "embedding": [1.0, 0.0] }
        ]
    }))
}

/// Liefert absichtlich 500 mit einer kleinen Fehlermeldung.
async fn mock_500(_body: String) -> (StatusCode, String) {
    (StatusCode::INTERNAL_SERVER_ERROR, "boom".to_string())
}

/// Liefert eine falsche Dimensionalität (3), während der Embedder 2 erwartet.
async fn mock_bad_dim(Json(_body): Json<serde_json::Value>) -> Json<serde_json::Value> {
    Json(json!({
        "embeddings": [
            { "embedding": [1.0, 0.0, 0.5] }
        ]
    }))
}

#[tokio::test]
async fn ollama_embedder_happy_path_against_mock() -> Result<()> {
    // --- Mock-Server auf zufälligem Port hochfahren
    let app = Router::new().route("/api/embeddings", post(mock_embeddings));
    let listener = TcpListener::bind(("127.0.0.1", 0)).await?;
    let addr: SocketAddr = listener.local_addr()?;
    let server = tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });

    // --- Embedder auf Mock zeigen
    let base = format!("http://{}", addr);
    let embedder = OllamaEmbedder::new(OllamaConfig {
        base_url: base,
        model: "mock-embed".to_string(),
        dim: 2,
    });

    // --- Zwei Texte => zwei Vektoren
    let inputs = vec!["eins", "zwei"];
    let embeddings = embedder.embed(&inputs).await?;

    // --- Assertions
    assert_eq!(embeddings.len(), 2, "expected two embedding rows");
    assert!(
        embeddings.iter().all(|v| v.len() == 2),
        "each vector must have dim=2"
    );

    // Inhalt grob prüfen (entspricht Mock)
    assert_eq!(embeddings[0], vec![1.0, 0.0]);
    assert_eq!(embeddings[1], vec![0.0, 1.0]);

    // Server stoppen
    server.abort();
    Ok(())
}

/// Negativtest: Server liefert 500 → Embedder muss mit Status-Fehler (inkl. Body) abbrechen.
#[tokio::test]
async fn ollama_embedder_propagates_http_status_error() -> Result<()> {
    // Mock, der 500 zurückgibt
    let app = Router::new().route("/api/embeddings", post(mock_500));
    let listener = TcpListener::bind(("127.0.0.1", 0)).await?;
    let addr: SocketAddr = listener.local_addr()?;
    let server = tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });

    let base = format!("http://{}", addr);
    let embedder = OllamaEmbedder::new(OllamaConfig {
        base_url: base,
        model: "mock-embed".to_string(),
        dim: 2,
    });

    let err = embedder.embed(&["x"]).await.unwrap_err();
    let msg = err.to_string();
    assert!(
        msg.contains("status 500"),
        "error should mention status 500, got: {msg}"
    );
    assert!(
        msg.contains("boom"),
        "error should include server message body, got: {msg}"
    );

    server.abort();
    Ok(())
}

/// Negativtest: Falsche Dimensionalität (Server liefert 3, Embedder erwartet 2).
#[tokio::test]
async fn ollama_embedder_rejects_wrong_dimensions() -> Result<()> {
    let app = Router::new().route("/api/embeddings", post(mock_bad_dim));
    let listener = TcpListener::bind(("127.0.0.1", 0)).await?;
    let addr: SocketAddr = listener.local_addr()?;
    let server = tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });

    let base = format!("http://{}", addr);
    let embedder = OllamaEmbedder::new(OllamaConfig {
        base_url: base,
        model: "mock-embed".to_string(),
        dim: 2, // Erwartet 2
    });

    let err = embedder.embed(&["x"]).await.unwrap_err();
    let msg = err.to_string();
    assert!(
        msg.contains("unexpected embedding dimensionality"),
        "dimension validation should fail, got: {msg}"
    );

    server.abort();
    Ok(())
}

/// Optional: Test für Einzeleingabe — Mock liefert trotzdem "embeddings" (Mehrfachform).
#[tokio::test]
async fn ollama_embedder_single_input_against_mock() -> Result<()> {
    let app = Router::new().route("/api/embeddings", post(mock_single_embedding));
    let listener = TcpListener::bind(("127.0.0.1", 0)).await?;
    let addr: SocketAddr = listener.local_addr()?;
    let server = tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });

    let base = format!("http://{}", addr);
    let embedder = OllamaEmbedder::new(OllamaConfig {
        base_url: base,
        model: "mock-embed".to_string(),
        dim: 2,
    });

    let inputs = vec!["solo"];
    let embeddings = embedder.embed(&inputs).await?;

    assert_eq!(embeddings.len(), 1, "must return one vector");
    assert_eq!(embeddings[0].len(), 2, "dim must be 2");
    assert_eq!(embeddings[0], vec![1.0, 0.0]);

    server.abort();
    Ok(())
}
