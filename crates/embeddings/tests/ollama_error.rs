use axum::http::StatusCode;
use axum::{routing::post, Router};
use embeddings::{Embedder, OllamaConfig, OllamaEmbedder};
use tokio::net::TcpListener;

#[tokio::test]
async fn ollama_embedder_returns_error_on_http_500() {
    // Mini-Axum-Server, der /api/embeddings immer 500 liefert
    async fn handler() -> (StatusCode, &'static str) {
        (StatusCode::INTERNAL_SERVER_ERROR, "boom")
    }
    let app = Router::new().route("/api/embeddings", post(handler));

    let listener = TcpListener::bind(("127.0.0.1", 0)).await.unwrap();
    let addr = listener.local_addr().unwrap();
    let _server = tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });

    let base = format!("http://{}", addr);
    let embedder = OllamaEmbedder::new(OllamaConfig {
        base_url: base,
        model: "test-model".into(),
        dim: 2,
    });

    let res = embedder.embed(&[String::from("hello")]).await;
    assert!(res.is_err(), "expected error on HTTP 500");
    let msg = format!("{:?}", res.err().unwrap());
    assert!(
        msg.contains("status 500"),
        "error should mention status 500, got: {msg}"
    );
}
