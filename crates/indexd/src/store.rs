use std::collections::HashMap;

use serde_json::Value;
use thiserror::Error;

const KEY_SEPARATOR: &str = "\u{241F}";

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
    }

    pub fn all_in_namespace<'a>(
        &'a self,
        namespace: &'a str,
    ) -> impl Iterator<Item = (&'a (String, String), &'a (Vec<f32>, Value))> + 'a {
        self.items
            .iter()
            .filter(move |((ns, _), _)| ns == namespace)
    }
}

#[derive(Debug, Error)]
pub enum VectorStoreError {
    #[error("embedding dimensionality mismatch: expected {expected}, got {actual}")]
    DimensionalityMismatch { expected: usize, actual: usize },
}

fn make_chunk_key(doc_id: &str, chunk_id: &str) -> String {
    format!("{doc_id}{KEY_SEPARATOR}{chunk_id}")
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
    }
}
