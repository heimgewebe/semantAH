use std::env;
use std::fs::{self, File};
use std::io::{BufRead, BufReader, BufWriter, Write};
use std::path::{Path, PathBuf};
use std::sync::Arc;

use anyhow::{anyhow, Context};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio::task;
use tracing::{info, warn};

use crate::{
    key::split_chunk_key_ref,
    store::VectorStore,
    AppState,
};

const ENV_DB_PATH: &str = "INDEXD_DB_PATH";

#[derive(Debug, Serialize, Deserialize)]
struct RowOwned {
    namespace: String,
    doc_id: String,
    chunk_id: String,
    embedding: Vec<f32>,
    meta: Value,
}

#[derive(Serialize)]
struct RowRef<'a> {
    namespace: &'a str,
    doc_id: &'a str,
    chunk_id: &'a str,
    embedding: &'a [f32],
    meta: &'a Value,
}

pub async fn maybe_load_from_env(state: &Arc<AppState>) -> anyhow::Result<()> {
    let Some(path) = env::var_os(ENV_DB_PATH).map(PathBuf::from) else {
        return Ok(());
    };

    let path_clone = path.clone();
    let items = task::spawn_blocking(move || read_jsonl(&path_clone))
        .await
        .map_err(|err| anyhow!("spawn blocking read_jsonl failed: {}", err))?
        .map_err(|err| anyhow!("read_jsonl failed: {}", err))?;

    let mut store = state.store.write().await;
    let mut dims: Option<usize> = store.dims;
    let mut skipped = 0usize;

    for row in items {
        if let Some(expected) = dims {
            if expected != row.embedding.len() {
                warn!(
                    chunk_id = %row.chunk_id,
                    "skip row with mismatched dims: expected {expected}, got {}",
                    row.embedding.len()
                );
                skipped += 1;
                continue;
            }
        } else {
            dims = Some(row.embedding.len());
        }

        let RowOwned {
            namespace,
            doc_id,
            chunk_id,
            embedding,
            meta,
        } = row;

        if let Err(err) = store.upsert(&namespace, &doc_id, &chunk_id, embedding, meta) {
            warn!(chunk_id = %chunk_id, error = %err, "failed to upsert row from persistence");
            skipped += 1;
        }
    }

    info!(
        path = %path.display(),
        count = store.len(),
        skipped,
        "loaded vector store"
    );
    Ok(())
}

pub async fn maybe_save_from_env(state: &Arc<AppState>) -> anyhow::Result<()> {
    let Some(path) = env::var_os(ENV_DB_PATH).map(PathBuf::from) else {
        return Ok(());
    };

    // Use read_owned to get an owned guard we can move into the blocking task
    let store = state.store.clone().read_owned().await;
    let row_count = store.len();
    let path_clone = path.clone();

    task::spawn_blocking(move || save_store_atomic(&path_clone, &store))
        .await
        .map_err(|err| anyhow!("spawn blocking save_store_atomic failed: {}", err))?
        .map_err(|err| anyhow!("save_store_atomic failed: {}", err))?;

    info!(path = %path.display(), count = row_count, "saved vector store");
    Ok(())
}

fn read_jsonl(path: &Path) -> anyhow::Result<Vec<RowOwned>> {
    let file = match File::open(path) {
        Ok(file) => file,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(Vec::new()),
        Err(e) => return Err(e.into()),
    };

    let reader = BufReader::new(file);
    let mut rows = Vec::new();

    for line in reader.lines() {
        let line = line?;
        if line.trim().is_empty() {
            continue;
        }

        let row: RowOwned = serde_json::from_str(&line)?;
        rows.push(row);
    }

    Ok(rows)
}

fn save_store_atomic(path: &Path, store: &VectorStore) -> anyhow::Result<()> {
    if let Some(dir) = path.parent() {
        fs::create_dir_all(dir).with_context(|| format!("create_dir_all {}", dir.display()))?;
    }

    let tmp = path.with_extension("tmp");
    {
        let file = File::create(&tmp)?;
        let mut writer = BufWriter::new(file);

        for (namespace, ns_items) in &store.items {
            for (key, (embedding, meta)) in ns_items {
                let (doc_id, chunk_id) = split_chunk_key_ref(key);
                let row = RowRef {
                    namespace,
                    doc_id,
                    chunk_id,
                    embedding,
                    meta,
                };
                serde_json::to_writer(&mut writer, &row)?;
                writer.write_all(b"\n")?;
            }
        }

        writer.flush()?;
    }

    #[cfg(windows)]
    if path.exists() {
        fs::remove_file(path)?;
    }

    fs::rename(tmp, path)?;
    Ok(())
}

#[cfg(test)]
fn write_jsonl_atomic(path: &Path, rows: &[RowOwned]) -> anyhow::Result<()> {
    if let Some(dir) = path.parent() {
        fs::create_dir_all(dir).with_context(|| format!("create_dir_all {}", dir.display()))?;
    }

    let tmp = path.with_extension("tmp");
    {
        let file = File::create(&tmp)?;
        let mut writer = BufWriter::new(file);

        for row in rows {
            serde_json::to_writer(&mut writer, row)?;
            writer.write_all(b"\n")?;
        }

        writer.flush()?;
    }

    #[cfg(windows)]
    if path.exists() {
        fs::remove_file(path)?;
    }

    fs::rename(tmp, path)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn jsonl_roundtrip() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("store.jsonl");

        let rows = vec![
            RowOwned {
                namespace: "ns".into(),
                doc_id: "d1".into(),
                chunk_id: "c1".into(),
                embedding: vec![0.1, 0.2],
                meta: serde_json::json!({"snippet": "hello"}),
            },
            RowOwned {
                namespace: "ns".into(),
                doc_id: "d2".into(),
                chunk_id: "c2".into(),
                embedding: vec![0.3, 0.4],
                meta: Value::Null,
            },
        ];

        write_jsonl_atomic(&path, &rows).unwrap();
        let back = read_jsonl(&path).unwrap();

        assert_eq!(rows.len(), back.len());
        assert_eq!(rows[0].doc_id, back[0].doc_id);
        assert_eq!(rows[0].embedding, back[0].embedding);
    }

    #[test]
    fn read_jsonl_not_found() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("non_existent.jsonl");
        // Should return empty vector, not error
        let result = read_jsonl(&path);
        assert!(
            result.is_ok(),
            "Expected Ok for non-existent file, got {:?}",
            result.err()
        );
        assert!(result.unwrap().is_empty());
    }

    #[test]
    fn jsonl_stream_roundtrip() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("store_stream.jsonl");

        let mut store = VectorStore::new();
        // vectors are normalized on insert, so we use unit vectors for easy check
        store
            .upsert(
                "ns",
                "d1",
                "c1",
                vec![1.0, 0.0],
                serde_json::json!({"a": 1}),
            )
            .unwrap();
        store
            .upsert("ns", "d2", "c2", vec![0.0, 1.0], Value::Null)
            .unwrap();

        save_store_atomic(&path, &store).unwrap();
        let back = read_jsonl(&path).unwrap();

        assert_eq!(store.len(), back.len());

        let row1 = back.iter().find(|r| r.doc_id == "d1").unwrap();
        assert_eq!(row1.namespace, "ns");
        assert_eq!(row1.chunk_id, "c1");
        assert_eq!(row1.meta, serde_json::json!({"a": 1}));
        assert_eq!(row1.embedding, vec![1.0, 0.0]);

        let row2 = back.iter().find(|r| r.doc_id == "d2").unwrap();
        assert_eq!(row2.embedding, vec![0.0, 1.0]);
    }
}
