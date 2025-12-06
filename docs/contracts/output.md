# semantAH – Output Contracts

Dieses Dokument definiert die garantierte Form aller Ausgaben von semantAH.
Es dient Leitstand, hausKI und chronik zur Orientierung.

---

## 1. Daily Insights

semantAH erzeugt täglich:

    VAULT_ROOT/.gewebe/insights/daily/YYYY-MM-DD.json
    VAULT_ROOT/.gewebe/insights/today.json

Format:
  → `contracts/insights.daily.schema.json`

Garantierte Felder:
  - `ts` (YYYY-MM-DD)
  - `topics` – sortiert nach Relevanz, max. 16 Einträge
  - `questions` – leere Liste erlaubt
  - `deltas` – leere Liste erlaubt

Optionale Felder:
  - `source: "semantAH.daily"`
  - `metadata.index_version`
  - `metadata.embedding_model`

---

## 2. Semantic Index

Der Index unter `.gewebe/index/*` ist **rebuildbar**.

Garantiert:
  - Dateien sind deterministisch aus dem Vault rekonstruierbar
  - Keine Persistenzgarantie über Geräte hinweg

Nicht garantiert:
  - Formatstabilität über Releases

---

## 3. Fehlerregeln

- Falls der Vault leer ist → Topics = [["vault", 1.0]]
- Falls Markdown-Dateien fehlerhaft sind → Datei wird ignoriert
- Falls Insight nicht erzeugt werden kann → semantAH gibt Exit-Code ≠ 0 zurück

---

## 4. Beziehung zu leitstand

leitstand konsumiert ausschließlich:
  - `insights.daily`

semantAH stellt sicher, dass diese Dateien:
  - exakt dem Schema entsprechen,
  - täglich erneuert werden,
  - nie „teilbeschrieben“ auftreten.

---

Dies ist der verlässliche Output-Vertrag von semantAH.
