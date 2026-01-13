use std::sync::Arc;
use tempfile::tempdir;
use indexd::{AppState, persist};
use serde_json::json;
use std::fs::File;
use std::io::Write;

#[tokio::test]
async fn persistence_normalizes_unnormalized_vectors_on_load() {
    let dir = tempdir().unwrap();
    let db_path = dir.path().join("legacy_store.jsonl");

    // 1. Create a JSONL file with unnormalized vectors
    // One vector with length 2.0 (should become [1.0, 0.0] or similar)
    // One vector with length ~1.414 (should become [0.707, 0.707])
    let rows = vec![
        json!({
            "namespace": "ns",
            "doc_id": "d1",
            "chunk_id": "c1",
            "embedding": [2.0, 0.0],
            "meta": {}
        }),
        json!({
            "namespace": "ns",
            "doc_id": "d2",
            "chunk_id": "c2",
            "embedding": [1.0, 1.0],
            "meta": {}
        }),
    ];

    {
        let mut file = File::create(&db_path).unwrap();
        for row in rows {
            writeln!(file, "{}", row.to_string()).unwrap();
        }
    }

    // 2. Set env var to point to this file
    std::env::set_var("INDEXD_DB_PATH", &db_path);

    // 3. Load the store
    let state = Arc::new(AppState::new());
    persist::maybe_load_from_env(&state).await.expect("load failed");

    // 4. Check that vectors are normalized
    let store = state.store.read().await;

    // Check d1: [2.0, 0.0] -> [1.0, 0.0]
    let items = store.items.get("ns").expect("namespace found");
    // Keys are constructed as "doc_id:chunk_id" usually, or whatever make_chunk_key does.
    // The key format is implicitly tested here, but looking at store.rs it is likely "doc_id:chunk_id" or similar.
    // However, I can just iterate or find by key if I know the key function.
    // Let's iterate to be safe if I don't want to import make_chunk_key or rely on internal delimiter.

    let (_, (vec1, _)) = items.iter().find(|(k, _)| k.contains("d1")).expect("d1 found");
    assert!((vec1[0] - 1.0).abs() < 1e-6, "d1[0] should be 1.0, got {}", vec1[0]);
    assert!((vec1[1] - 0.0).abs() < 1e-6, "d1[1] should be 0.0, got {}", vec1[1]);

    // Check d2: [1.0, 1.0] -> [0.70710678, 0.70710678]
    let (_, (vec2, _)) = items.iter().find(|(k, _)| k.contains("d2")).expect("d2 found");
    let expected = 1.0 / (2.0f32).sqrt();
    assert!((vec2[0] - expected).abs() < 1e-6, "d2[0] should be {}, got {}", expected, vec2[0]);
    assert!((vec2[1] - expected).abs() < 1e-6, "d2[1] should be {}, got {}", expected, vec2[1]);

    // 5. Cleanup
    std::env::remove_var("INDEXD_DB_PATH");
}
