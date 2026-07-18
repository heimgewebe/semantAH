# `indexd`: Architektur und belegter Implementierungsstand

Dieses Dokument ist die kanonische Ist-Beschreibung des Rust-Dienstes `indexd`.
Historische Entwürfe und Roadmaps dürfen hiervon abweichen, müssen aber ausdrücklich als
Plan oder Konzept gekennzeichnet sein. Bei Widersprüchen gelten Code, Tests und
commitgebundene Benchmarkberichte vor beschreibendem Text.

## Kurzfassung

`indexd` ist derzeit ein einzelner Axum-Dienst mit einem pro Prozess gehaltenen
`VectorStore`. Er bietet Upsert, dokumentweises Löschen, exakte Vektorsuche und optional
serverseitige Texteinbettung. Es gibt **keinen HNSW-, Faiss- oder anderen ANN-Index**.

Die Suche normalisiert Vektoren und führt einen exakten linearen Scan innerhalb genau
eines Namespace aus. Da gespeicherte und angefragte Vektoren auf Einheitslänge
normalisiert werden, entspricht das verwendete Skalarprodukt der Cosinus-Ähnlichkeit.

## Laufzeitaufbau

- `AppState` hält `Arc<Tokio::RwLock<VectorStore>>` und optional einen `Embedder`.
- `VectorStore` erzwingt eine gemeinsame Vektordimensionalität über alle Namespaces.
- Jeder Namespace enthält eine zusammenhängende Liste `Arc<StoredItem>` für den linearen
  Scan und eine Key→Index-Abbildung für Ersetzen und Metadatenzugriff.
- Upsert und Delete laufen unter dem Write-Lock des Stores.
- Die HTTP-Suche hält den Read-Lock nur für die O(1)-Aufnahme eines
  `Arc<NamespaceItems>`-Snapshots und das Lesen der Dimension.
- Normalisierung, Ranking und Snippet-Erzeugung laufen danach außerhalb des gemeinsamen
  Store-Locks in `spawn_blocking`.

Ein in-flight Request sieht dadurch eine konsistente Namespace-Version. Überlappt ein
Writer mit einem gehaltenen Snapshot, kopiert `Arc::make_mut` die Namespace-Liste und den
Key-Index flach. Unveränderte Keys, Embeddings und Metadaten bleiben referenzgeteilt.

## Suchvertrag

1. `k` muss größer als null sein.
2. Das Query-Embedding wird in dieser Reihenfolge ermittelt:
   `query.meta.embedding`, Top-Level `embedding`, Legacy-Top-Level `meta.embedding`,
   optional konfigurierter Server-Embedder.
3. Leere oder dimensionsfalsche Vektoren werden abgewiesen.
4. Der Query-Vektor wird normalisiert.
5. Alle Einträge des gewählten Namespace werden exakt gescannt.
6. Ein begrenzter Heap hält die besten `k` Treffer; Score-Gleichstände werden
   deterministisch nach Dokument- und Chunk-ID aufgelöst.
7. `snippet` stammt aus `meta.snippet`; `rationale` ist derzeit leer.

Das Feld `filters` ist Teil des akzeptierten Requestschemas, wird aber im aktuellen
Store noch **nicht ausgewertet**. Clients dürfen daraus keine Filtergarantie ableiten.

Komplexität der exakten Suche: O(n × d) für `n` Namespace-Einträge und `d`
Vektordimensionen, zuzüglich O(log k) pro Heap-Aktualisierung. Snapshotaufnahme selbst
ist O(1).

## Persistenzvertrag

Wenn `INDEXD_DB_PATH` gesetzt ist:

- beim Start wird die JSONL-Datei in einem Blocking-Task vollständig gelesen;
- Zeilen mit abweichender Dimension werden protokolliert und übersprungen;
- gültige Einträge werden über den normalen Upsert-Pfad normalisiert und aufgebaut;
- beim geordneten Shutdown wird der gesamte Store in eine temporäre Datei geschrieben
  und per Rename atomar ersetzt.

Jede Zeile enthält `namespace`, `doc_id`, `chunk_id`, `embedding` und `meta`.

Diese Persistenz ist ein Start-/Shutdown-Snapshot. Sie ist **kein** Write-Ahead-Log,
keine kontinuierliche Durability-Garantie, kein Multi-Prozess-Store und keine
transaktionale Datenbank. Sled, SQLite und binäre ANN-Snapshots sind nicht implementiert.

## Belegte Leistungsgrenze

Der Benchmark `indexd_real_workload` ruft den produktiven Axum-Handler in-process auf.
Der kontrollierte A/B-Bericht für PR #261 ist an den geprüften Head
`2b42a5339bd90cb8ffe1519967fd51113be70a1a` gebunden und hat SHA-256
`041ddef812a34db595f7a129665ffd83029a0c50eb5d620f0e75d9bc2e75f1e9`.

Im Standardprofil lagen die sequenziellen p95-Werte bei:

| Namespacegröße × Dimension | p95 | parallele Suche p95 | Writer-Lock-Wartezeit p95 |
| --- | ---: | ---: | ---: |
| 5.000 × 384 | 0,616 ms | 0,778 ms | 0,000110 ms |
| 10.000 × 768 | 2,987 ms | 2,901 ms | 0,000050 ms |
| 10.000 × 1.536 | 4,842 ms | 7,157 ms | 0,000050 ms |

Dies sind synthetische, hostgebundene In-process-Daten. Sie belegen weder
Produktionskapazität noch Netzwerk-, Reverse-Proxy- oder Multi-Instanz-Latenz.
Weitere Details und Reproduktionsregeln stehen in
[`indexd-performance.md`](indexd-performance.md).

## Statusmatrix

| Fähigkeit | Status |
| --- | --- |
| Axum-API für Upsert, Delete, Search und Embed Text | implementiert |
| exakte Cosinus-Suche innerhalb eines Namespace | implementiert |
| deterministische Score-Tie-Breaks | implementiert |
| O(1)-Namespace-Snapshot vor Ranking | implementiert |
| JSONL-Laden beim Start und atomisches Speichern beim Shutdown | implementiert |
| serverseitiges Query-Embedding | optional implementiert |
| Metadatenfilter in der Suche | nicht implementiert; Feld wird ignoriert |
| HNSW/Faiss/anderer ANN-Index | nicht implementiert |
| Sled/SQLite als Metadaten- oder Vektorstore | nicht implementiert |
| Write-Ahead-Log oder kontinuierliche Persistenz | nicht implementiert |
| Authentifizierung, Rate-Limiting, Multi-Instanz-Koordination | nicht implementiert |

## ANN-Entscheidungsgrenze

ANN ist eine spätere, messpflichtige Entscheidung und keine bereits gewählte
Architektur. Eine Einführung benötigt mindestens:

- einen repräsentativen Korpus und exakte Suche als Ground Truth;
- festgelegte Recall@k- und Latenzbudgets;
- Speicher-, Build-, Update-, Delete- und Wiederanlaufmessungen;
- einen persistenzgebundenen Format- und Migrationsvertrag;
- deterministischen Fallback auf exakte Suche unterhalb einer belegten Schwelle;
- Negativtests für beschädigte Indizes und dimensions-/modellfremde Daten.

Bis diese Verträge erfüllt und eine Aktivierungsschwelle belegt sind, bleibt exakte
Suche der kanonische Pfad.

## Nichtaussagen

Dieses Dokument belegt keine Produktionsreife, keine ANN-Notwendigkeit, keine
Filtersemantik, keine Crash-Durability zwischen Upserts und Shutdown, keine
Lock-Freiheit und keine über den getesteten Einzelprozess hinausgehende Konsistenz.
