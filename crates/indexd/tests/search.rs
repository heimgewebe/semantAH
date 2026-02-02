use std::sync::Arc;

use anyhow::Result as AnyResult;
use async_trait::async_trait;
use axum::{body::to_bytes, body::Body, http::Request};
use embeddings::Embedder;
use indexd::{api, AppState};
use serde_json::json;
use tower::ServiceExt;

struct StaticEmbedder {
    vector: Vec<f32>,
}

#[async_trait]
impl Embedder for StaticEmbedder {
    async fn embed(&self, texts: &[String]) -> AnyResult<Vec<Vec<f32>>> {
        Ok(texts.iter().map(|_| self.vector.clone()).collect())
    }

    fn dim(&self) -> usize {
        self.vector.len()
    }

    fn id(&self) -> &'static str {
        "static"
    }

    async fn version(&self) -> AnyResult<String> {
        Ok("static-version".to_string())
    }
}

#[tokio::test]
async fn upsert_then_search_with_query_meta_embedding_returns_hit() {
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

#[tokio::test]
async fn upsert_then_search_with_legacy_meta_embedding_returns_hit() {
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
        "meta": {"embedding": [1.0, 0.0]}
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
async fn query_meta_embedding_overrides_other_locations() {
    let state = Arc::new(AppState::new());
    let app = api::router(state.clone());

    let upsert_payload = json!({
        "doc_id": "d1",
        "namespace": "ns",
        "chunks": [
            {"id": "c1", "text": "x", "meta": {"embedding": [1.0, 0.0], "snippet": "x"}},
            {"id": "c2", "text": "y", "meta": {"embedding": [0.0, 1.0], "snippet": "y"}}
        ]
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
            "text": "irrelevant",
            "meta": {"embedding": [0.0, 1.0]}
        },
        "namespace": "ns",
        "k": 1,
        "embedding": [1.0, 0.0],
        "meta": {"embedding": [1.0, 0.0]}
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
    assert_eq!(results[0]["chunk_id"], "c2");
}

#[tokio::test]
async fn search_generates_embedding_from_query_text_when_embedder_configured() {
    let embedder: Arc<dyn Embedder> = Arc::new(StaticEmbedder {
        vector: vec![1.0, 0.0],
    });
    let state = Arc::new(AppState::with_embedder(Some(embedder)));
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

/// Functional test for the search endpoint to ensure it returns correct results
/// after refactoring to use `spawn_blocking`.
///
/// NOTE: This test does not explicitly verify that the search runs on a blocking
/// thread (which would be fragile and runtime-dependent), but it exercises
/// the code path that uses `read_owned` and `spawn_blocking`.
#[tokio::test]
async fn search_smoke_query_meta_embedding() {
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

    app.clone()
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

    let search_payload = json!({
        "query": {
            "text": "hello",
            "meta": {"embedding": [1.0, 0.0]}
        },
        "k": 1,
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

    assert!(
        response.status().is_success(),
        "Search failed: {:?}",
        response.status()
    );

    let body = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();

    let results = json["results"]
        .as_array()
        .expect("results should be an array");
    assert_eq!(results.len(), 1);
    assert_eq!(results[0]["doc_id"], "d1");
}
