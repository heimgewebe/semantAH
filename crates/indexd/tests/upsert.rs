use std::sync::Arc;

use axum::{body::to_bytes, body::Body, http::Request, http::StatusCode};
use indexd::{api, AppState};
use serde_json::json;
use tower::ServiceExt;

#[tokio::test]
async fn upsert_with_dimension_mismatch_fails() {
    let state = Arc::new(AppState::new());
    let app = api::router(state.clone());

    let upsert_payload1 = json!({
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
                .body(Body::from(upsert_payload1.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    let upsert_payload2 = json!({
        "doc_id": "d2",
        "namespace": "ns",
        "chunks": [{
            "id": "c2",
            "text": "world",
            "meta": {"embedding": [1.0, 0.0, 0.0], "snippet": "world"}
        }]
    });
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/index/upsert")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(upsert_payload2.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);

    let body = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
    assert_eq!(
        json["error"],
        "chunk 'c2' embedding dimensionality mismatch: expected 2, got 3"
    );
}

#[tokio::test]
async fn upsert_is_atomic_and_replaces_old_chunks() {
    let state = Arc::new(AppState::new());
    let app = api::router(state.clone());

    let upsert_payload1 = json!({
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
                .body(Body::from(upsert_payload1.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    let search_payload1 = json!({
        "query": {
            "text": "hello",
            "meta": {"embedding": [1.0, 0.0]}
        },
        "k": 5,
        "namespace": "ns"
    });
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/index/search")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(search_payload1.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());
    let body = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
    let results = json["results"].as_array().unwrap();
    assert_eq!(results.len(), 1);
    assert_eq!(results[0]["chunk_id"], "c1");

    let upsert_payload2 = json!({
        "doc_id": "d1",
        "namespace": "ns",
        "chunks": [{
            "id": "c2",
            "text": "world",
            "meta": {"embedding": [0.0, 1.0], "snippet": "world"}
        }]
    });
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/index/upsert")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(upsert_payload2.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    let search_payload2 = json!({
        "query": {
            "text": "world",
            "meta": {"embedding": [0.0, 1.0]}
        },
        "k": 5,
        "namespace": "ns"
    });
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/index/search")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(search_payload2.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());
    let body = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
    let results = json["results"].as_array().unwrap();
    assert_eq!(results.len(), 1);
    assert_eq!(results[0]["chunk_id"], "c2");

    let search_payload3 = json!({
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
                .body(Body::from(search_payload3.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());
    let body = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
    let results = json["results"].as_array().unwrap();
    assert!(
        results.iter().all(|r| r["chunk_id"] != "c1"),
        "old chunk c1 should not be present in search results"
    );
}
