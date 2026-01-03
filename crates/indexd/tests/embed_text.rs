use std::sync::Arc;

use axum::{
    body::Body,
    http::{Request, StatusCode},
};
use indexd::{api, AppState};
use serde_json::{json, Value};
use tower::ServiceExt;

async fn request_as_json(app: axum::Router, req: Request<Body>) -> (StatusCode, Value) {
    let response = app.oneshot(req).await.unwrap();
    let status = response.status();
    let body = axum::body::to_bytes(response.into_body(), usize::MAX)
        .await
        .unwrap();
    let json: Value = serde_json::from_slice(&body).unwrap();
    (status, json)
}

#[tokio::test]
async fn embed_text_requires_embedder() {
    let state = Arc::new(AppState::new());
    let app = api::router(state.clone()).merge(indexd::router(state.clone()));

    let payload = json!({
        "text": "hello world",
        "namespace": "osctx",
        "source_ref": "test-ref"
    });

    let req = Request::builder()
        .uri("/embed/text")
        .method("POST")
        .header("content-type", "application/json")
        .body(Body::from(payload.to_string()))
        .unwrap();

    let (status, body) = request_as_json(app, req).await;
    assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
    assert!(body["error"]
        .as_str()
        .unwrap()
        .contains("embedder not configured"));
}

#[tokio::test]
async fn embed_text_validates_namespace() {
    use async_trait::async_trait;
    use embeddings::Embedder;

    #[derive(Debug)]
    struct TestEmbedder;

    #[async_trait]
    impl Embedder for TestEmbedder {
        async fn embed(&self, texts: &[String]) -> anyhow::Result<Vec<Vec<f32>>> {
            Ok(texts.iter().map(|_| vec![1.0f32, 0.0]).collect())
        }

        fn dim(&self) -> usize {
            2
        }

        fn id(&self) -> &'static str {
            "test"
        }
    }

    let embedder: Arc<dyn Embedder> = Arc::new(TestEmbedder);
    let state = Arc::new(AppState::with_embedder(Some(embedder)));
    let app = api::router(state.clone()).merge(indexd::router(state.clone()));

    let payload = json!({
        "text": "hello world",
        "namespace": "invalid",
        "source_ref": "test-ref"
    });

    let req = Request::builder()
        .uri("/embed/text")
        .method("POST")
        .header("content-type", "application/json")
        .body(Body::from(payload.to_string()))
        .unwrap();

    let (status, body) = request_as_json(app, req).await;
    assert_eq!(status, StatusCode::BAD_REQUEST);
    assert!(body["error"]
        .as_str()
        .unwrap()
        .contains("invalid namespace"));
}

#[tokio::test]
async fn embed_text_requires_source_ref() {
    use async_trait::async_trait;
    use embeddings::Embedder;

    #[derive(Debug)]
    struct TestEmbedder;

    #[async_trait]
    impl Embedder for TestEmbedder {
        async fn embed(&self, texts: &[String]) -> anyhow::Result<Vec<Vec<f32>>> {
            Ok(texts.iter().map(|_| vec![1.0f32, 0.0]).collect())
        }

        fn dim(&self) -> usize {
            2
        }

        fn id(&self) -> &'static str {
            "test"
        }
    }

    let embedder: Arc<dyn Embedder> = Arc::new(TestEmbedder);
    let state = Arc::new(AppState::with_embedder(Some(embedder)));
    let app = api::router(state.clone()).merge(indexd::router(state.clone()));

    let payload = json!({
        "text": "hello world",
        "namespace": "osctx",
        "source_ref": ""
    });

    let req = Request::builder()
        .uri("/embed/text")
        .method("POST")
        .header("content-type", "application/json")
        .body(Body::from(payload.to_string()))
        .unwrap();

    let (status, body) = request_as_json(app, req).await;
    assert_eq!(status, StatusCode::BAD_REQUEST);
    assert!(body["error"]
        .as_str()
        .unwrap()
        .contains("source_ref cannot be empty"));
}

#[tokio::test]
async fn embed_text_returns_schema_compliant_response() {
    use async_trait::async_trait;
    use embeddings::Embedder;

    #[derive(Debug)]
    struct TestEmbedder;

    #[async_trait]
    impl Embedder for TestEmbedder {
        async fn embed(&self, texts: &[String]) -> anyhow::Result<Vec<Vec<f32>>> {
            Ok(texts.iter().map(|_| vec![0.1f32, 0.2, 0.3]).collect())
        }

        fn dim(&self) -> usize {
            3
        }

        fn id(&self) -> &'static str {
            "test-model"
        }
    }

    let embedder: Arc<dyn Embedder> = Arc::new(TestEmbedder);
    let state = Arc::new(AppState::with_embedder(Some(embedder)));
    let app = api::router(state.clone()).merge(indexd::router(state.clone()));

    let payload = json!({
        "text": "hello world",
        "namespace": "osctx",
        "source_ref": "test-event-123"
    });

    let req = Request::builder()
        .uri("/embed/text")
        .method("POST")
        .header("content-type", "application/json")
        .body(Body::from(payload.to_string()))
        .unwrap();

    let (status, body) = request_as_json(app, req).await;
    assert_eq!(status, StatusCode::OK, "body: {}", body);

    // Verify schema-compliant fields
    assert!(body["embedding_id"].is_string());
    assert_eq!(body["text"], "hello world");
    assert_eq!(body["embedding"].as_array().unwrap().len(), 3);
    assert_eq!(body["embedding_model"], "test-model");
    assert_eq!(body["embedding_dim"], 3);
    assert_eq!(body["model_revision"], "test-model-3");
    assert!(body["generated_at"].is_string());
    assert_eq!(body["namespace"], "osctx");
    assert_eq!(body["source_ref"], "test-event-123");
    assert_eq!(body["producer"], "semantAH");
    assert_eq!(body["determinism_tolerance"], 1e-6);
}

#[tokio::test]
async fn embed_text_all_valid_namespaces() {
    use async_trait::async_trait;
    use embeddings::Embedder;

    #[derive(Debug)]
    struct TestEmbedder;

    #[async_trait]
    impl Embedder for TestEmbedder {
        async fn embed(&self, texts: &[String]) -> anyhow::Result<Vec<Vec<f32>>> {
            Ok(texts.iter().map(|_| vec![0.1f32]).collect())
        }

        fn dim(&self) -> usize {
            1
        }

        fn id(&self) -> &'static str {
            "test"
        }
    }

    let embedder: Arc<dyn Embedder> = Arc::new(TestEmbedder);
    let state = Arc::new(AppState::with_embedder(Some(embedder)));

    for namespace in ["chronik", "osctx", "docs", "code", "insights"] {
        let app = api::router(state.clone()).merge(indexd::router(state.clone()));

        let payload = json!({
            "text": format!("test for {}", namespace),
            "namespace": namespace,
            "source_ref": format!("ref-{}", namespace)
        });

        let req = Request::builder()
            .uri("/embed/text")
            .method("POST")
            .header("content-type", "application/json")
            .body(Body::from(payload.to_string()))
            .unwrap();

        let (status, body) = request_as_json(app, req).await;
        assert_eq!(
            status,
            StatusCode::OK,
            "namespace {} should be valid, body: {}",
            namespace,
            body
        );
        assert_eq!(body["namespace"], namespace);
    }
}

/// Test determinism: same input should produce same embedding (within tolerance)
#[tokio::test]
async fn embed_text_determinism() {
    use async_trait::async_trait;
    use embeddings::Embedder;

    #[derive(Debug)]
    struct DeterministicEmbedder;

    #[async_trait]
    impl Embedder for DeterministicEmbedder {
        async fn embed(&self, texts: &[String]) -> anyhow::Result<Vec<Vec<f32>>> {
            // Simple deterministic embedding for testing purposes
            // Note: Uses basic hash function; collisions possible but acceptable for tests
            Ok(texts
                .iter()
                .map(|t| {
                    let hash = t.bytes().fold(0u32, |acc, b| acc.wrapping_add(b as u32));
                    vec![
                        (hash % 1000) as f32 / 1000.0,
                        ((hash / 1000) % 1000) as f32 / 1000.0,
                    ]
                })
                .collect())
        }

        fn dim(&self) -> usize {
            2
        }

        fn id(&self) -> &'static str {
            "deterministic"
        }
    }

    let embedder: Arc<dyn Embedder> = Arc::new(DeterministicEmbedder);
    let state = Arc::new(AppState::with_embedder(Some(embedder)));

    let test_text = "determinism test text";

    // Request embedding twice
    let mut embeddings = Vec::new();
    for _ in 0..2 {
        let app = api::router(state.clone()).merge(indexd::router(state.clone()));

        let payload = json!({
            "text": test_text,
            "namespace": "osctx",
            "source_ref": "test-ref"
        });

        let req = Request::builder()
            .uri("/embed/text")
            .method("POST")
            .header("content-type", "application/json")
            .body(Body::from(payload.to_string()))
            .unwrap();

        let (status, body) = request_as_json(app, req).await;
        assert_eq!(status, StatusCode::OK);

        let embedding = body["embedding"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| v.as_f64().unwrap() as f32)
            .collect::<Vec<_>>();
        embeddings.push(embedding);
    }

    // Check that embeddings are identical (or very close)
    let tolerance = 1e-6;
    assert_eq!(embeddings[0].len(), embeddings[1].len());
    for (a, b) in embeddings[0].iter().zip(embeddings[1].iter()) {
        let diff = (a - b).abs();
        assert!(
            diff < tolerance,
            "embeddings differ by {} (tolerance: {})",
            diff,
            tolerance
        );
    }
}
