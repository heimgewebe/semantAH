# HausKI-Integration

HausKI bleibt das lokale Orchestrierungs-Gateway. semantAH ergänzt es als semantische Gedächtnis-Schicht. Dieser Leitfaden beschreibt, wie die neuen Komponenten (`indexd`, `embeddings`, Obsidian-Adapter) eingebunden werden und welche Policies greifen.

---

## Architekturüberblick

1. **`crates/embeddings`** – stellt den `Embedder`-Trait bereit und kapselt Provider:
   - `Ollama` (lokal, offline) ruft `http://127.0.0.1:11434/api/embeddings` auf.
   - `CloudEmbedder` (optional) nutzt HausKIs AllowlistedClient. Aktiv nur, wenn `safe_mode=false` und der Zielhost in der Egress-Policy freigeschaltet ist.
2. **`crates/indexd`** – HTTP-Service mit Routen:
   - `POST /index/upsert` – nimmt Chunks + Metadaten entgegen und legt Vektoren im HNSW-Index ab.
   - `POST /index/delete` – entfernt Dokumente aus einem Namespace.
   - `POST /index/search` – Top-k-Suche mit Filtern (Tags, Projekte, Pfade).
   - Persistenz liegt unter `~/.local/state/hauski/index/<namespace>/`.
3. **Obsidian-Adapter (Thin Plugin)** – zerlegt Notizen und Canvas-Dateien, sendet Upserts an HausKI und ruft Suchergebnisse für „Related“/Command-Paletten ab.
4. **Policies & Observability** – bestehende Features (CORS, `/health`, `/metrics`, `safe_mode`, Latency-Budgets) gelten auch für `/index/*`.

---

## Workspace-Konfiguration

`Cargo.toml` (Workspace):

```toml
[workspace]
members = [
  "crates/core",
  "crates/cli",
  "crates/indexd",
  "crates/embeddings"
]
```

`crates/embeddings/src/lib.rs` definiert den Trait und z. B. `Ollama`:

```rust
#[async_trait::async_trait]
pub trait Embedder {
    async fn embed(&self, texts: &[String]) -> anyhow::Result<Vec<Vec<f32>>>;
    fn dim(&self) -> usize;
    fn id(&self) -> &'static str;
}
```

Implementierungen greifen auf `reqwest::Client` zurück. Cloud-Varianten müssen über HausKIs AllowlistedClient laufen, um Egress-Guards einzuhalten.

`crates/indexd` kapselt Embedder + Vektorstore (HNSW + Metadata-KV, z. B. `sled`). Der Router wird in `core::plugin_routes()` unter `/index` gemountet:

```rust
fn plugin_routes() -> Router<AppState> {
    let embedder = embeddings::Ollama::new(/* url, model, dim */);
    let store = indexd::store::hnsw(/* state_path */);
    Router::new().nest("/index", indexd::Indexd::new(embedder, store).router())
}
```

---

## HTTP-API

### Upsert

```http
POST /index/upsert
{
  "namespace": "obsidian",
  "doc_id": "notes/gfk.md",
  "chunks": [
    {"id": "notes/gfk.md#0", "text": "...", "meta": {"topics": ["gfk"], "frontmatter": {...}}}
  ]
}
```

### Delete

```http
POST /index/delete
{"namespace": "obsidian", "doc_id": "notes/gfk.md"}
```

### Search

```http
POST /index/search
{
  "namespace": "obsidian",
  "query": "empatische Kommunikation",
  "k": 10,
  "filters": {"topics": ["gfk"], "projects": ["wgx"]}
}
```

Antwort: Treffer mit Score, Dokument/Chunk-ID, Snippet, Rationales (`why`).

---

## Persistenz & Budgets

- Indexdaten leben im `index.path` aus der HausKI-Config (`~/.local/state/hauski/index`).
- HNSW-Index + Sled/SQLite halten Embeddings und Metadaten.
- Latency-Budgets: `limits.latency.index_topk20_ms` (Config) definiert das p95-Ziel. K6-Smoke nutzt diesen Wert als Assertion.
- Prometheus-Metriken für `/index/*` werden automatisch vom Core erfasst (`http_requests_total`, `http_request_duration_seconds`).

---

## Konfiguration (`configs/hauski.yml`)

```yaml
index:
  path: "$HOME/.local/state/hauski/index"
  provider:
    embedder: "ollama"
    model: "nomic-embed-text"
    url: "http://127.0.0.1:11434"
    dim: 768
  namespaces:
    obsidian:
      auto_cutoff: 0.82
      suggest_cutoff: 0.70
      policies:
        allow_autolink: true
        folder_overrides:
          archive:
            mode: incoming-only
plugins:
  enabled:
    - obsidian_index
```

`safe_mode: true` sperrt Cloud-Provider automatisch. Namespaces können weitere Regeln (z. B. strengere Cutoffs) erhalten.

---

## Obsidian-Plugin (Adapter)

- Hook auf `onSave` / `metadataCache.on("changed")`.
- Chunking (200–300 Tokens, 40 Overlap), Canvas-JSON-Knoten werden zusätzliche Chunks.
- Sendet `POST /index/upsert` mit Frontmatter/Tags/Canvas-Beziehungen im `meta`-Feld.
- Command „Semantisch ähnliche Notizen“ → `POST /index/search` und Anzeige der Ergebnisse.
- Optionaler Review-Dialog für Vorschläge (Accept/Reject → Frontmatter `accepted_edges` / `rejected_edges`).

---

## Automatisierung & Tests

- `wgx run index:obsidian` ruft der Reihe nach `build_index`, `build_graph`, `update_related` auf.
- systemd-Timer führt `make all` nightly aus (siehe `docs/blueprint.md`).
- CI/K6: Smoke-Test gegen `/index/search` mit Query-Stubs → prüft p95 < `limits.latency.index_topk20_ms`.

---

## Mehrwert

- Saubere Zuständigkeiten (UI vs. Dienste).
- Egress-kontrollierte Einbindung externer Provider.
- Explainable Scores via `why`-Feld.
- Reports & Policies sorgen für qualitätsgesicherte Auto-Links.

> *Ironische Auslassung:* HausKI bleibt der Türsteher – aber semantAH entscheidet, wer auf die VIP-Liste der Notizen kommt.

