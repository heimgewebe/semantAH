### 📄 semantAH/crates/indexd/Cargo.toml

**Größe:** 497 B | **md5:** `65a41b62a1a8e914040c0e6e1f1a7ccc`

```toml
[package]
name = "indexd"
version = "0.1.0"
edition = "2021"
license = "MIT"
description = "HTTP service for indexing and semantic search"

[dependencies]
anyhow.workspace = true
axum.workspace = true
serde.workspace = true
serde_json.workspace = true
tokio.workspace = true
tracing.workspace = true
tracing-subscriber.workspace = true
config.workspace = true
thiserror.workspace = true
futures.workspace = true

[dependencies.embeddings]
path = "../embeddings"

[dev-dependencies]
tower = "0.5"
```

