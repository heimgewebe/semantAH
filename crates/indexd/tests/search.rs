use std::sync::Arc;

use axum::{body::to_bytes, body::Body, http::Request};
use indexd::{api, AppState};
use serde_json::json;
use tower::ServiceExt;

#[tokio::test]
async fn upsert_then_search_returns_hit() {
    let state = Arc::new(AppState::new());
    let app = api::router(state.clone());

    let upsert_payload = json!({
        "doc_id": "d1",
        "namespace": "ns",
        "chunks": [{
            "id": "c1",
            "text": "hello",
            "meta": {"embedding": [1.0, 0.0], "snippet": "hello"}
        }]
    });

    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/index/upsert")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(upsert_payload.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();

    assert!(response.status().is_success());

    let search_payload = json!({
        "query": {
            "text": "hello",
            "meta": {"embedding": [1.0, 0.0]}
        },
        "k": 5,
        "namespace": "ns"
    });

    let response = app
        .oneshot(
            Request::builder()
                .uri("/index/search")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(search_payload.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();

    assert!(response.status().is_success());

    let body = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();

    let results = json["results"]
        .as_array()
        .expect("results should be an array");
    assert_eq!(results.len(), 1);
    assert_eq!(results[0]["doc_id"], "d1");
    assert_eq!(results[0]["chunk_id"], "c1");
}

#[tokio::test]
async fn upsert_then_search_with_top_level_embedding_returns_hit() {
    let state = Arc::new(AppState::new());
    let app = api::router(state.clone());

    let upsert_payload = json!({
        "doc_id": "d1",
        "namespace": "ns",
        "chunks": [{
            "id": "c1",
            "text": "hello",
            "meta": {"embedding": [1.0, 0.0], "snippet": "hello"}
        }]
    });

    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/index/upsert")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(upsert_payload.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();

    assert!(response.status().is_success());

    let search_payload = json!({
        "query": "hello",
        "k": 5,
        "namespace": "ns",
        "embedding": [1.0, 0.0]
    });

    let response = app
        .oneshot(
            Request::builder()
                .uri("/index/search")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(search_payload.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();

    assert!(response.status().is_success());

    let body = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();

    let results = json["results"]
        .as_array()
        .expect("results should be an array");
    assert_eq!(results.len(), 1);
    assert_eq!(results[0]["doc_id"], "d1");
    assert_eq!(results[0]["chunk_id"], "c1");
}
