use std::cmp::{Ordering, Reverse};
use std::collections::{BinaryHeap, HashMap};
use std::sync::Arc;

use serde_json::Value;
use thiserror::Error;

use crate::key::{make_chunk_key, split_chunk_key, split_chunk_key_ref, KEY_SEPARATOR};

macro_rules! rank_normalized_query {
    ($entries:expr, $query:expr, $k:expr) => {{
        let mut heap: BinaryHeap<Reverse<Hit>> = BinaryHeap::with_capacity($k);
        let mut dropped_nan = 0usize;

        for item in $entries {
            let score = dot($query, &item.embedding);

            if score.is_nan() {
                dropped_nan += 1;
                continue;
            }

            let hit = Hit { item, score };

            if heap.len() < $k {
                heap.push(Reverse(hit));
            } else {
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
        sorted.sort_unstable_by(|a, b| b.cmp(a));
        sorted
    }};
}

/// One immutable stored vector and its metadata.
///
/// Entries are reference-counted so a request can retain a consistent namespace
/// snapshot after the mutable store lock has been released. Replacing or deleting
/// a live entry does not mutate snapshots already held by in-flight searches.
#[derive(Debug)]
pub struct StoredItem {
    pub(crate) key: Arc<str>,
    pub(crate) embedding: Vec<f32>,
    pub(crate) meta: Value,
}

/// Immutable namespace storage shared by live state and request snapshots.
///
/// The entry vector keeps exact-search scans contiguous, while the key index
/// preserves O(1) replacement and metadata lookup. Cloning this structure is
/// shallow because keys and stored entries are both Arc-backed.
#[derive(Debug, Clone, Default)]
pub struct NamespaceItems {
    by_key: HashMap<Arc<str>, usize>,
    entries: Vec<Arc<StoredItem>>,
}

impl NamespaceItems {
    fn len(&self) -> usize {
        self.entries.len()
    }

    fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    fn upsert(&mut self, key: Arc<str>, item: Arc<StoredItem>) {
        if let Some(index) = self.by_key.get(key.as_ref()).copied() {
            self.entries[index] = item;
        } else {
            let index = self.entries.len();
            self.by_key.insert(key, index);
            self.entries.push(item);
        }
    }

    fn delete_doc(&mut self, doc_id: &str) {
        let prefix = format!("{doc_id}{KEY_SEPARATOR}");
        self.entries
            .retain(|item| !item.key.starts_with(prefix.as_str()));
        self.by_key.clear();
        self.by_key.reserve(self.entries.len());
        for (index, item) in self.entries.iter().enumerate() {
            self.by_key.insert(Arc::clone(&item.key), index);
        }
    }

    fn get(&self, key: &str) -> Option<&StoredItem> {
        self.by_key
            .get(key)
            .and_then(|index| self.entries.get(*index))
            .map(Arc::as_ref)
    }

    fn iter(&self) -> impl Iterator<Item = &StoredItem> {
        self.entries.iter().map(Arc::as_ref)
    }

    pub(crate) fn stored_items(&self) -> impl Iterator<Item = &StoredItem> {
        self.iter()
    }
}

/// Request-local immutable view of one namespace.
#[derive(Debug, Clone)]
pub(crate) struct NamespaceSnapshot {
    dims: Option<usize>,
    items: Arc<NamespaceItems>,
}

/// In-memory vector store for embeddings with cosine similarity search.
///
/// All vectors in the store must have the same dimensionality, which is
/// determined by the first insertion. The store organizes items by namespace
/// and supports atomic document-level operations.
#[derive(Debug, Default)]
pub struct VectorStore {
    /// Expected dimensionality of all vectors. Set by the first insertion.
    pub dims: Option<usize>,
    /// Storage: namespace -> immutable indexed namespace data.
    pub items: HashMap<String, Arc<NamespaceItems>>,
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

        let chunk_key: Arc<str> = make_chunk_key(doc_id, chunk_id).into();
        let item = Arc::new(StoredItem {
            key: Arc::clone(&chunk_key),
            embedding: vector,
            meta,
        });
        Arc::make_mut(self.items.entry(namespace.to_string()).or_default()).upsert(chunk_key, item);
        Ok(())
    }

    /// Delete all chunks belonging to a document within a namespace.
    ///
    /// If this leaves the store empty, the dimensionality constraint is reset.
    pub fn delete_doc(&mut self, namespace: &str, doc_id: &str) {
        let is_empty = if let Some(ns_items) = self.items.get_mut(namespace) {
            let ns_items = Arc::make_mut(ns_items);
            ns_items.delete_doc(doc_id);
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
    ) -> impl Iterator<Item = &'a StoredItem> + 'a {
        self.items
            .get(namespace)
            .into_iter()
            .flat_map(|ns_items| ns_items.iter())
    }

    /// Capture a consistent namespace view while holding the caller's store lock.
    ///
    /// Snapshot capture is O(1): it clones the namespace map's `Arc`, not its
    /// keys, vectors or metadata. A concurrent writer shallow-clones only the map
    /// of Arc-backed entries before mutation, leaving in-flight snapshots intact.
    pub(crate) fn namespace_snapshot(&self, namespace: &str) -> NamespaceSnapshot {
        NamespaceSnapshot {
            dims: self.dims,
            items: self.items.get(namespace).cloned().unwrap_or_default(),
        }
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
        normalize_query(&mut query);
        rank_normalized_query!(self.all_in_namespace(namespace), &query, k)
            .into_iter()
            .map(|hit| {
                let (doc_id, chunk_id) = split_chunk_key(hit.item.key.as_ref());
                (doc_id, chunk_id, hit.score)
            })
            .collect()
    }

    /// Searches with a query that has already been normalized in place.
    ///
    /// This is crate-private so API handlers that already own the query vector
    /// can avoid a second allocation and keep normalization outside the store
    /// read-lock. Callers must use [`normalize_query`] first.
    #[cfg(test)]
    #[inline(always)]
    pub(crate) fn search_normalized(
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

        rank_normalized_query!(self.all_in_namespace(namespace), query, k)
            .into_iter()
            .map(|hit| {
                let (doc_id, chunk_id) = split_chunk_key(hit.item.key.as_ref());
                (doc_id, chunk_id, hit.score)
            })
            .collect()
    }

    pub fn chunk_meta(&self, namespace: &str, doc_id: &str, chunk_id: &str) -> Option<&Value> {
        let chunk_key = make_chunk_key(doc_id, chunk_id);
        self.items
            .get(namespace)
            .and_then(|ns_items| ns_items.get(chunk_key.as_str()))
            .map(|item| &item.meta)
    }
}

impl NamespaceSnapshot {
    pub(crate) fn dims(&self) -> Option<usize> {
        self.dims
    }

    /// Search and materialize snippets from this immutable request snapshot.
    pub(crate) fn search_normalized_with_snippets(
        &self,
        query: &[f32],
        k: usize,
        _filters: &Value,
    ) -> Vec<(String, String, f32, String)> {
        if k == 0 {
            return Vec::new();
        }

        let Some(expected) = self.dims else {
            return Vec::new();
        };

        if expected != query.len() {
            tracing::warn!(
                expected,
                actual = query.len(),
                "vector dimensionality mismatch in snapshot search; returning no results"
            );
            return Vec::new();
        }

        rank_normalized_query!(self.items.iter(), query, k)
            .into_iter()
            .map(|hit| {
                let (doc_id, chunk_id) = split_chunk_key(hit.item.key.as_ref());
                let snippet = hit
                    .item
                    .meta
                    .get("snippet")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                    .to_string();
                (doc_id, chunk_id, hit.score, snippet)
            })
            .collect()
    }
}

#[derive(Debug, Error)]
pub enum VectorStoreError {
    #[error("embedding dimensionality mismatch: expected {expected}, got {actual}")]
    DimensionalityMismatch { expected: usize, actual: usize },
}

struct Hit<'a> {
    item: &'a StoredItem,
    score: f32,
}

impl<'a> PartialEq for Hit<'a> {
    fn eq(&self, other: &Self) -> bool {
        self.cmp(other) == Ordering::Equal
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
                let (doc_self, chunk_self) = split_chunk_key_ref(self.item.key.as_ref());
                let (doc_other, chunk_other) = split_chunk_key_ref(other.item.key.as_ref());

                // Invert so that smaller (doc,chunk) becomes "Greater"/better.
                doc_other
                    .cmp(doc_self)
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
        sum += ca[0] * cb[0]
            + ca[1] * cb[1]
            + ca[2] * cb[2]
            + ca[3] * cb[3]
            + ca[4] * cb[4]
            + ca[5] * cb[5]
            + ca[6] * cb[6]
            + ca[7] * cb[7];
    }

    for (x, y) in rem_a.iter().zip(rem_b.iter()) {
        sum += x * y;
    }

    sum
}

fn l2_norm(vector: &[f32]) -> f32 {
    vector.iter().map(|x| x * x).sum::<f32>().sqrt()
}

pub(crate) fn normalize_query(vector: &mut [f32]) {
    normalize(vector);
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
    fn prepared_search_matches_public_search() {
        let mut store = VectorStore::new();
        store
            .upsert("ns", "doc-a", "c1", vec![3.0, 4.0], Value::Null)
            .unwrap();
        store
            .upsert("ns", "doc-b", "c2", vec![4.0, 3.0], Value::Null)
            .unwrap();

        let query = vec![6.0, 8.0];
        let expected = store.search("ns", &query, 2, &Value::Null);
        let mut prepared = query;
        normalize_query(&mut prepared);
        let actual = store.search_normalized("ns", &prepared, 2, &Value::Null);

        assert_eq!(actual, expected);
    }

    #[test]
    fn prepared_search_preserves_zero_query_tie_order() {
        let mut store = VectorStore::new();
        store
            .upsert("ns", "doc-b", "c1", vec![1.0, 0.0], Value::Null)
            .unwrap();
        store
            .upsert("ns", "doc-a", "c1", vec![0.0, 1.0], Value::Null)
            .unwrap();

        let query = vec![0.0, 0.0];
        let expected = store.search("ns", &query, 2, &Value::Null);
        let mut prepared = query;
        normalize_query(&mut prepared);
        let actual = store.search_normalized("ns", &prepared, 2, &Value::Null);

        assert_eq!(actual, expected);
    }

    #[test]
    fn namespace_copy_on_write_reuses_unchanged_stored_items() {
        let mut store = VectorStore::new();
        store
            .upsert(
                "ns",
                "doc-a",
                "c1",
                vec![1.0, 0.0],
                serde_json::json!({"snippet": "a"}),
            )
            .unwrap();
        store
            .upsert(
                "ns",
                "doc-b",
                "c1",
                vec![0.0, 1.0],
                serde_json::json!({"snippet": "b"}),
            )
            .unwrap();

        let snapshot = store.namespace_snapshot("ns");
        let retained = Arc::clone(
            snapshot
                .items
                .entries
                .iter()
                .find(|item| item.key.as_ref() == make_chunk_key("doc-a", "c1"))
                .expect("doc-a is present"),
        );

        store
            .upsert(
                "ns",
                "doc-c",
                "c1",
                vec![1.0, 1.0],
                serde_json::json!({"snippet": "c"}),
            )
            .unwrap();

        let live = store.namespace_snapshot("ns");
        let reused = live
            .items
            .entries
            .iter()
            .find(|item| item.key.as_ref() == make_chunk_key("doc-a", "c1"))
            .expect("doc-a remains present");
        assert!(Arc::ptr_eq(&retained, reused));
    }

    #[test]
    fn namespace_snapshot_remains_consistent_after_live_mutation() {
        let mut store = VectorStore::new();
        store
            .upsert(
                "ns",
                "doc-a",
                "c1",
                vec![1.0, 0.0],
                serde_json::json!({"snippet": "old"}),
            )
            .unwrap();

        let original = store.namespace_snapshot("ns");
        store
            .upsert(
                "ns",
                "doc-a",
                "c1",
                vec![0.0, 1.0],
                serde_json::json!({"snippet": "new"}),
            )
            .unwrap();
        store
            .upsert(
                "ns",
                "doc-b",
                "c1",
                vec![1.0, 0.0],
                serde_json::json!({"snippet": "added"}),
            )
            .unwrap();
        let after_update = store.namespace_snapshot("ns");
        store.delete_doc("ns", "doc-a");

        let original_results =
            original.search_normalized_with_snippets(&[1.0, 0.0], 10, &Value::Null);
        assert_eq!(original_results.len(), 1);
        assert_eq!(original_results[0].0, "doc-a");
        assert_eq!(original_results[0].3, "old");
        assert!((original_results[0].2 - 1.0).abs() < f32::EPSILON);

        let updated_results =
            after_update.search_normalized_with_snippets(&[1.0, 0.0], 10, &Value::Null);
        assert_eq!(updated_results.len(), 2);
        assert_eq!(updated_results[0].0, "doc-b");
        assert_eq!(updated_results[0].3, "added");
        assert_eq!(updated_results[1].3, "new");

        let live_results = store
            .namespace_snapshot("ns")
            .search_normalized_with_snippets(&[1.0, 0.0], 10, &Value::Null);
        assert_eq!(live_results.len(), 1);
        assert_eq!(live_results[0].0, "doc-b");
    }

    #[test]
    fn search_with_k_zero_is_safe() {
        let mut store = VectorStore::new();
        store
            .upsert("ns", "d", "c", vec![1.0], Value::Null)
            .unwrap();
        let results = store.search("ns", &[1.0], 0, &Value::Null);
        assert!(results.is_empty());
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
            store
                .upsert(namespace, &format!("doc-{}", i), "chunk", vec, Value::Null)
                .unwrap();
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

        println!(
            "Search took avg: {:?} for {} iterations",
            duration / iterations,
            iterations
        );
    }
}
