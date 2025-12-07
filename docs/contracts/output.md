# semantAH – Output Contracts

Dieses Dokument beschreibt die garantierte Form aller **extern konsumierbaren**
Ausgaben von semantAH in menschenlesbarer Form.

- Die **maschinelle Quelle der Wahrheit** ist das JSON-Schema unter
  `contracts/insights.schema.json`.
- Dieses Dokument ergänzt dieses Schema um Regeln zu Häufigkeit, Kardinalität,
  Fehlerverhalten und Verantwortlichkeiten.

**Hinweis zu Schemas**: In älteren Versionen wurde in der Implementierung
`insights.daily.schema.json` erwähnt. Diese Datei existiert nicht mehr;
`insights.schema.json` ist das maßgebliche Schema für Daily-Insights.

Primäre Konsumenten:
- leitstand (UI / Visualisierung)

Optionale/sekundäre Konsumenten:
- hausKI (KI-gestützte Auswertung)
- chronik (Persistenz von Tageszuständen / Audits)

---

## 1. Daily Insights

semantAH erzeugt täglich:

    VAULT_ROOT/.gewebe/insights/daily/YYYY-MM-DD.json
    VAULT_ROOT/.gewebe/insights/today.json

Format:
  → `contracts/insights.schema.json`

### 1.1 Garantierte Felder (semantische Ebene)

- `ts`
  - Typ: String
  - Format: `YYYY-MM-DD` (ISO-Datum, lokale Zeitsicht des Vaults)

- `topics`
  - Typ: JSON-Array
  - Sortierung: absteigend nach Relevanz
  - Kardinalität: **maximal 16 Einträge**
  - Die konkrete Struktur der Einträge (z. B. Felder, Typen) ergibt sich aus
    dem Schema `contracts/insights.schema.json`.

- `questions`
  - Typ: JSON-Array
  - Darf leer sein (`[]`)
  - Struktur der Einträge: gemäß `contracts/insights.schema.json`

- `deltas`
  - Typ: JSON-Array
  - Darf leer sein (`[]`)
  - Struktur der Einträge: gemäß `contracts/insights.schema.json`

Optionale Felder:
- `source`
  - empfohlener Wert: `"semantAH.daily"`

- `metadata.index_version`
  - beschreibt die interne Version des semantischen Index, der zur Erzeugung
    der Daily-Insights verwendet wurde

- `metadata.embedding_model`
  - Freitext oder Identifier des verwendeten Embedding-Modells

### 1.2 Contract-Versionierung

semantAH kann (und sollte perspektivisch) eine explizite Contract-Version
mitliefern:

- `metadata.contract_version: "1.x"`

Regeln:
- Fehlt `metadata.contract_version`, **müssen** Konsumenten das Dokument als
  kompatibel zu Version `1.x` interpretieren (Backward-Kompatibilität).
- Neue Major-Versionen (z. B. `"2.0"`) dürfen nur eingeführt werden, wenn
  das zugrunde liegende Schema (`insights`) ebenfalls ein Major-Update
  erfährt und Konsumenten explizit darauf vorbereitet wurden.
- Konsumenten sollten `metadata.contract_version` nicht hart parsen, sondern
  nur grob Major/Minor interpretieren (z. B. `"1.x"` → Major 1).

Hinweis: Die exakte Form und Pflicht/Optionalität von `metadata.contract_version`
ist Sache des JSON-Schemas. Dieses Dokument beschreibt das empfohlene
Versionierungsmodell.

---

## 2. Semantic Index

Der Index unter `.gewebe/index/*` ist **rebuildbar**.

Garantiert:
  - Dateien sind deterministisch aus dem Vault rekonstruierbar
  - Keine Persistenzgarantie über Geräte hinweg

Nicht garantiert (kein Teil der öffentlichen API):
  - Formatstabilität der einzelnen Indexdateien über Releases
  - Verzeichnisstruktur unterhalb von `.gewebe/index/`

Der Index ist damit **primär ein interner Cache** von semantAH:

- leitstand, hausKI und chronik **dürfen sich nicht** auf bestimmte Dateien
  oder Strukturen unter `.gewebe/index/*` verlassen.
- Zulässige Annahme für Konsumenten:
  - Index kann jederzeit regeneriert werden (z. B. durch semantAH-CLI).
  - Löschen des Index führt nur zu längerem ersten Lauf, nicht zum
    Datenverlust im Vault selbst.

Der einzige dauerhaft stabile Vertrag für Konsumenten sind die Dateien unter
`.gewebe/insights/*` (siehe Abschnitt 1).

---

## 3. Fehlerregeln

- Falls der Vault leer ist:
  - semantAH erzeugt trotzdem eine gültige `insights.daily`-Datei.
  - `topics` enthält mindestens einen Eintrag, z. B. `"vault"` oder eine
    ähnliche Default-Kategorie (konkreter Wortlaut: gemäß Schema).
  - (Schema-seitig ist eine leere Liste erlaubt, semantAH verpflichtet sich
    aber, mindestens einen Default-Eintrag zu erzeugen.)
- Falls Markdown-Dateien fehlerhaft sind:
  - Datei wird ignoriert (Fehler in Einzeldateien führen nicht zum Abbruch
    des gesamten Laufs).
- Falls ein Daily Insight **gar nicht** erzeugt werden kann:
  - semantAH gibt einen Exit-Code ≠ 0 zurück.
  - Konsumenten (z. B. leitstand) dürfen in diesem Fall auf die letzte
    gültige Daily-Datei zurückfallen oder einen Fehlerzustand anzeigen.

---

## 4. Beziehung zu leitstand

leitstand konsumiert ausschließlich:
  - `insights.daily`

semantAH stellt sicher, dass diese Dateien:
  - exakt dem Schema entsprechen,
  - täglich erneuert werden,
  - nie „teilbeschrieben" auftreten (Write-Operationen sind atomar:
    erst nach vollständigem Schreiben ist die Datei für Konsumenten sichtbar,
    z. B. durch Schreiben in eine temporäre Datei und anschließendes Umbenennen).

## 5. Beziehung zu hausKI und chronik

- hausKI **kann** `insights.daily` als zusätzlichen Kontext oder als
  Trainings-/Evaluationssignal verwenden, sollte aber robust gegenüber
  fehlenden Dateien und neuen Feldern bleiben (Schema-Versionierung beachten).

- chronik **kann** Snapshots von `insights.daily` persistieren, um
  zeitliche Verläufe und historische Zustände nachzuvollziehen.
  Auch hier gilt: Consumer sollen sich am Schema und an `contract_version`
  orientieren, nicht an internen Indexformaten.

---

Dies ist der verlässliche Output-Vertrag von semantAH für externe Konsumenten.
