//! Minimal HTTP server stub for the semantic index daemon (indexd).

use indexd::api;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    indexd::run(api::router).await
}
