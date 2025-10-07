pub mod store;

use tokio::sync::RwLock;

#[derive(Debug)]
pub struct AppState {
    pub store: RwLock<store::VectorStore>,
}

impl AppState {
    pub fn new() -> Self {
        Self {
            store: RwLock::new(store::VectorStore::new()),
        }
    }
}

impl Default for AppState {
    fn default() -> Self {
        Self::new()
    }
}

pub use store::{VectorStore, VectorStoreError};
