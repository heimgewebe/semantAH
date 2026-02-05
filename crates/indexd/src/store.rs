use std::cmp::{Ordering, Reverse};
use std::collections::{BinaryHeap, HashMap};

use serde_json::Value;
use thiserror::Error;

use crate::key::{make_chunk_key, split_chunk_key, split_chunk_key_ref, KEY_SEPARATOR};

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

        // Min-Heap (via Reverse) to keep top-k best items.
        // We store Reverse<Hit> so the Heap pops the "Worst" (Smallest) Hit.
        // Hit Ord: High Score > Low Score.
        let mut heap: BinaryHeap<Reverse<Hit>> = BinaryHeap::with_capacity(k);
        let mut dropped_nan = 0usize;

        for (key, (embedding, _meta)) in self.all_in_namespace(namespace) {
            // Since both vectors are normalized, cosine similarity is just the dot product.
            let score = dot(&query, embedding);

            if score.is_nan() {
                dropped_nan += 1;
                continue;
            }

            // 'key' here is &String from the map iteration.
            // Hit expects &'a str, so we use as_str().
            let hit = Hit { key: key.as_str(), score };

            if heap.len() < k {
                heap.push(Reverse(hit));
            } else {
                // Heap is full. Check if we should replace the worst element.
                // peek() gives the Max of Reverse<Hit>, which is the Min of Hit (Worst).
                let mut worst = heap.peek_mut().unwrap();
                if hit > worst.0 {
                    *worst = Reverse(hit);
                }
            }
        }

        if dropped_nan > 0 {
            tracing::warn!(
                dropped = dropped_nan,
                "dropped search hits with NaN scores before ranking"
            );
        }

        let mut sorted: Vec<_> = heap.into_vec().into_iter().map(|Reverse(h)| h).collect();
        // Sort Best to Worst (Descending)
        sorted.sort_unstable_by(|a, b| b.cmp(a));

        sorted
            .into_iter()
            .map(|h| {
                let (doc_id, chunk_id) = split_chunk_key(h.key);
                (doc_id, chunk_id, h.score)
            })
            .collect()
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

struct Hit<'a> {
    key: &'a str,
    score: f32,
}

impl<'a> PartialEq for Hit<'a> {
    fn eq(&self, other: &Self) -> bool {
        self.score.to_bits() == other.score.to_bits() && self.key == other.key
    }
}

impl<'a> Eq for Hit<'a> {}

impl<'a> PartialOrd for Hit<'a> {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl<'a> Ord for Hit<'a> {
    fn cmp(&self, other: &Self) -> Ordering {
        // "Better" hits must compare as Greater:
        // 1) higher score is better
        // 2) if score ties: doc_id asc, chunk_id asc is better (legacy)
        self.score
            .partial_cmp(&other.score)
            .unwrap_or(Ordering::Equal)
            .then_with(|| {
                 let (doc_self, chunk_self) = split_chunk_key_ref(self.key);
                 let (doc_other, chunk_other) = split_chunk_key_ref(other.key);

                 // Invert so that smaller (doc,chunk) becomes "Greater"/better.
                 doc_other.cmp(doc_self)
                     .then_with(|| chunk_other.cmp(chunk_self))
            })
    }
}

fn dot(a: &[f32], b: &[f32]) -> f32 {
    debug_assert_eq!(a.len(), b.len());
    let mut sum = 0.0;

    let chunks_a = a.chunks_exact(8);
    let chunks_b = b.chunks_exact(8);
    let rem_a = chunks_a.remainder();
    let rem_b = chunks_b.remainder();

    for (ca, cb) in chunks_a.zip(chunks_b) {
        sum += ca[0] * cb[0] + ca[1] * cb[1] + ca[2] * cb[2] + ca[3] * cb[3]
             + ca[4] * cb[4] + ca[5] * cb[5] + ca[6] * cb[6] + ca[7] * cb[7];
    }

    for (x, y) in rem_a.iter().zip(rem_b.iter()) {
        sum += x * y;
    }

    sum
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
        store
            .upsert("ns", "doc-b", "c1", vec![1.0], meta.clone())
            .unwrap();
        store
            .upsert("ns", "doc-a", "c1", vec![1.0], meta.clone())
            .unwrap();
        store
            .upsert("ns", "doc-b", "c2", vec![1.0], meta.clone())
            .unwrap();

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

    #[test]
    #[ignore]
    fn bench_search_performance() {
        use std::time::Instant;
        let mut store = VectorStore::new();
        let dim = 1536;
        let num_vectors = 10_000;
        let namespace = "bench_ns";

        // Populate
        for i in 0..num_vectors {
            let vec: Vec<f32> = (0..dim).map(|v| (v as f32) + (i as f32)).collect();
            store.upsert(namespace, &format!("doc-{}", i), "chunk", vec, Value::Null).unwrap();
        }

        let query: Vec<f32> = (0..dim).map(|v| v as f32).collect();

        // Warmup
        store.search(namespace, &query, 10, &Value::Null);

        let start = Instant::now();
        let iterations = 10;
        for _ in 0..iterations {
            store.search(namespace, &query, 10, &Value::Null);
        }
        let duration = start.elapsed();

        println!("Search took avg: {:?} for {} iterations", duration / iterations, iterations);
    }
}
