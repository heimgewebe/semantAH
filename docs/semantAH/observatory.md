# Knowledge Observatory

## Überblick

Das Knowledge Observatory ist semantAHs nüchternes Beobachtungsinstrument für die semantische Infrastruktur. Es **beobachtet**, **zählt** und **meldet** — aber **interpretiert nicht**.

## Philosophie

> Ein Observatorium, das erklärt, warum etwas wichtig ist, ist kein Observatorium, sondern ein Kommentarspaltentäter. semantAH soll schauen, nicht schwadronieren.

Das Observatory folgt dem Prinzip der **kontraktgetriebenen Minimalität**:
- **Zählungen**: Quantitative Fakten (neue Embeddings pro Namespace)
- **Drift-Indikatoren**: Objektive Änderungen (neue Modellrevision)
- **Leerräume**: Fehlende Signale (Namespaces ohne Daten)
- **Keine Interpretation**: Kein "gut/schlecht", nur Zustand

## Produkte

### 1. Knowledge Observatory Artefakt

**Datei**: `artifacts/knowledge.observatory.json`  
**Schema**: `contracts/knowledge.observatory.schema.json`  
**Frequenz**: Täglich (06:15 UTC via Cron)  
**Publisher**: GitHub Workflow `publish-knowledge-observatory.yml`

### Struktur

```json
{
  "observatory_id": "obs-uuid-...",
  "generated_at": "2026-01-03T06:15:00Z",
  "source": {
    "component": "semantAH",
    "version": "commit-sha"
  },
  "topics": [
    {
      "topic": "Semantic Infrastructure",
      "confidence": 0.85,
      "sources": [
        {"type": "repo_file", "ref": "crates/indexd/", "weight": 0.7}
      ],
      "suggested_questions": [
        "Are all namespaces receiving embeddings?",
        "Has the model revision changed?"
      ]
    }
  ],
  "signals": [
    {
      "type": "gap",
      "description": "Embedding namespaces with no data: code, insights"
    }
  ],
  "blind_spots": [
    "No embedding data available for analysis."
  ],
  "considered_but_rejected": []
}
```

## Embedding Tracking

Das Observatory verfolgt Embeddings über fünf kanonische Namespaces:

| Namespace | Quelle | Zweck |
|-----------|--------|-------|
| `chronik` | Event-Log | Aktivitätsverlauf |
| `osctx` | OS-Kontext | Systemzustand |
| `docs` | Dokumentation | Wissensbasis |
| `code` | Repository | Code-Semantik |
| `insights` | Analysen | Aggregierte Erkenntnisse |

### Metriken

Das Observatory zählt **pro Namespace**:
- Anzahl neuer Embeddings (seit letztem Snapshot)
- Aktive Modellrevision
- Fehlende Namespaces (Leerräume)

**Wichtig**: Das Observatory wertet **nicht**, ob diese Zahlen "gut" oder "schlecht" sind. Downstream-Systeme (hausKI, heimgeist, leitstand) ziehen ihre eigenen Schlüsse.

## Konsumenten

### hausKI (Index)
- Verwendet Observatory zur Index-Koordination
- Prüft auf Modell-Drift vor Re-Indexing
- Identifiziert Namespaces mit fehlenden Embeddings

### heimgeist (Reflexion)
- Nutzt Observatory für Meta-Analysen
- Erkennt Muster in Signal-Historie
- Generiert Fragen aus `suggested_questions`

### leitstand (UI)
- Zeigt Observatory-Daten in Dashboard
- Visualisiert Namespace-Coverage
- Alarmiert bei unerwarteten Gaps

## API: Embedding Service

Das Observatory beobachtet Embeddings, die über den `/embed/text` Endpoint erzeugt werden.

### Endpoint

```http
POST /embed/text
Content-Type: application/json

{
  "text": "Text to embed",
  "namespace": "osctx",
  "source_ref": "event-abc-123"
}
```

### Response (Schema-konform)

```json
{
  "embedding_id": "embed-uuid-...",
  "text": "Text to embed",
  "embedding": [0.123, -0.456, ...],
  "embedding_model": "nomic-embed-text",
  "embedding_dim": 768,
  "model_revision": "nomic-embed-text-768",
  "generated_at": "2026-01-03T21:00:00Z",
  "namespace": "osctx",
  "source_ref": "event-abc-123",
  "producer": "semantAH",
  "determinism_tolerance": 1e-6
}
```

### Versionierung

**Kritisch**: Modellwechsel = neue Revision, **niemals stillschweigend**.

Die `model_revision` identifiziert deterministisch:
- Modellname (z.B. `nomic-embed-text`)
- Dimensionalität (z.B. `768`)
- Optional: Modell-Hash oder Version

Ohne strikte Versionierung ist **Vergleich über Zeit unmöglich** (epistemischer Drift).

### Determinismus

**Garantie**: Gleicher Input + gleiche Modellrevision → identischer Vektor (bis auf float-Toleranz).

**Toleranz**: ε = 1e-6 (dokumentiert in Schema)

**Test**: CI prüft, dass derselbe Text zweimal eingebettet eine Cosine-Similarity ≥ 0.9999 ergibt.

## Namespaces & Provenienz

### Namespace-Validierung

Alle fünf Namespaces sind **hard-coded** und werden validiert:
- `chronik` | `osctx` | `docs` | `code` | `insights`

Ungültige Namespaces werden mit HTTP 400 abgelehnt.

### Provenienz-Pflicht

**Keine anonymen Vektoren.**

Jedes Embedding **muss** enthalten:
- `source_ref`: Event-ID, Pfad, Hash oder andere eindeutige Referenz
- `producer`: Immer `"semantAH"`
- `namespace`: Einer der fünf kanonischen Namespaces

Embeddings ohne Provenienz sind **epistemisch wertlos**.

## Betrieb

### Manuelle Generation

```bash
uv run scripts/observatory_mvp.py
```

Erzeugt: `artifacts/knowledge.observatory.json`

### CI/CD (Täglich)

Workflow: `.github/workflows/publish-knowledge-observatory.yml`
- Trigger: Cron (06:15 UTC täglich)
- Schritte:
  1. Generiere Observatory
  2. Validiere gegen Schema (AJV)
  3. Publiziere als GitHub Release Asset
  4. Notifiziere Plexer (optional)

### Download (Konsumenten)

```bash
curl -L https://github.com/heimgewebe/semantAH/releases/download/knowledge-observatory/knowledge.observatory.json
```

## Fehlervermeidung

### Verboten
- **Stiller Modellwechsel**: Revision **muss** geändert werden
- **Überfrachtetes Observatory**: Kennzahlen ja, Deutung nein
- **Unklare Herkunft**: Ohne `source_ref` kein Embedding
- **Zu hohe Frequenz**: Täglich reicht; Echtzeit ist Rauschen

### Erlaubt
- Zählungen
- Drift-Indikatoren
- Leerräume
- Objektive Metadaten

## Scope & Grenzen

### Was das Observatory IST
- Nüchterner Beobachter
- Quantitativer Datensammler
- Provenienz-Tracker
- Drift-Detektor

### Was das Observatory NICHT IST
- Interpretations-Engine
- Entscheidungssystem
- Qualitäts-Richter
- Echtzeit-Monitor

## Weiterführende Dokumentation

- Contract: `contracts/knowledge.observatory.schema.json`
- Embedding Schema: `contracts/os.context.text.embed.schema.json`
- API Reference: `docs/indexd-api.md`
- Namespaces: `docs/namespaces.md`

## Beispiel-Workflow

1. **Embedding erzeugen**:
   ```bash
   curl -X POST http://localhost:8080/embed/text \
     -H "Content-Type: application/json" \
     -d '{"text":"Example","namespace":"osctx","source_ref":"ref-1"}'
   ```

2. **Observatory generieren**:
   ```bash
   uv run scripts/observatory_mvp.py
   ```

3. **Konsumieren** (hausKI):
   ```python
   import requests
   # Replace {owner}/{repo} with actual values
   obs_url = "https://github.com/heimgewebe/semantAH/releases/download/knowledge-observatory/knowledge.observatory.json"
   obs = requests.get(obs_url).json()
   for topic in obs["topics"]:
       if topic["topic"] == "Semantic Infrastructure":
           print(topic["suggested_questions"])
   ```

## Ungewissheit

Das Observatory selbst hat **keine Meinung** zu seiner Ungewissheit. Es meldet Fakten. Downstream-Systeme entscheiden, wie sie mit Lücken, Drift oder Stille umgehen.

---

**Letzte Aktualisierung**: 2026-01-03  
**Maintainer**: semantAH Team  
**Status**: MVP → Production-Ready
