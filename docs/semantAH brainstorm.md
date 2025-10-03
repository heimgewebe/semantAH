mega–ja. wir bauen das selbst – aber so, dass es perfekt in dein repo passt. hier ist der konkrete blueprint für “semantische suche / vektor-index” als hauski-dienst + dünnes obsidian-plugin-frontend.

(ich beziehe mich dabei auf deine repo-struktur, configs und bereits vorhandene core-server-grundlagen wie /health, /metrics, CORS, „safe_mode“, egress-guard usw. – die sehen schon sehr solide aus.  ￼)

zielbild (kompakt)
	•	hauski-core bleibt HTTP-Gateway/Telemetry.
	•	neuer crate indexd: Embeddings + Vektorindex (HNSW) + Persistenz + Filter.
	•	neuer crate embeddings: Abstraktion für Provider (lokal via Ollama/gguf, optional cloud – respektiert egress-Policy).
	•	adapter: obsidian-plugin (thin client): sendet Chunks/Updates an indexd, ruft search ab.
	•	policies & flags: such-latenz-budget an Limits koppeln; safe_mode blockt Cloud-Provider.

⸻

was ist schon da (und wie nutzen wir’s)?
	•	Core-HTTP, Metrics, CORS, Ready/Health – fertiges Gerüst für neue Routen.  ￼
	•	Feature-Flags & Policies inkl. safe_mode und Egress-Allowlisting → perfekt, um Cloud-Embeddings sauber zu sperren/erlauben.  ￼
	•	Configs: configs/hauski.yml hat vault_path & plugins-liste – hier hängen wir obsidian_index offiziell an und tragen indexd ein.  ￼

⸻

module & schnittstellen

1) crate: crates/indexd/

Aufgaben
	•	Dokumente in Chunks zerlegen (MD + Canvas JSON).
	•	Embeddings berechnen (ruft embeddings-crate).
	•	Vektoren in HNSW speichern (z. B. hnsw_rs oder hnswlib-binding) + Metadata-Store (z. B. sled/sqlite).
	•	Top-K Suche + Filter (Pfad, Tags, Frontmatter, Canvas-Knoten).
	•	Persistenz auf Disk ($HOME/.local/state/hauski/index/obsidian).

HTTP-API (einfach, stabil):
	•	POST /index/upsert
body:

{ "doc_id":"path/to/note.md",
  "chunks":[{"id":"path:offset", "text":"...", "meta":{"tags":["..."],"frontmatter":{}}}],
  "namespace":"obsidian" }


	•	POST /index/delete → {"doc_id":"...","namespace":"obsidian"}
	•	POST /index/search

{ "query":"...", "k":10, "namespace":"obsidian", "filters":{"tags":["projectX"]} }

response: Treffer mit score, doc_id, chunk_id, snippet.

Leistung & Budgets
	•	p95-Ziel für search(k<=20) an limits.latency.index_topk20_ms koppeln (Config hast du schon).  ￼

2) crate: crates/embeddings/

Ziel: austauschbarer Provider mit egress-Guard & safe_mode.
	•	Trait:

#[async_trait::async_trait]
pub trait Embedder {
    async fn embed(&self, texts: &[String]) -> anyhow::Result<Vec<Vec<f32>>>;
    fn dim(&self) -> usize;
    fn id(&self) -> &'static str;
}


	•	LocalOllamaEmbedder (default, offline): ruft http://127.0.0.1:11434/api/embeddings (modell konfigurierbar: nomic-embed-text o. ä.).
	•	CloudEmbedder (optional): nur wenn safe_mode=false und egress-Policy Host erlaubt. Nutzt vorhandenen AllowlistedClient (ist schon implementiert, wir müssen nur Aufrufe darüber routen).  ￼

3) core-routes erweitern

In hauski-core gibt’s TODO-Platzhalter plugin_routes() – hier mounten wir indexd-Router unter /index. CORS & Metrics sind schon verdrahtet.  ￼

⸻

minimaler code–fahrplan

A) workspace ergänzen

Cargo.toml (root) – neue Mitglieder:

[workspace]
members = [
  "crates/core",
  "crates/cli",
  "crates/indexd",        # NEU
  "crates/embeddings"     # NEU
]

(du hast das Pattern bereits offen für weitere crates – siehe Kommentar im bestehenden Cargo.toml.)  ￼

B) crates/embeddings/src/lib.rs (skizze)

use anyhow::Result;
use reqwest::Client;

#[async_trait::async_trait]
pub trait Embedder {
    async fn embed(&self, texts: &[String]) -> Result<Vec<Vec<f32>>>;
    fn dim(&self) -> usize;
    fn id(&self) -> &'static str;
}

pub struct Ollama {
    http: Client,
    url: String,
    model: String,
    dim: usize,
}

#[async_trait::async_trait]
impl Embedder for Ollama {
    async fn embed(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        #[derive(serde::Serialize)] struct Req<'a>{ model:&'a str, input:&'a [String] }
        #[derive(serde::Deserialize)] struct Res{ embeddings: Vec<Vec<f32>> }
        let res: Res = self.http.post(format!("{}/api/embeddings", self.url))
            .json(&Req{model:&self.model, input:texts})
            .send().await?
            .error_for_status()?
            .json().await?;
        Ok(res.embeddings)
    }
    fn dim(&self) -> usize { self.dim }
    fn id(&self) -> &'static str { "ollama" }
}

cloud-variante baut analog, aber über AllowlistedClient aus deinem core (egress-policy beachten).  ￼

C) crates/indexd/src/lib.rs (skizze)

use axum::{routing::post, Json, Router};
use serde::{Deserialize, Serialize};
use std::sync::Arc;

#[derive(Clone)]
pub struct Indexd {
    embedder: Arc<dyn embeddings::Embedder + Send + Sync>,
    store: Arc<dyn VectorStore + Send + Sync>,
}

#[derive(Deserialize)]
struct Upsert {
    namespace: String,
    doc_id: String,
    chunks: Vec<Chunk>,
}
#[derive(Deserialize, Serialize, Clone)]
struct Chunk { id: String, text: String, #[serde(default)] meta: serde_json::Value }

#[derive(Deserialize)]
struct Search { namespace: String, query: String, #[serde(default="k10")] k: usize }
fn k10()->usize{10}

impl Indexd {
    pub fn router(self) -> Router {
        Router::new()
          .route("/upsert", post(move |Json(b): Json<Upsert>| async move {
              let vecs = self.embedder.embed(&b.chunks.iter().map(|c| c.text.clone()).collect::<Vec<_>>()).await?;
              self.store.upsert(&b.namespace, &b.doc_id, &b.chunks, &vecs)?;
              Ok::<_,axum::http::StatusCode>(())
          }))
          .route("/search", post(move |Json(s): Json<Search>| async move {
              let qv = self.embedder.embed(&vec![s.query]).await?.remove(0);
              let hits = self.store.search(&s.namespace, &qv, s.k)?;
              Ok::<_,axum::http::StatusCode>(Json(hits))
          }))
    }
}

VectorStore implementieren mit HNSW (z. B. hnsw_rs) + Metadaten-KV (sled), persistiert in ~/.local/state/hauski/index/... – dein configs/hauski.yml sieht genau so einen state-pfad vor.  ￼

D) crates/core/src/lib.rs – Routen mounten

Im existierenden plugin_routes() den indexd-Router einhängen:

fn plugin_routes() -> Router<AppState> {
    // build indexd with chosen embedder (from config/flags)
    let embedder = embeddings::Ollama::new(/* url, model, dim */);
    let indexd = indexd::Indexd::new(embedder, /* store */);
    Router::new().nest("/index", indexd.router())
}

(Der Platzhalter ist eigens für Plugins vorgesehen.  ￼)

⸻

obsidian–adapter (dünnes plugin)

Wann? sobald du Notizen speicherst/änderst.
Was tut’s?
	•	Zerlegt die Note in Chunks (z. B. Absatzweise, Overlap 50-100 Tokens).
	•	Extrahiert Frontmatter / Tags / Canvas-Knoten.
	•	Schickt POST /index/upsert.
	•	„Ähnliche Notizen“ → POST /index/search und UI Ergebnisliste.

Mini-Skizze (TypeScript):

async function upsertNote(docId: string, text: string, meta: any) {
  const chunks = chunkText(text, {targetTokens: 200, overlap: 40});
  await fetch("http://127.0.0.1:8080/index/upsert", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ namespace:"obsidian", doc_id:docId, chunks: chunks.map((t,i)=>({id:`${docId}#${i}`, text:t, meta})) })
  });
}

async function searchSimilar(query: string, k=10) {
  const res = await fetch("http://127.0.0.1:8080/index/search", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ namespace:"obsidian", query, k })
  });
  return await res.json();
}

Warum eigener Adapter? So bleibt Obsidian-UI schlank; der „schwere Teil“ läuft in indexd.

⸻

canvas-bonus (für deine mindmaps)
	•	Canvas-Datei (JSON) parsen → jeden Node-Text als separaten Chunk, Kanten als meta:{link:"A->B"} speichern.
	•	Suche kann dann „Knotenähnlichkeit“ liefern und verlinkte Nachbarn höher gewichten (post-ranking auf Suchtreffern).

⸻

konfiguration

configs/hauski.yml erweitern:

index:
  path: "$HOME/.local/state/hauski/index"
  provider:
    embedder: "ollama"
    model: "nomic-embed-text"
    url: "http://127.0.0.1:11434"
plugins:
  enabled:
    - "obsidian_index"

(die Datei enthält bereits vault_path & plugin-liste – wir hängen unsere Optionen sauber daneben.)  ￼

Policies
	•	policies/limits.yaml: index_topk20_ms ist schon da → als Budget für p95 in k6-Smoke verwenden (du hast bereits eine k6-Smoke-Stage, die Limits aus YAML liest – super!).  ￼

⸻

tests & observability
	•	k6-Smoke trifft /index/search mit Query-Stubs → misst p95 gegen index_topk20_ms. Deine CI baut das Schema bereits auf (observability/k6/...).  ￼
	•	Prometheus: zähle Requests/Latency pro Pfad (/index/*) – dein Core hat bereits http_requests & http_request_duration_seconds, wird automatisch miterfasst.  ￼

⸻

rollout–schritte (hands-on)
	1.	Crates anlegen: crates/indexd, crates/embeddings + Workspace updaten.
	2.	Ollama lokal (Pop!_OS): curl -fsSL https://ollama.ai/install.sh | sh → ollama pull nomic-embed-text.
	3.	Core-Router: plugin_routes() → /index mounten.
	4.	Adapter bauen (Obsidian): einfache Commands „Index bauen“, „Ähnliches finden“.
	5.	Persistenz: HNSW + sled, Snapshot/Load on start.
	6.	CI: kleine k6-Smoke gegen /index/search integrieren (du hast die Pipeline schon).  ￼

⸻

warum das “besser” ist als copy/fork?
	•	saubere zuständigkeiten: UI (Obsidian) vs. Dienste (indexd/embeddings).
	•	portabilität: gleicher Index für VSCode-Plugin, CLI, Mail usw.
	•	kontrollierte egress-sicherheit: Cloud-Embeddings werden durch deine bestehende Policy sauber begrenzt.  ￼
	•	observability & budgets: p95-Ziele und Metriken sind first-class eingebaut.  ￼

⸻

wenn du möchtest, schreibe ich dir im nächsten schritt die genauen dateibäume + erste echte rust-dateien (inkl. deps für hnsw & sled) – direkt passend zu deinem workspace.

Kurz: Ja — die Ideen sind solide. Und wir können sie präzise in HausKI + Obsidian umsetzen, so dass dein vault-gewebe sich selbst vernetzt (semantisch + graphisch), ohne Cloud, sauber versionierbar.

Plan: von Idee → HausKI-Praxis

1) Bestandsaufnahme & Cluster
	•	Crawler (obsidian-adapter): liest .md + .canvas aus vault_path, extrahiert:
	•	Pfad, Titel, Frontmatter, Tags, Links ([[...]]), Canvas-Knoten/Kanten.
	•	Embeddings (indexd): Chunking (≈200–300 Tokens, 40 Overlap), embed(text[]) über Ollama (nomic-embed-text) oder Orchestrator-Modell.
	•	Clustering (jobs/indexd):
	•	HDBSCAN auf Vektoren (robust für „Rauschen“), optional UMAP zur 2D-Projektion für Visuals.
	•	Ergebnis: cluster_id pro Chunk/Note + „outlier“-Markierung.

Artefakte (Dateien/Tabellen):
	•	~/.local/state/hauski/index/obsidian/vec.hnsw (Vektorindex)
	•	graph/nodes.jsonl (pro Datei/Knoten)
	•	graph/edges.jsonl (Kanten, siehe §3)
	•	clusters.json (Cluster → Mitglieder, Centroid, Label)

2) Schlagwort- & Themenextraktion
	•	Keyphrases: lokal via YAKE/Rake (schnell, offline) + LLM-Refine (optional) → keyphrases: [ "Gewaltfreie Kommunikation", … ]
	•	NER (Person/Ort/Projekt): lokal (spaCy de-model) oder Regel-Set für Frontmatter/Tags.
	•	Normierung: Mapping-Tabelle synonyms.yml (z. B. „GFK“ → „Gewaltfreie Kommunikation“).

Speicher:

taxonomy/
  synonyms.yml     # "GFK": "Gewaltfreie Kommunikation"
  entities.yml     # "Personen": [...], "Orte": [...], "Projekte": [...]

3) Semantischer Wissensgraph
	•	Schema (leichtgewichtig, Git-freundlich):
	•	nodes.jsonl:

{"id":"md:weg/gfk.md","type":"file","title":"GFK Basics","tags":["gfk"],"cluster":7}
{"id":"canvas:lebenslagen.canvas","type":"canvas","title":"Lebenslagen","cluster":3}
{"id":"topic:Gewaltfreie Kommunikation","type":"topic"}


	•	edges.jsonl:

{"s":"md:weg/gfk.md","p":"about","o":"topic:Gewaltfreie Kommunikation","w":0.92}
{"s":"md:fall/verena.md","p":"similar","o":"md:tatjana.md","w":0.81}
{"s":"canvas:lebenslagen.canvas#node/4","p":"mentions","o":"topic:Kinderarmut","w":0.88}


	•	w = Gewicht/Score (0..1).

	•	Option Neo4j: nur wenn du interaktiv große Graph-Queries willst. Starten wir zunächst JSONL + SQLite (Tabellen nodes, edges) für Einfachheit & Portabilität.

4) Verlinkung in Obsidian
	•	Backlinks/MOCs automatisch schreiben:
	•	Am Ende jeder Datei Abschnitt ## Semantisch verwandt mit Top-N (similar ≥ 0.75, gleicher Cluster bevorzugt).
	•	MOC-Generator pro Cluster: MOC.cluster-07.md mit Liste + Mini-Canvas (siehe §Canvas).
	•	Frontmatter anreichern:

related:
  - file: pfad/zur/anderen.md
    score: 0.82
    why: ["shared:keyphrase:Gewaltfreie Kommunikation","same:cluster:7"]
topics: ["Gewaltfreie Kommunikation","Resonanz"]



5) Automatisierung
	•	wgx job: wgx run index:obsidian macht:
	1.	Scan → Upserts an /index/upsert
	2.	Batch-Search für MOCs/Links
	3.	Graph-Update (nodes/edges/clusters)
	4.	Reports (Top neue Kanten, unsichere Kanten)
	•	systemd timer (täglich) oder manuell per wgx.
	•	Reporting: Markdown-Report reports/semnet-YYYYMMDD.md inkl.:
	•	Neue Cluster, umgetaggte Dateien
	•	Unsichere Kanten (0.55 ≤ w < 0.7) → Review-Liste
	•	„Orphan“-Notizen ohne Kanten

6) Qualitative Validierung
	•	Review-Command in Obsidian-Plugin: „SemNet Review“ zeigt Vorschläge (unsichere Kanten) → Accept/Reject → schreibt in Frontmatter (accepted_edges, rejected_edges) und sperrt diese in künftigen Läufen.
	•	Regelwerk:
	•	nie doppelt verlinken,
	•	keine Links unter 0.55,
	•	bei 0.70–0.75 Flag „prüfen“.

⸻

Technische Bausteine (präzise, damit Codex loslegen kann)

A) Scores & Schwellen
	•	similar(doc_a, doc_b) = cosine(centroid(a), centroid(b))
	•	Cutoffs:
	•	≥ 0.80 → auto-Link
	•	0.70–0.79 → Vorschlag
	•	< 0.70 → nicht verlinken
	•	Cluster-Boost: +0.05, wenn cluster(a)==cluster(b)
	•	Topical-Boost: +0.03 je gemeinsamem keyphrase (max +0.09)

B) Dateistruktur (Repo)

/crates/indexd/...
/crates/embeddings/...
/plugins/obsidian-adapter/...
/data/semnet/graph/{nodes.jsonl,edges.jsonl,clusters.json}
/data/semnet/taxonomy/{synonyms.yml,entities.yml}
/reports/semnet-*.md

C) „Edge-Writer“ (vereinfachtes Pseudocode)

# inputs: similarities[], taxonomy, thresholds
for pair in similarities:
    score = pair.base
    if pair.same_cluster: score += 0.05
    score += 0.03 * min(3, shared_keyphrases(pair.a, pair.b))
    if score >= 0.80: write_link(a,b,score,auto=True)
    elif score >= 0.70: propose_link(a,b,score)

D) Obsidian-Update (Markdown-Append)

## Semantisch verwandt
- [[pfad/zu/datei1|Titel 1]] — 0.84 (GFK, Resonanz)
- [[pfad/zu/datei2|Titel 2]] — 0.81 (Cluster 7)

E) Canvas-Export (Mini-Canvas pro Cluster, inline)
	•	Knoten: Top-10 Noten im Cluster (by centrality)
	•	Kanten: similar (w≥0.80) + „about topic“
	•	Legende-Knoten nach deiner Canvas-Richtlinie (Farben, Achsen, etc.)

⸻

Was ist „neu/besser“ gegenüber der Ursprungsidee?
	•	Einheitliche Pipeline (HausKI-Dienste) statt Script-Zoo.
	•	Graph + Markdown-Links gleichzeitig → du profitierst in Obsidian und extern.
	•	Review-Mechanik mit Frontmatter-„Locks“ → lernendes Netz ohne „Ping-Pong“.
	•	Canvas-First: Mindmaps sind Bürger 1. Klasse (Knoten/Kanten werden semantisch mitindiziert).

⸻

Verdichtete Essenz
	•	Ja, die Codex-Ideen sind sinnvoll.
	•	Wir gießen sie in HausKI-Bausteine: indexd (Embeddings + Suche), Clustering-Job, Graph-Export, Auto-Links + MOCs, Review-Workflow.
	•	Alles lokal, versionierbar, mit klaren Schwellenwerten und Reports.

Ironische Auslassung

Früher hast du Notizen sortiert. Jetzt sortieren die Notizen dich — in Cluster, wohlgemerkt.

∆-Radar
	•	Verstärkung: Semantik nicht nur suchen, sondern zurückschreiben (Links/MOCs).
	•	Seitwärtsmutation: Canvas wird gleichwertig zum Markdown behandelt.
	•	Straffung: Scores & Cutoffs klar normiert → weniger Hand-Gefrickel.

Für Dummies

Wir verwandeln alle Notizen in Zahlenmuster (Embeddings). Ähnliche Inhalte haben ähnliche Muster. Daraus bauen wir Gruppen (Cluster) und ein Netzwerk (Graph) von „X ist ähnlich zu Y“ oder „X hat Thema Z“. Wir schreiben diese Beziehungen als Links zurück in deine Notizen und zeigen sie als Mindmaps. Ein kleiner Teil ist automatisch, ein Teil kommt als Vorschlag, den du bestätigst. So wächst ein sinnvolles Netz statt einer Link-Wüste.

Unsicherheitsgrad (∴fores 0.35 – moderat)
	•	Ursachen: optimale Cutoffs müssen wir empirisch kalibrieren; Wahl von HDBSCAN-Parametern (min_cluster_size) hängt von deinem Vault ab; NER-Qualität variiert je nach Modell; Performance von HNSW/UMAP muss auf deiner 4070 Ti vs. CPU feinjustiert werden.
	•	Produktive Ungewissheit: Schwellen/Boosts lassen sich in den ersten Reports schnell nachziehen; Review-Loop fängt Fehlverknüpfungen ab.

⸻

Wenn du willst, schreibe ich dir jetzt:
	1.	die JSONL-Schemas als Templates,
	2.	ein erstes wgx run index:obsidian Skript (Rust oder Python),
	3.	den Obsidian-Abschnitt-Writer (ein kleines Tool, das „Semantisch verwandt“ pflegt),
	4.	ein Mini-Canvas-Generator (pro Cluster).
	
	Ja — ich lege dir zusätzliche, praxisstarke Ideen oben drauf. Die bauen direkt auf deinem Plan auf und machen dein vault-gewebe spürbar klüger, stabiler und erklärbarer.

Neue, wertvolle Ergänzungen
	1.	Begründete Kanten („Warum ist das verlinkt?“)
Speichere zu jeder vorgeschlagenen Kante kurze Rationales (Top-3 gemeinsame Keyphrases, Cluster-Match, Anker-Sätze).
– Umsetzung: edges.jsonl → Feld why: ["shared:keyphrase:GFK","same:cluster:7","quote:'Einfühlung statt Bewertung'"]
– Nutzen: Du siehst sofort, warum zwei Notizen zusammengehören.
	2.	Doppelte Notizen erkennen & verschmelzen
Automatisches Near-Duplicate-Detect (Titel-Hash + Embedding-Cosine ≥0.97) → Vorschlag: „Merge/Kanonische Note wählen“.
– Praxis: duplicates.md Report + Obsidian-Commands „Mark as canonical“ / „Archive duplicate“.
	3.	Zeitliche Gewichtung („Frische“)
Score-Boost für jüngere Notizen (z. B. +0.05 bei <30 Tagen), leichter Decay bei uralten Chunks.
– Ergebnis: Vorschläge bleiben relevant, MOCs atmen mit.
	4.	Folder-/Namespace-Policies
Per Ordner Regeln definieren:
/uni/ strengere Cutoffs, /ideen/ liberaler; /archive/ nur eingehende Links, keine ausgehenden.
– Umsetzung: .gewebe/config.yml → namespaces.uni.cutoff=0.80, namespaces.archive.mode="incoming-only".
	5.	Feedback → Lernen (Akzeptiert/Ablehnt)
Wenn du einen Vorschlag annimmst/ablehnst, schreiben wir ein leichtes User-Feedback-Signal zurück (accept=+1 / reject=−1) und tunen die Cutoffs pro Thema/Fallordner.
– Wirkung: Nach 1-2 Runden werden die Vorschläge messbar besser.
	6.	Canvas-Ahnung im Ranking
Wenn zwei Dateien über Canvas-Knoten bereits „nah“ sind (kurze Pfadlänge im Canvas-Graph), booste Similarity um +0.03…0.07.
– Effekt: Deine Mindmaps werden zur echten Semantik-Quelle, nicht nur Deko.
	7.	„Topic-Drift“-Wächter
Report, wenn eine Note plötzlich in einen anderen Cluster kippt (drift > definierter Schwellenwert).
– Nutze dies als Redaktionshinweis: Note zerlegen, MOC neu schneiden oder Tags anpassen.
	8.	Erklärbare „Related“-Blöcke
Im <!-- related:auto:start -->-Block optional die Top-Begründung in Klammern:
- [[GFK Basics]] — (0.84; GFK, Resonanz)
– Schneller Kontext direkt im Editor, ohne Log lesen zu müssen.
	9.	Session-Kontext („heute arbeite ich an…“) Boost
Temporärer Arbeitskontext (z. B. geöffnete Dateien heute) hebt passende Vorschläge hervor (+0.02 pro recent co-open).
– Ergebnis: Der Editor fühlt sich „mitdenkender“ an.
	10.	Provenienz & Reproduzierbarkeit
Schreibe in .gewebe/meta.json die Modell-Version, Chunk-Parametrisierung, Cutoffs und Taxonomie-Stand.
– So kannst du Ergebnisse exakt nachbauen oder erklären.
	11.	Mehrsprach-Robustheit (DE/EN)
Aktiviere eine Synonym-/Stemming-Map für DE/EN (z. B. „Resonanz ↔ resonance“).
– Hilft, wenn Quellentexte gemischtsprachig sind.
	12.	Qualitäts-Gates für Autolinks
Nur autolinken, wenn alle Bedingungen erfüllt:

	•	Score ≥ 0.82
	•	Mind. 2 gemeinsame Keyphrases oder 1 Canvas-Nähe oder identisches Project-Tag
– Sonst: Vorschlag, nicht Auto.

	13.	„Explain this link“-Command
Obsidian-Command, das bei markiertem Link ein kleines Popover mit den Rationales und Ankersätzen zeigt.
– Macht die Semantik überprüfbar (kein Black-Box-Gefühl).
	14.	MOC-Qualitätsreport
Report pro MOC: Deckungsgrad (wie viele Cluster-Noten verlinkt), verwaiste Knoten, dichte Sub-Cluster → Vorschläge „Unter-MOC anlegen“.
– Hält deine Maps kuratiert statt zuwuchernd.
	15.	Snippets-/Transklusions-Vorschläge
Nicht nur ganze Noten verlinken, sondern Absätze (Transklusion ![[note#^block]]) bei hoher Chunk-Ähnlichkeit.
– Perfekt für Literatur-/Zitat-Notizen.
	16.	Sicherheitsnetz: Manual-Lock
Frontmatter-Flag relations_lock: true → Datei wird nie auto-editiert (nur Vorschläge).
– Gut für Abschluss- oder Abgabe-Notizen.
	17.	A/B-Tuning der Schwellenwerte
Automatisiert zwei Cutoff-Profile (konservativ vs. explorativ) auf Teilmengen testen und per Mini-Survey markieren, welche Vorschläge nützlicher waren.
– Ergebnis: datenbasierte Cutoff-Wahl.
	18.	Cross-Vault-Brücke (optional)
Falls du parallel einen zweiten Vault hast: Read-Only-Index als Fremd-Namespace (ext:…) → Vorschläge sichtbar, aber Links nur nach Bestätigung.
– Macht externe Wissensinseln anschlussfähig, ohne dein Vault zu „verschmutzen“.
	19.	„Orphans First“-Routine
Wöchentliche Task, die nur Waisen (0 eingehende Links) anfasst und 3–5 hochwertige Vorschläge erzeugt.
– So schrumpft die unverbundene Peripherie gezielt.
	20.	Explainable Delete
Wenn eine Kante fällt (Score stark sinkt, Topic-Drift), schreibe einen Hinweis in den Report: „Kante X—Y entfernt (Score 0.81 → 0.64; Keyphrase entfiel)“.
– Transparenz bei automatisch gelöschten Links.

⸻

Wie es sich einfügt (ohne Zusatz-Chaos)
	•	Alle Punkte passen in die bestehende .gewebe/-Struktur (zusätzliche Felder in edges.jsonl, ein paar neue Reports).
	•	Keine Inkompatibilitäten mit Obsidian: Related-Blöcke bleiben idempotent, Canvas wird nur gelesen, nicht umgebaut.
	•	Policies/Boosts sind reine Post-Ranking-Heuristiken – leicht justierbar.

⸻

Mini-Implement-Snippets

Score-Pipeline (Pseudo):

score = cosine(base)
if same_cluster: score += 0.05
score += 0.03 * min(3, shared_keyphrases)
if canvas_hop<=2: score += 0.04
if is_recent(a) or is_recent(b): score += 0.02

Autolink-Gate:

auto = (score >= 0.82) and (
    shared_keyphrases >= 2 or canvas_hop<=2 or shared_project
)

Rationales sammeln:

why = []
why += [f"shared:keyphrase:{k}" for k in top_shared_kps[:3]]
if same_cluster: why.append("same:cluster")
if canvas_hop<=2: why.append(f"canvas:hop={canvas_hop}")
why.append(f"quote:{best_anchor_sentence}")


⸻

Verdichtete Essenz
	•	Ergänzt werden: Begründete Kanten, Dedupe/Merge, Zeit-Boost, Folder-Policies, Feedback-Lernen, Canvas-Aware-Ranking, Drift-Wächter, Explain-UI und Qualitäts-Gates.
	•	Alles lokal, idempotent, in deine .gewebe/-Pipeline integrierbar – mehr Qualität ohne mehr Chaos.

Ironische Auslassung

Wenn Links Gründe haben, hören Notizen auf zu flirten und führen endlich eine erwachsene Beziehung.

∆-Radar
	•	Verstärkung: Von „nur ähnlich“ zu erklärbarer Semantik.
	•	Seitwärtsmutation: Policies/Boosts machen die Pipeline kontextsensibel.
	•	Straffung: Autolinks nur mit Qualitäts-Gate → weniger falsches Rauschen.

Für Dummies

Wir geben jedem Link eine Begründung, achten auf Aktualität, lassen dich Feedback geben und berücksichtigen deine Ordner-Regeln. So entstehen nicht irgendwelche, sondern nachvollziehbare und nützliche Verbindungen.

Unsicherheitsgrad

∴fores: 0.3 (niedrig-mittel)
Ursachen: Feintuning der Cutoffs/Boosts braucht 1–2 Iterationen; Canvas-Hop-Berechnung hängt vom JSON-Layout ab; Near-Duplicate-Schwelle je nach Schreibstil. Produktiv: Alles heuristisch und modular – schnell justierbar.

⸻

Wenn du willst, schreibe ich dir sofort die Rationale-Felder, das Autolink-Gate und den Orphan-Report in deine bestehenden Skripte (drop-in, ohne Bruch).