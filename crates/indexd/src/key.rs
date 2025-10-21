pub(crate) const KEY_SEPARATOR: &str = "\u{241F}";

pub(crate) fn make_chunk_key(doc_id: &str, chunk_id: &str) -> String {
    format!("{doc_id}{KEY_SEPARATOR}{chunk_id}")
}

pub(crate) fn split_chunk_key(key: &str) -> (String, String) {
    match key.split_once(KEY_SEPARATOR) {
        Some((doc_id, chunk_id)) => (doc_id.to_string(), chunk_id.to_string()),
        None => (key.to_string(), String::new()),
    }
}
