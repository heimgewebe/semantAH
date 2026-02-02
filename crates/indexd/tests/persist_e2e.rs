use std::env;
use std::path::PathBuf;
use std::sync::Arc;

use indexd::{persist, AppState};
use tempfile::tempdir;

/// End-to-end Persistenztest ohne HTTP:
/// 1) State A: upsert -> save (JSONL)
/// 2) State B: load -> verifiziere Inhalte
#[tokio::test]
async fn vector_store_persist_and_load_roundtrip() {
    // --- Temp-Datei für JSONL vorbereiten
    let dir = tempdir().expect("tempdir");
    let db_path: PathBuf = dir.path().join("store.jsonl");
    env::set_var("INDEXD_DB_PATH", &db_path);

    // --- State A: befüllen und speichern
    let state_a = Arc::new(AppState::new());
    {
        let mut store = state_a.store.write().await;
        // zwei Chunks, gleiche Dimensionalität
        store
            .upsert(
                "ns",
                "doc-1",
                "c1",
                vec![1.0f32, 0.0],
                serde_json::json!({"snippet": "hello"}),
            )
            .expect("upsert c1");
        store
            .upsert(
                "ns",
                "doc-1",
                "c2",
                vec![0.5f32, 0.5],
                serde_json::json!({"snippet": "world"}),
            )
            .expect("upsert c2");
    }
    // Save nach JSONL
    persist::maybe_save_from_env(&state_a)
        .await
        .expect("save must succeed");
    assert!(db_path.exists(), "persisted file must exist");

    // --- State B: neu und leer, dann load
    let state_b = Arc::new(AppState::new());
    persist::maybe_load_from_env(&state_b)
        .await
        .expect("load must succeed");

    // Verifikation
    let store_b = state_b.store.read().await;

    // Dimensionalität erhalten
    assert_eq!(store_b.dims, Some(2));

    // Zwei Items (ns/doc-1#{c1,c2})
    assert_eq!(store_b.len(), 2, "must have exactly two items");

    // Metadatenprüfung: snippet
    let meta_c1 = store_b
        .chunk_meta("ns", "doc-1", "c1")
        .expect("meta for c1 must exist");
    assert_eq!(
        meta_c1.get("snippet").and_then(|v| v.as_str()),
        Some("hello")
    );
    let meta_c2 = store_b
        .chunk_meta("ns", "doc-1", "c2")
        .expect("meta for c2 must exist");
    assert_eq!(
        meta_c2.get("snippet").and_then(|v| v.as_str()),
        Some("world")
    );
}
