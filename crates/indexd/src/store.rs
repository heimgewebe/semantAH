use std::cmp::Ordering;
use std::collections::HashMap;

use serde_json::Value;
use thiserror::Error;

use crate::key::{make_chunk_key, split_chunk_key, KEY_SEPARATOR};

#[derive(Debug, Default)]
pub struct VectorStore {
    pub dims: Option<usize>,
    pub items: HashMap<(String, String), (Vec<f32>, Value)>,
}

impl VectorStore {
    pub fn new() -> Self {
        Self {
            dims: None,
            items: HashMap::new(),
        }
    }

    pub fn upsert(
        &mut self,
        namespace: &str,
        doc_id: &str,
        chunk_id: &str,
        vector: Vec<f32>,
        meta: Value,
    ) -> Result<(), VectorStoreError> {
        if let Some(expected) = self.dims {
            if expected != vector.len() {
                return Err(VectorStoreError::DimensionalityMismatch {
                    expected,
                    actual: vector.len(),
                });
            }
        } else {
            self.dims = Some(vector.len());
        }

        let key = (namespace.to_string(), make_chunk_key(doc_id, chunk_id));
        self.items.insert(key, (vector, meta));
        Ok(())
    }

    pub fn delete_doc(&mut self, namespace: &str, doc_id: &str) {
        let prefix = format!("{doc_id}{KEY_SEPARATOR}");
        self.items
            .retain(|(ns, key), _| !(ns == namespace && key.starts_with(&prefix)));

        if self.items.is_empty() {
            self.dims = None;
        }
    }

    pub fn all_in_namespace<'a>(
        &'a self,
        namespace: &'a str,
    ) -> impl Iterator<Item = (&'a (String, String), &'a (Vec<f32>, Value))> + 'a {
        self.items
            .iter()
            .filter(move |((ns, _), _)| ns == namespace)
    }

    /// Executes a cosine-similarity search over all items in the namespace and
    /// returns the top-k matches sorted descending by score.
    pub fn search(
        &self,
        namespace: &str,
        query: &[f32],
        k: usize,
    ) -> Result<Vec<(String, String, f32, Value)>, VectorStoreError> {
        let Some(expected) = self.dims else {
            return Ok(Vec::new());
        };

        if expected != query.len() {
            return Err(VectorStoreError::DimensionalityMismatch {
                expected,
                actual: query.len(),
            });
        }

        let q_norm = l2_norm(query);
        if q_norm == 0.0 {
            return Ok(Vec::new());
        }

        let mut scored: Vec<(String, String, f32, Value)> = self
            .all_in_namespace(namespace)
            .filter_map(|((_, key), (embedding, meta))| {
                let denom = q_norm * l2_norm(embedding);
                if denom == 0.0 {
                    return None;
                }

                let score = dot(query, embedding) / denom;
                let (doc_id, chunk_id) = split_chunk_key(key);
                Some((doc_id, chunk_id, score, meta.clone()))
            })
            .collect();

        scored.sort_by(|a, b| b.2.partial_cmp(&a.2).unwrap_or(Ordering::Equal));
        if scored.len() > k {
            scored.truncate(k);
        }

        Ok(scored)
    }
}

#[derive(Debug, Error)]
pub enum VectorStoreError {
    #[error("embedding dimensionality mismatch: expected {expected}, got {actual}")]
    DimensionalityMismatch { expected: usize, actual: usize },
}

fn dot(a: &[f32], b: &[f32]) -> f32 {
    a.iter().zip(b.iter()).map(|(x, y)| x * y).sum()
}

fn l2_norm(vector: &[f32]) -> f32 {
    vector.iter().map(|x| x * x).sum::<f32>().sqrt()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn upsert_delete_smoke() {
        let mut store = VectorStore::new();
        let meta = Value::Null;
        store
            .upsert("namespace", "doc", "chunk-1", vec![0.1, 0.2], meta.clone())
            .expect("first insert sets dims");
        store
            .upsert("namespace", "doc", "chunk-2", vec![0.3, 0.4], meta)
            .expect("second insert matches dims");

        assert_eq!(store.items.len(), 2);

        store.delete_doc("namespace", "doc");

        assert!(store.items.is_empty(), "store should be empty after delete");
        assert!(
            store.dims.is_none(),
            "dims should reset after deleting all items"
        );
    }

    #[test]
    fn search_returns_ordered_hits() {
        let mut store = VectorStore::new();
        store
            .upsert("ns", "doc-a", "c1", vec![1.0, 0.0], Value::Null)
            .unwrap();
        store
            .upsert("ns", "doc-b", "c2", vec![0.0, 1.0], Value::Null)
            .unwrap();

        let results = store.search("ns", &[1.0, 0.0], 2).unwrap();
        assert_eq!(results.len(), 2);
        assert_eq!(results[0].0, "doc-a");
        assert_eq!(results[0].1, "c1");
        assert!(results[0].2 > results[1].2);
    }
}
