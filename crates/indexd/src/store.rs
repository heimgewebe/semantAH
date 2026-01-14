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
    /// Storage: namespace -> (chunk_key -> (embedding_vector, metadata))
    pub items: HashMap<String, HashMap<String, (Vec<f32>, Value)>>,
}

impl VectorStore {
    /// Create a new empty vector store.
    pub fn new() -> Self {
        Self {
            dims: None,
            items: HashMap::new(),
        }
    }

    /// Returns total number of chunks across all namespaces.
    pub fn len(&self) -> usize {
        self.items.values().map(|ns| ns.len()).sum()
    }

    /// Returns true if the store is empty.
    pub fn is_empty(&self) -> bool {
        self.items.is_empty() || self.items.values().all(|ns| ns.is_empty())
    }

    /// Insert or update a chunk's embedding and metadata.
    ///
    /// The first insertion sets the expected dimensionality for all future
    /// insertions. Subsequent insertions with mismatched dimensions will fail.
    ///
    /// Vectors are normalized to unit length upon insertion to optimize search.
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
        mut vector: Vec<f32>,
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

        normalize(&mut vector);

        let chunk_key = make_chunk_key(doc_id, chunk_id);
        self.items
            .entry(namespace.to_string())
            .or_default()
            .insert(chunk_key, (vector, meta));
        Ok(())
    }

    /// Delete all chunks belonging to a document within a namespace.
    ///
    /// If this leaves the store empty, the dimensionality constraint is reset.
    pub fn delete_doc(&mut self, namespace: &str, doc_id: &str) {
        let is_empty = if let Some(ns_items) = self.items.get_mut(namespace) {
            let prefix = format!("{doc_id}{KEY_SEPARATOR}");
            ns_items.retain(|key, _| !key.starts_with(&prefix));
            ns_items.is_empty()
        } else {
            false
        };

        if is_empty {
            self.items.remove(namespace);
        }

        if self.is_empty() {
            self.dims = None;
        }
    }

    pub fn all_in_namespace<'a>(
        &'a self,
        namespace: &'a str,
    ) -> impl Iterator<Item = (&'a String, &'a (Vec<f32>, Value))> + 'a {
        self.items
            .get(namespace)
            .into_iter()
            .flat_map(|ns_items| ns_items.iter())
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
        if k == 0 {
            return Vec::new();
        }

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

        let mut query = query.to_vec();
        normalize(&mut query);

        let mut scored: Vec<(String, String, f32)> = self
            .all_in_namespace(namespace)
            .map(|(key, (embedding, _meta))| {
                // Since both vectors are normalized, cosine similarity is just the dot product.
                let score = dot(&query, embedding);
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

        // Deterministic sorting: Score (desc) > DocID (asc) > ChunkID (asc).
        // Note: We filter NaNs above, so partial_cmp should not return None, but we use unwrap_or(Equal) just in case.
        let compare_hits = |a: &(String, String, f32), b: &(String, String, f32)| {
            b.2.partial_cmp(&a.2)
                .unwrap_or(Ordering::Equal)
                .then_with(|| a.0.cmp(&b.0))
                .then_with(|| a.1.cmp(&b.1))
        };

        if k < scored.len() {
            // O(N) selection of top-k
            // We want the best k elements, so we select the element at index k-1.
            // Elements 0..=k-1 will be partition <= element[k-1] (better or equal).
            scored.select_nth_unstable_by(k - 1, compare_hits);
            scored.truncate(k);
        }

        // Final sort of the top-k results
        scored.sort_by(compare_hits);

        scored
    }

    pub fn chunk_meta(&self, namespace: &str, doc_id: &str, chunk_id: &str) -> Option<&Value> {
        let chunk_key = make_chunk_key(doc_id, chunk_id);
        self.items
            .get(namespace)
            .and_then(|ns_items| ns_items.get(&chunk_key))
            .map(|(_, meta)| meta)
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

fn normalize(vector: &mut [f32]) {
    let norm = l2_norm(vector);
    if norm > f32::EPSILON {
        let inv_norm = 1.0 / norm;
        for x in vector.iter_mut() {
            *x *= inv_norm;
        }
    }
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

        assert_eq!(store.len(), 2);

        store.delete_doc("namespace", "doc");

        assert!(store.is_empty(), "store should be empty after delete");
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

    #[test]
    fn search_sorts_deterministically_with_ties() {
        let mut store = VectorStore::new();
        let meta = Value::Null;

        // Upsert items with vectors that will yield identical scores (same vector)
        // Insert order: B, A, C (to test that it's not just insertion order)
        store.upsert("ns", "doc-b", "c1", vec![1.0], meta.clone()).unwrap();
        store.upsert("ns", "doc-a", "c1", vec![1.0], meta.clone()).unwrap();
        store.upsert("ns", "doc-b", "c2", vec![1.0], meta.clone()).unwrap();

        // Search
        let results = store.search("ns", &[1.0], 10, &Value::Null);

        // Expect:
        // 1. doc-a, c1 (doc-a < doc-b)
        // 2. doc-b, c1 (chunk c1 < c2)
        // 3. doc-b, c2

        assert_eq!(results.len(), 3);

        // Check scores are all equal (approx 1.0)
        assert!((results[0].2 - 1.0).abs() < f32::EPSILON);
        assert!((results[1].2 - 1.0).abs() < f32::EPSILON);
        assert!((results[2].2 - 1.0).abs() < f32::EPSILON);

        // Check order
        assert_eq!(results[0].0, "doc-a");
        assert_eq!(results[0].1, "c1");

        assert_eq!(results[1].0, "doc-b");
        assert_eq!(results[1].1, "c1");

        assert_eq!(results[2].0, "doc-b");
        assert_eq!(results[2].1, "c2");
    }
}
