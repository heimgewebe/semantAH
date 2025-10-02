<!--
Quelle: /home/alex/vault-gewebe/coding/semantAH/semantAH.md
-->

Alles klar – ich setze dir jetzt die finale, maximal umfassende Blaupause für dein vault-gewebe auf. Damit hast du einen selbstvernetzenden Wissensspeicher, der semantische Suche, Clustering, Graph, Backlinks, MOCs, Canvas-Integration und Qualitätssicherung kombiniert – alles lokal, reproduzierbar und mit Reports.

⸻

🔵 Vault-Gewebe – Finale Blaupause

0. Systemordner & Konventionen
	•	.gewebe/ (zentraler Ordnungsbaum)

.gewebe/
  config.yml           # Parameter (Modelle, Cutoffs, Policies)
  embeddings.parquet   # Chunks + Vektoren
  nodes.jsonl          # Graph-Knoten
  edges.jsonl          # Graph-Kanten
  clusters.json        # Cluster & Label
  taxonomy/
    synonyms.yml
    entities.yml
  reports/
    semnet-YYYYMMDD.md
  meta.json            # Provenienz (Modell, Param, Hashes)


	•	Frontmatter (YAML) für jede Datei:

id: 2025-VAULT-####   # stabiler Schlüssel
title: ...
topics: [HausKI, Weltgewebe]
persons: [Verena]
places: [Hamburg]
projects: [wgx, hauski]
aliases: [HK, WG]
relations_lock: false



⸻

1. Indexing & Embeddings
	•	Crawler: iteriert Markdown & Canvas (ignoriert .gewebe/, .obsidian/).
	•	Chunking: 200–300 Tokens, Overlap 40–60, Paragraph/Block.
	•	Modelle: all-MiniLM-L6-v2 oder intfloat/e5-base (GPU-fähig via PyTorch/CUDA).
	•	Output: embeddings.parquet (id, path, chunk_id, text, embedding).

⸻

2. Schlagwort- & Entitätsextraktion
	•	Keyphrase: YAKE/RAKE lokal → refine via LLM optional.
	•	NER: spaCy de-model → Personen, Orte, Projekte.
	•	Taxonomie: .gewebe/taxonomy/synonyms.yml:

topics:
  hauski: [haus-ki, hk]
persons:
  verena: [v.]


	•	Normalisierung: bei Indexlauf Tokens mappen → Normform, ins Frontmatter schreiben.

⸻

3. Clusterbildung
	•	Verfahren: HDBSCAN (robust) + UMAP (2D-Projection).
	•	Ergebnis: clusters.json:

{ "id":7, "label":"Kommunikation/GFK", "members":["noteA","noteB"], "centroid":[...] }


	•	Orphan detection: Notizen ohne Cluster → eigene Liste.

⸻

4. Semantischer Wissensgraph
	•	Nodes (nodes.jsonl):

{"id":"md:gfk.md","type":"file","title":"GFK","topics":["gfk"],"cluster":7}
{"id":"topic:Gewaltfreie Kommunikation","type":"topic"}
{"id":"person:Verena","type":"person"}


	•	Edges (edges.jsonl):

{"s":"md:gfk.md","p":"about","o":"topic:Gewaltfreie Kommunikation","w":0.92,"why":["shared:keyphrase:GFK","same:cluster"]}
{"s":"md:verena.md","p":"similar","o":"md:tatjana.md","w":0.81,"why":["cluster:7","quote:'…'"]}



⸻

5. Verlinkung in Obsidian
	•	Related-Blöcke (idempotent, autogeneriert):

<!-- related:auto:start -->
## Related
- [[Tatjana]] — (0.81; Cluster 7, GFK)
- [[Lebenslagen]] — (0.78; Resonanz)
<!-- related:auto:end -->


	•	MOCs (_moc/topic.md):
	•	Beschreibung
	•	Dataview-Tabelle (alle Notizen mit topics:topic)
	•	Mini-Canvas-Link
	•	Canvas-Erweiterung:
	•	Knoten = Notizen/Topics/Persons
	•	Kanten = Similar/About/Mentions
	•	Legende-Knoten nach Canvas-Richtlinie.

⸻

6. Automatisierung
	•	wgx Recipes:

index:
    python3 tools/build_index.py
graph:
    python3 tools/build_graph.py
related:
    python3 tools/update_related.py
all: index graph related


	•	systemd –user Timer oder cron: nightly make all.
	•	Git Hook (pre-commit): delta-Index → Related aktualisieren.

⸻

7. Qualitative Validierung
[...]

(Die Blaupause ist gekürzt; siehe Original in deinem Vault.)

