# Pipeline-Skripte

Das Skript `ingest_leitstand.py` verarbeitet eine `aussen.jsonl`-Datei aus dem Leitstand-Export und erzeugt eine formatierte `today.json`-Datei im `.gewebe/insights`-Verzeichnis.

| Skript | Zweck | Output |
| --- | --- | --- |
| `ingest_leitstand.py` | Verarbeitet Leitstand-Daten zu Insights. | `.gewebe/insights/today.json` |

## Ausführung

Das Skript wird typischerweise über das `Makefile` ausgeführt:

```bash
make ingest-leitstand
```

Alternativ kann es direkt mit `uv run` aufgerufen werden:

```bash
uv run scripts/ingest_leitstand.py leitstand/data/aussen.jsonl
```
