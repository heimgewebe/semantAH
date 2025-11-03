### 📄 crates/indexd/tests/e2e_http.rs

**Größe:** 2 KB | **md5:** `81ed8662b1cf7dd7775b3e74c9916702`

```rust
use std::net::SocketAddr;
use std::sync::Arc;

use axum::Router;
use indexd::{api, AppState};
use serde_json::json;
use tokio::net::TcpListener;

#[tokio::test]
async fn upsert_and_search_over_http() {
    // --- start server on a random local port
    let state = Arc::new(AppState::new());
    let app: Router = api::router(state);

    let listener = TcpListener::bind(("127.0.0.1", 0)).await.unwrap();
    let addr: SocketAddr = listener.local_addr().unwrap();

    let server = tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });

    let base = format!("http://{}", addr);
    let client = reqwest::Client::new();

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
```

### 📄 crates/indexd/tests/healthz.rs

**Größe:** 608 B | **md5:** `11486604bd2275696876d40b80e646e9`

```rust
use std::sync::Arc;

use axum::{
    body::{to_bytes, Body},
    http::{Request, StatusCode},
};
use tower::ServiceExt;

#[tokio::test]
async fn healthz_returns_ok() {
    let app = indexd::router(Arc::new(indexd::AppState::new()));

    let response = app
        .oneshot(
            Request::builder()
                .uri("/healthz")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);

    let body = to_bytes(response.into_body(), 1024).await.unwrap();
    assert_eq!(body.as_ref(), b"ok");
}
```

### 📄 crates/indexd/tests/search.rs

**Größe:** 9 KB | **md5:** `a61256b507e0f17cb72e820dd7a6de97`

```rust
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
```

