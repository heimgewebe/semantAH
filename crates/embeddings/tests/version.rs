use embeddings::{Embedder, OllamaConfig, OllamaEmbedder};
use serde_json::json;
use wiremock::matchers::{method, path};
use wiremock::{Mock, MockServer, ResponseTemplate};

#[tokio::test]
async fn test_version_via_show() {
    let mock_server = MockServer::start().await;

    // Test A: digest via /api/show
    Mock::given(method("POST"))
        .and(path("/api/show"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "digest": "sha256:abc"
        })))
        .mount(&mock_server)
        .await;

    let embedder = OllamaEmbedder::new(OllamaConfig {
        base_url: mock_server.uri(),
        model: "nomic-embed-text".to_string(),
        dim: 768,
    });

    let version = embedder.version().await.expect("version() failed");
    assert_eq!(version, "sha256:abc");
}

#[tokio::test]
async fn test_version_via_tags_fallback() {
    let mock_server = MockServer::start().await;

    // Test B: /api/show fails, fallback to /api/tags
    Mock::given(method("POST"))
        .and(path("/api/show"))
        .respond_with(ResponseTemplate::new(500))
        .mount(&mock_server)
        .await;

    Mock::given(method("GET"))
        .and(path("/api/tags"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "models": [
                { "name": "other-model", "digest": "sha256:ignore" },
                { "name": "nomic-embed-text", "digest": "sha256:def" }
            ]
        })))
        .mount(&mock_server)
        .await;

    let embedder = OllamaEmbedder::new(OllamaConfig {
        base_url: mock_server.uri(),
        model: "nomic-embed-text".to_string(),
        dim: 768,
    });

    let version = embedder.version().await.expect("version() failed");
    assert_eq!(version, "sha256:def");
}

#[tokio::test]
async fn test_version_via_tags_fallback_latest() {
    let mock_server = MockServer::start().await;

    // Test B.2: /api/show fails, fallback to /api/tags with ":latest" suffix
    Mock::given(method("POST"))
        .and(path("/api/show"))
        .respond_with(ResponseTemplate::new(500))
        .mount(&mock_server)
        .await;

    Mock::given(method("GET"))
        .and(path("/api/tags"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "models": [
                { "name": "other-model", "digest": "sha256:ignore" },
                // Only the :latest version is present, no exact match
                { "name": "nomic-embed-text:latest", "digest": "sha256:latest" }
            ]
        })))
        .mount(&mock_server)
        .await;

    let embedder = OllamaEmbedder::new(OllamaConfig {
        base_url: mock_server.uri(),
        model: "nomic-embed-text".to_string(),
        dim: 768,
    });

    let version = embedder.version().await.expect("version() failed");
    assert_eq!(version, "sha256:latest");
}

#[tokio::test]
async fn test_version_unknown_fallback() {
    let mock_server = MockServer::start().await;

    // Test C: both ways fail -> unknown
    Mock::given(method("POST"))
        .and(path("/api/show"))
        .respond_with(ResponseTemplate::new(500))
        .mount(&mock_server)
        .await;

    Mock::given(method("GET"))
        .and(path("/api/tags"))
        .respond_with(ResponseTemplate::new(500))
        .mount(&mock_server)
        .await;

    let embedder = OllamaEmbedder::new(OllamaConfig {
        base_url: mock_server.uri(),
        model: "nomic-embed-text".to_string(),
        dim: 768,
    });

    let version = embedder.version().await.expect("version() failed");
    assert_eq!(version, "nomic-embed-text:unknown");
}

#[tokio::test]
async fn test_caching_behavior() {
    let mock_server = MockServer::start().await;

    // Optional Bonus: Caching
    // Verify that the mock is hit only once.
    Mock::given(method("POST"))
        .and(path("/api/show"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "digest": "sha256:cached"
        })))
        .expect(1) // Expect exactly one request
        .mount(&mock_server)
        .await;

    let embedder = OllamaEmbedder::new(OllamaConfig {
        base_url: mock_server.uri(),
        model: "nomic-embed-text".to_string(),
        dim: 768,
    });

    // First call hits mock
    let v1 = embedder.version().await.expect("first call failed");
    assert_eq!(v1, "sha256:cached");

    // Second call hits cache (if it hits mock again, .expect(1) will panic/fail at the end of test or immediately)
    let v2 = embedder.version().await.expect("second call failed");
    assert_eq!(v2, "sha256:cached");
}
