//! Minimal HTTP server stub for the semantic index daemon (indexd).

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    indexd::run().await
}
