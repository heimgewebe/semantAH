use indexd::{persist, AppState};
use serde_json::{json, Value};
use std::fs::File;
use std::io::Write;
use std::sync::Arc;
use tempfile::tempdir;

struct EnvGuard {
    key: &'static str,
}

impl Drop for EnvGuard {
    fn drop(&mut self) {
        std::env::remove_var(self.key);
    }
}

#[tokio::test]
async fn persistence_normalizes_unnormalized_vectors_on_load() {
    let dir = tempdir().unwrap();
    let db_path = dir.path().join("legacy_store.jsonl");

    // 1. Create a JSONL file with unnormalized vectors
    // d1: [2.0, 0.0] -> should normalize to [1.0, 0.0]
    // d2: [1.0, 1.0] -> should normalize to [0.707..., 0.707...]
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

    // 2. Set env var to point to this file using guard
    std::env::set_var("INDEXD_DB_PATH", &db_path);
    let _guard = EnvGuard {
        key: "INDEXD_DB_PATH",
    };

    // 3. Load the store
    let state = Arc::new(AppState::new());
    persist::maybe_load_from_env(&state)
        .await
        .expect("load failed");

    // 4. Verify via public API (search)
    let store = state.store.read().await;

    // Query with [1.0, 0.0].
    // If d1 was normalized to [1.0, 0.0], dot product should be 1.0.
    // If d2 was normalized to [0.707, 0.707], dot product should be 0.707.
    let results = store.search("ns", &[1.0, 0.0], 10, &Value::Null);

    assert_eq!(results.len(), 2, "should find both documents");

    // Check d1
    let d1 = results
        .iter()
        .find(|(doc, chunk, _)| doc == "d1" && chunk == "c1")
        .expect("d1 should be present");
    assert!(
        (d1.2 - 1.0).abs() < 1e-6,
        "d1 score should be 1.0 (normalized), got {}",
        d1.2
    );

    // Check d2
    let d2 = results
        .iter()
        .find(|(doc, chunk, _)| doc == "d2" && chunk == "c2")
        .expect("d2 should be present");
    let expected_score = 1.0 / (2.0f32).sqrt(); // cos(45 deg)
    assert!(
        (d2.2 - expected_score).abs() < 1e-6,
        "d2 score should be ~{}, got {}",
        expected_score,
        d2.2
    );

    // Verify ordering: d1 (1.0) > d2 (0.707)
    let d1_pos = results.iter().position(|r| r.0 == "d1").unwrap();
    let d2_pos = results.iter().position(|r| r.0 == "d2").unwrap();
    assert!(d1_pos < d2_pos, "d1 should be ranked higher than d2");
}
