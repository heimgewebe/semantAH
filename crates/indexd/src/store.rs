use std::cmp::Ordering;
use std::collections::HashMap;

use serde_json::Value;
use thiserror::Error;

use crate::key::{make_chunk_key, split_chunk_key, KEY_SEPARATOR};

/// In-memory vector store for embeddings with cosine similarity search.
///
/// All vectors in the store must have the same dimensionality, which is
/// determined by the first insertion. The store organizes items by namespace
/// and supports atomic document-level operations.
#[derive(Debug, Default)]
pub struct VectorStore {
    /// Expected dimensionality of all vectors. Set by the first insertion.
    pub dims: Option<usize>,
    /// Storage: (namespace, chunk_key) -> (embedding_vector, metadata)
    pub items: HashMap<(String, String), (Vec<f32>, Value)>,
}

impl VectorStore {
    /// Create a new empty vector store.
    pub fn new() -> Self {
        Self {
            dims: None,
            items: HashMap::new(),
        }
    }

    /// Insert or update a chunk's embedding and metadata.
    ///
    /// The first insertion sets the expected dimensionality for all future
    /// insertions. Subsequent insertions with mismatched dimensions will fail.
    ///
    /// # Errors
    ///
    /// Returns `VectorStoreError::DimensionalityMismatch` if the vector
    /// dimensionality doesn't match the store's expected dimension.
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

    /// Delete all chunks belonging to a document within a namespace.
    ///
    /// If this leaves the store empty, the dimensionality constraint is reset.
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
        _filters: &Value,
    ) -> Vec<(String, String, f32)> {
        let Some(expected) = self.dims else {
            return Vec::new();
        };

        if expected != query.len() {
            tracing::warn!(
                expected = expected,
                actual = query.len(),
                "vector dimensionality mismatch in search; returning no results"
            );
            return Vec::new();
        }

        let mut scored: Vec<(String, String, f32)> = self
            .all_in_namespace(namespace)
            .map(|((_, key), (embedding, _meta))| {
                let score = cosine(query, embedding);
                let (doc_id, chunk_id) = split_chunk_key(key);
                (doc_id, chunk_id, score)
            })
            .collect();

        // Guard against NaN scores from cosine() to keep ordering deterministic.
        let original_len = scored.len();
        scored.retain(|(_, _, score)| !score.is_nan());
        let dropped = original_len - scored.len();
        if dropped > 0 {
            tracing::warn!(
                dropped = dropped,
                "dropped search hits with NaN scores before ranking"
            );
        }

        scored.sort_by(|a, b| {
            b.2.partial_cmp(&a.2)
                .unwrap_or(Ordering::Equal)
                .then_with(|| a.0.cmp(&b.0))
                .then_with(|| a.1.cmp(&b.1))
        });
        if scored.len() > k {
            scored.truncate(k);
        }

        scored
    }

    pub fn chunk_meta(&self, namespace: &str, doc_id: &str, chunk_id: &str) -> Option<&Value> {
        let key = (namespace.to_string(), make_chunk_key(doc_id, chunk_id));
        self.items.get(&key).map(|(_, meta)| meta)
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

fn cosine(a: &[f32], b: &[f32]) -> f32 {
    let denom = l2_norm(a) * l2_norm(b);
    if denom == 0.0 {
        return 0.0;
    }
    dot(a, b) / denom
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

        let results = store.search("ns", &[1.0, 0.0], 2, &Value::Null);
        assert_eq!(results.len(), 2);
        assert_eq!(results[0].0, "doc-a");
        assert_eq!(results[0].1, "c1");
        assert!(results[0].2 > results[1].2);
    }
}
