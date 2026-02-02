use indexd::VectorStore;
use serde_json::Value;

#[test]
fn test_prefix_sort_order() {
    let mut store = VectorStore::new();
    let meta = Value::Null;

    // "doc" is a prefix of "doc-extended"
    // In tuple sort: ("doc", "c1") < ("doc-extended", "c1")
    // In key sort with \u{241F}: "doc\u{241F}c1" vs "doc-extended\u{241F}c1"
    // "doc" matches. "\u{241F}" vs "-".
    // \u{241F} (9247) > '-' (45).
    // So "doc\u{241F}..." > "doc-extended..."
    // So "doc" will come AFTER "doc-extended".

    store
        .upsert("ns", "doc", "c1", vec![1.0], meta.clone())
        .unwrap();
    store
        .upsert("ns", "doc-extended", "c1", vec![1.0], meta.clone())
        .unwrap();

    let results = store.search("ns", &[1.0], 10, &Value::Null);

    assert_eq!(results.len(), 2);
    // Scores are equal.
    // doc_id asc.
    // "doc" should be first.
    assert_eq!(
        results[0].0, "doc",
        "Expected 'doc' first, but got '{}'",
        results[0].0
    );
    assert_eq!(results[1].0, "doc-extended");
}
