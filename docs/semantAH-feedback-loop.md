# semantAH Feedback-Loop

Dieses Dokument beschreibt, wie semantAH als semantisches Observatorium
Signale an den Heimgewebe-Organismus zurückgeben soll – und wie daraus
Policies für Selbstverbesserung entstehen können.

Ziel: aus einer reinen Index-/Graph-Engine wird ein aktives Feedback-Organ
im Organismus.

## 1. Grundidee

semantAH sitzt zwischen Rohmaterial (Vaults, Events) und Entscheidungsinstanzen
wie HausKI, Heimlern, Leitstand.

In Kurzform:

- Eingänge: Texte, Events, Intents
- Verarbeitung: Embeddings, Index, Graph, Insights
- Ausgänge: Suchergebnisse, „Related“-Blöcke, Export-Artefakte

Der Feedback-Loop ergänzt:

- semantAH erzeugt Signals & Metrics (z. B. Coverage, Fehler, Drift).
- Diese werden als Events/Metriken in Heimgewebe gespiegelt.
- Heimgewebe (z. B. Heimlern, heimgeist, HausKI) passt daraufhin
  Policies und Konfiguration an.
- Neue Läufe von semantAH verwenden diese geänderten Policies.

semantAH wird damit nicht nur Datensenke, sondern auch Sensor und Kritiker.

## 2. Loop-Topologie (Zielbild)

Zielbild des Regelkreises:

```text
Rohdaten (Vault, Events, Intents)
   │
   ▼
semantAH-Pipeline
(Embeddings, Index, Graph)
   │
   ├─► Insights / Artefakte (nodes.jsonl, edges.jsonl, Reports)
   │
   ├─► Metrics (Laufzeiten, Fehlerquoten, Coverage)
   │
   ▼
Feedback-Export
(Events, Snapshots, Reports)
   │
   ▼
Heimgewebe (HausKI, Heimlern, Leitstand)
   │
   ├─ Policy-Updates (Cutoffs, Boosts, Safe Mode)
   ├─ neue Intents / Jobs
   ▼
neue semantAH-Läufe mit angepassten Policies
```

Wichtig: Dieses Dokument definiert das Zielbild.
Die konkrete technische Umsetzung (Event-Namen, exakte Metriken) wird
schrittweise an Contracts und chronik angepasst.

## 3. Quellen im Code / Repo

Relevante Stellen im Repo (Stand dieses Dokuments):

- scripts/export_insights.py: Exportiert Insights/Graph-Artefakte
  als Grundlage für Feedback-Snapshots.
- scripts/wgx-metrics-snapshot.sh: erzeugt Metrik-Snapshots für WGX/Fleet.
- .github/workflows/metrics.yml: CI-Einstiegspunkt für Metrik-Läufe.
- docs/runbook.observability.md: beschreibt Observability-Stack
  (Grafana, Loki, Tempo) zur Laufzeitbeobachtung.
- docs/hauski.md, docs/x-repo/weltgewebe.md: Einbettung von semantAH
  in HausKI und den Organismus.

Dieses Dokument positioniert diese Bausteine in einem konsistenten Loop.

## 4. Welche Signale semantAH liefern soll

Als Zielbild für eine erste Policy-Version (siehe policy/feedback-loop.v1.yml)
bietet sich an:

1. Coverage-Signale
    - Anteil der Dateien im Vault, die Embeddings besitzen.
    - Anteil der Dateien mit mindestens einem Graph-Knoten.
2. Graph-Qualität
    - Verhältnis Knoten/Kanten (zu wenig Kanten → isolierte Inseln,
      zu viele Kanten → unlesbare „Spaghetti-“Graphen).
    - Anzahl „verwaister“ Knoten (ohne eingehende/ausgehende Kanten).
3. Search-Qualität (Proxy)
    - Top-k-Latenzen (p50, p95), Fehlerraten.
    - Zahl der Suchanfragen mit leerem Ergebnis.
4. Pipeline-Stabilität
    - Wiederkehrende Fehler in Python-Skripten (z. B. Parsing-Fehler),
      sichtbar über Observability.

Diese Signale müssen nicht alle von Anfang an vorhanden sein.
Das Ziel dieses Dokuments ist, sie explizit zu machen und damit
eine Struktur zu schaffen, in die konkrete Implementierungen hineinwachsen.

## 5. Richtungen des Feedbacks

### 5.1 semantAH → Heimgewebe

semantAH soll in regelmäßigen Abständen (z. B. nach einem WGX-Job
oder nach einem kompletten Vault-Lauf) einen Snapshot liefern, der u. a. enthält:

- coverage: z. B. „80 % der Markdown-Dateien haben Embeddings“.
- graph_density: Knoten/Kanten-Verhältnis, Zahl verwaister Knoten.
- search_health: Latenzen, Fehlerquote.
- warnings: z. B. „Namespace X wächst stark, aber ohne Kanten zu Y“.

Diese Snapshots können:

- im Leitstand visualisiert werden,
- in chronik als Events landen,
- von Heimlern als Trainingssignal verwendet werden.

### 5.2 Heimgewebe → semantAH

Auf Basis dieser Snapshots können andere Organe (z. B. Heimlern, heimgeist,
HausKI) Policies zurückspielen:

- Anpassung von Cutoffs und Boosts
- Aktivierung eines „Safe Mode“ bei Fehlerclustern
- Änderung der Prioritäten für bestimmte Namespaces oder Pfade
- Anstoßen zusätzlicher Läufe (z. B. nur für bestimmte Ordner)

Diese Richtungsänderungen landen entweder:

- direkt in der semantah.yml (konfigurierbare Policies),
- oder in eigenen Policy-Dateien unter policy/.

## 6. Policy-Datei: feedback-loop.v1.yml

Die Datei policy/feedback-loop.v1.yml definiert eine erste,
menschenlesbare Sicht auf diesen Loop:

- Welche Signale erwartet semantAH?
- Ab welchen Schwellwerten gelten Zustände als „ok“, „warnend“ oder „kritisch“?
- Welche Aktionen dürfen automatisch vorgeschlagen werden,
  welche nur als Hinweis in Reports auftauchen?

Die Policy-Datei ist bewusst technologie-agnostisch formuliert, damit:

- HausKI/Heimlern sie interpretieren und überschreiben kann,
- WGX-Rezepte sie verwenden können, ohne an konkrete Implementierungen
  im Code gebunden zu sein.

## 7. Fahrplan

Kurzfristig:

- Dokument hier als Referenz etablieren.
- Policy-Datei policy/feedback-loop.v1.yml hinzufügen.
- WGX- und CI-Runbooks an dieses Zielbild referenzieren.

Mittelfristig:

- konkrete Metriken in scripts/export_insights.py und
  scripts/wgx-metrics-snapshot.sh ergänzen,
  die mit der Policy-Datei korrespondieren.
- Events/Contracts im contracts-Repo und in chronik nachziehen
  (z. B. contracts/semantah.feedback.snapshot.schema.json),
  sodass der hier beschriebene Loop vollständig contract-first angebunden ist.

Langfristig:

- Heimlern-Policies definieren, die aus Feedback-Events lernen,
- Leitstand-Ansichten bauen, die den semantAH-Loop transparent machen.

Oder in einem Satz:

semantAH soll nicht nur sagen, was im Vault steht,
sondern auch, wie gut es selbst dabei ist – und was es sich
für seine nächste Evolutionsstufe wünscht.
