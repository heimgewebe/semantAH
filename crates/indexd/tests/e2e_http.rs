use std::net::SocketAddr;
use std::sync::Arc;

use axum::Router;
use indexd::{api, router as base_router, AppState};
use serde_json::json;
use tokio::net::TcpListener;

#[tokio::test]
async fn upsert_and_search_over_http() {
    // --- start server on a random local port
    let state = Arc::new(AppState::new());
    let app: Router = Router::new()
        .merge(base_router(state.clone()))
        .merge(api::router(state));

    let listener = TcpListener::bind(("127.0.0.1", 0)).await.unwrap();
    let addr: SocketAddr = listener.local_addr().unwrap();

    let server = tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });

    let base = format!("http://{}", addr);
    let client = reqwest::Client::builder()
        .no_proxy()
        .build()
        .expect("failed to build HTTP client without proxy");

    // --- healthz
    let health = client
        .get(format!("{base}/healthz"))
        .send()
        .await
        .expect("healthz request failed");
    assert!(health.status().is_success());
    assert_eq!(health.text().await.unwrap(), "ok");

    // --- upsert
    let upsert_payload = json!({
        "doc_id": "d1",
        "namespace": "ns",
        "chunks": [{
            "id": "c1",
            "text": "hello world",
            "meta": { "embedding": [1.0, 0.0], "snippet": "hello world" }
        }]
    });

    let upsert_res = client
        .post(format!("{base}/index/upsert"))
        .json(&upsert_payload)
        .send()
        .await
        .expect("upsert request failed");
    assert!(upsert_res.status().is_success());
    let upsert_json: serde_json::Value = upsert_res.json().await.unwrap();
    assert_eq!(upsert_json["status"], "accepted");
    assert_eq!(upsert_json["chunks"], 1);

    // --- search with explicit embedding
    let search_payload = json!({
        "query": "hello",
        "k": 5,
        "namespace": "ns",
        "embedding": [1.0, 0.0]
    });

    let search_res = client
        .post(format!("{base}/index/search"))
        .json(&search_payload)
        .send()
        .await
        .expect("search request failed");
    assert!(search_res.status().is_success());
    let search_json: serde_json::Value = search_res.json().await.unwrap();
    let results = search_json["results"].as_array().unwrap();
    assert_eq!(results.len(), 1);
    assert_eq!(results[0]["doc_id"], "d1");
    assert_eq!(results[0]["chunk_id"], "c1");
    assert!(results[0]["score"].as_f64().unwrap() > 0.0);

    // --- stop server
    server.abort();
}
