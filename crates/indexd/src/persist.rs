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

use crate::{key::split_chunk_key, AppState};

const ENV_DB_PATH: &str = "INDEXD_DB_PATH";

#[derive(Debug, Serialize, Deserialize)]
struct RowOwned {
    namespace: String,
    doc_id: String,
    chunk_id: String,
    embedding: Vec<f32>,
    meta: Value,
}

pub async fn maybe_load_from_env(state: &Arc<AppState>) -> anyhow::Result<()> {
    let Some(path) = env::var_os(ENV_DB_PATH).map(PathBuf::from) else {
        return Ok(());
    };

    if !path.exists() {
        return Ok(());
    }

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
        count = store.items.len(),
        skipped,
        "loaded vector store"
    );
    Ok(())
}

pub async fn maybe_save_from_env(state: &Arc<AppState>) -> anyhow::Result<()> {
    let Some(path) = env::var_os(ENV_DB_PATH).map(PathBuf::from) else {
        return Ok(());
    };

    let store = state.store.read().await;
    let mut rows = Vec::with_capacity(store.items.len());

    for ((namespace, key), (embedding, meta)) in store.items.iter() {
        let (doc_id, chunk_id) = split_chunk_key(key);
        rows.push(RowOwned {
            namespace: namespace.clone(),
            doc_id,
            chunk_id,
            embedding: embedding.clone(),
            meta: meta.clone(),
        });
    }

    let row_count = rows.len();
    let path_clone = path.clone();
    task::spawn_blocking(move || write_jsonl_atomic(&path_clone, &rows))
        .await
        .map_err(|err| anyhow!("spawn blocking write_jsonl_atomic failed: {}", err))?
        .map_err(|err| anyhow!("write_jsonl_atomic failed: {}", err))?;

    info!(path = %path.display(), count = row_count, "saved vector store");
    Ok(())
}

fn read_jsonl(path: &Path) -> anyhow::Result<Vec<RowOwned>> {
    let file = File::open(path)?;
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
}
