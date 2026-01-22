# semantAH Optimierungs-Leitfaden

Um *semantAH* zu einem wahrhaft „verständigen“ Wissens‑Organ zu machen, ist mehr nötig als nur einen Vektorindex aufzusetzen. Die Dokumentation und der Bauplan des Projekts zeigen, dass semantAH als Teil des Heimgewebe‑Organismus eine modulare Pipeline aus Python‑Skripten und einem Rust‑Dienst bildet, die Embeddings erzeugt, einen Index und Wissensgraphen aufbaut und anschließend verwandte Notizen automatisch in Markdown einbettet. Eine optimale Konfiguration entsteht, wenn Sie sowohl die zugrunde liegende Embedding‑Qualität als auch die darauf aufbauenden Ranking‑, Feedback‑ und Monitoring‑Mechanismen verbessern.

### 1. Bessere Embeddings und Chunking

* **Modellwahl und Provider:** semantAH nutzt derzeit standardmäßig das lokale Ollama‑Modell `nomic‑embed‑text`. Für höhere semantische Präzision sollten Sie in der `semantah.yml` einen leistungsfähigeren Provider wählen (z. B. `sentence‑transformers/all‑MiniLM‑L6‑v2` oder später via OpenAI) und das Modell regelmäßig aktualisieren. Wichtig ist, dass semantAH jede Modellrevision versioniert und mit Provenienzdaten speichert, damit Vergleiche über die Zeit möglich bleiben.
* **Chunk‑Größe und Überschneidung:** Laut Blaupause werden Notizen in Blöcke von 200–300 Tokens mit 40–60 Tokens Überlappung zerlegt. Diese Granularität stellt sicher, dass Embeddings genügend Kontext enthalten, ohne die Vektoren zu verwässern. Für Text‑Notizen können Sie alternativ eine Zielanzahl von 1200 Zeichen mit ca. 200 Zeichen Überlappung wählen.
* **Normalisierung:** Achten Sie darauf, dass Embeddings vor dem Persistieren L2‑normalisiert werden. Die aktuelle Pipeline ruft `sentence‑transformers` mit `normalize_embeddings=True` auf, damit der Index sofort die Kosinus‑Ähnlichkeit verwenden kann.

### 2. Ranking‑Regeln und Cutoffs verbessern

semantAH verwendet eine Score‑Formel aus Basisscore (Kosinus‑Ähnlichkeit) plus Boosts für verschiedene Signale. Im Bauplan sind folgende Heuristiken vorgesehen:

| Boost/Schwellwert                              | Zweck                                                                                                                 |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| **+0.05 Cluster‑Boost**                        | gleiche Cluster erhalten einen Bonus.                                                                                 |
| **+0.03 pro geteiltem Keyphrase** (max. +0.09) | fördert inhaltliche Überschneidungen.                                                                                 |
| **+0.04 Canvas-Hop ≤ 2**                       | kurze Verbindungswege in Obsidian‑Canvas steigern den Score.                                                          |
| **+0.02 Recency‑Bonus**                        | kürzlich geänderte Notizen werden bevorzugt.                                                                          |
| **Cutoffs**                                    | Score ≥ 0.82 + (≥ 2 Keyphrases oder kurzer Canvas‑Hop) → Auto‑Link; Score 0.70–0.81 → Vorschlag, darunter ignorieren. |

Die in `docs/roadmap.md` und der Blaupause beschriebenen nächsten Schritte empfehlen, Heuristiken modular als Config‑Werte zu definieren, sodass A/B‑Tests möglich bleiben. Implementieren Sie die Boosts (z. B. Zeit, Tags, Canvas, Cluster) in `tools/update_related.py` und legen Sie Grenzwerte in `.gewebe/config.yml` oder `semantah.yml` ab. Achten Sie darauf, dass der Score nur dann auto‑verlinkt, wenn mindestens zwei unabhängige Kriterien erfüllt sind (z. B. Keyphrases **und** Canvas‑Hop).

### 3. Synonyme, Entitäten und Taxonomie einsetzen

Um semantAH „verständiger“ zu machen, reicht die reine Vektorähnlichkeit nicht aus. Ergänzen Sie Ihre Notizen durch semantische Metadaten:

* **Frontmatter‑Felder:** Nutzen Sie in jeder Datei Frontmatter für `topics`, `persons`, `places` und `projects`, damit semantAH wichtige Konzepte erkennen kann.
* **Synonym‑ und Entitäten‑Dateien:** Halten Sie Synonyme in `.gewebe/taxonomy/synonyms.yml` fest (z. B. `hauski` ↦ `haus-ki`, `hk`) und führen Sie Entitäten in `entities.yml` auf. Die Pipeline mappt bei der Indizierung Tokens auf diese Normformen, sodass unterschiedliche Schreibweisen zusammengeführt werden.
* **NER und Keyphrase Extraction:** Laut Blaupause sollen lokale Keyphrase‑Algorithmen (YAKE/RAKE) und spaCy‑basierte Named‑Entity‑Erkennung eingesetzt werden. Durch diese Extraktion können relevante Kanten (`about`, `similar`) im Graphen begründet werden.

### 4. Feedback‑Loop implementieren

Das Dokument zum Feedback‑Loop stellt klar, dass semantAH nicht nur Daten liefert, sondern selbst gemessen werden soll: Coverage, Graph‑Dichte, Suchlatenzen und Fehlerquoten. Um semantAH zu optimieren:

1. **Signal sammeln:** Erfassen Sie Kennzahlen wie „Anteil der Dateien mit Embeddings“, „Verhältnis von Knoten zu Kanten“ oder „Anzahl verwaister Knoten“. Speichern Sie diese Metriken nach jedem Lauf als Snapshot.
2. **Policies ableiten:** Definieren Sie in einer Policy‑Datei (`policy/feedback-loop.v1.yml`) Schwellwerte für „OK“, „Warnung“ und „Kritisch“ und legen Sie Aktionen fest (z. B. Cutoffs anpassen, Safe Mode einschalten).
3. **Automatisches Tuning:** Lassen Sie Heimgewebe‑Komponenten (HausKI, Heimlern) diese Snapshots konsumieren und automatisch Cutoff‑Werte oder Boost‑Prioritäten anpassen.

Durch einen solchen Regelkreis kann semantAH lernen, z. B. bei schlechter Suche den Top‑k‑Wert zu verringern, bei zu wenigen Kanten den Graph‑Cutoff zu senken oder bei zu vielen „Spaghetti‑Kanten“ den Score‑Boost zu reduzieren.

### 5. Knowledge Observatory nutzen

Für eine objektive Bewertung gibt es das Knowledge Observatory. Es beobachtet Embeddings, zählt und meldet Status, ohne zu interpretieren. Es verfolgt z. B. für die fünf Namespaces (`chronik`, `osctx`, `docs`, `code`, `insights`) die Gesamtzahl der Embeddings und plant weitere Metriken wie neue Embeddings pro Namespace oder Modellrevision. Die Ergebnisse werden täglich als JSON‑Artefakt veröffentlicht. Nutzen Sie diese Daten, um:

* **Gaps zu identifizieren:** Das Observatory meldet Namespaces ohne Daten und erzeugt „gap“-Signale.
* **Drift zu erkennen:** Mit `model_revision` und `embedding_dim` erfasst das Observatory Modellwechsel und sichert die Reproduzierbarkeit.
* **Provenienz zu erzwingen:** Jeder Embedding‑Request verlangt einen `source_ref` und `producer`, invalides Namespace liefert HTTP 422. Embeddings ohne Provenienz sind wertlos.

### 6. Qualitätssicherung und Erweiterungen

* **Duplicate‑Detection & Topic‑Drift:** Verwenden Sie die in der Blaupause vorgeschlagene Near‑Duplicate‑Erkennung (Cosine ≥ 0.97) und Topic‑Drift‑Überwachung. Das hilft, redundante Notizen zusammenzuführen und thematische Veränderungen zu erkennen.
* **Explainable Related‑Blöcke:** Schreiben Sie `why`‑Felder mit Keyphrases, Cluster und Zitaten in die Kanten. In Obsidian können Sie per „Explain‑this‑link“ die Begründung abrufen, was das Vertrauen in semantAH erhöht.
* **Session‑Context & Manual Lock:** Implementieren Sie einen Recency‑Boost (+0.02 für aktuelle Dateien) und erlauben Sie per `relations_lock: true` in der Frontmatter, dass einzelne Notizen von Auto‑Edits ausgeschlossen werden.
* **Observability Stack:** Nutzen Sie das Runbook zur Observability, um Grafana, Loki und Tempo aufzusetzen. So können Sie Durchsatz, Latenzen und Fehlerquoten der Pipeline überwachen.

### Fazit

semantAH lässt sich nicht mit einem einzigen Parameter „schneller“ machen. Es wird „verständig“, wenn Sie:

1. **Hochwertige, normalisierte Embeddings** mit geeigneter Chunk‑Größe erzeugen,
2. **Raffinierte Ranking‑Regeln** (Cluster, Keyphrases, Canvas‑Hop, Recency) nutzen und in der Config justierbar machen,
3. **Semantische Metadaten** wie Synonyme, Entitäten und Taxonomien einbeziehen,
4. **Feedback‑Loops & Observability** einsetzen, um Coverage, Graph‑Dichte, Suchlatenzen und Drifts zu messen,
5. **Qualitätssichernde Features** wie Duplicate‑Erkennung, Topic‑Drift‑Wächter, Explain‑this‑link und Manual‑Lock implementieren.

Durch diese Maßnahmen baut semantAH eine robuste semantische Gedächtnisschicht auf, die kontextreiche, nachvollziehbare Beziehungen erstellt und sich selbst kontinuierlich verbessert.
