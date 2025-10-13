# Pipeline-Skripte

Die Python-Skripte im Verzeichnis `scripts/` bilden den orchestrierten Pipeline-Flow von semantAH nach. Aktuell handelt es sich um ausführbare Stubs, die Struktur, Artefakte und Logging demonstrieren. Sie können als Ausgangspunkt für produktive Implementierungen dienen.

| Skript | Zweck | Output | Hinweise |
| --- | --- | --- | --- |
| `build_index.py` | Erstellt Embedding-Datei (`embeddings.parquet`). | `.gewebe/embeddings.parquet` | Legt bei Bedarf das Zielverzeichnis an und erzeugt eine CSV-ähnliche Platzhalterdatei. |
| `build_graph.py` | Übersetzt Embeddings in Graph-Knoten/-Kanten. | `.gewebe/nodes.jsonl`, `.gewebe/edges.jsonl` | Schreibt minimal valide JSONL-Zeilen, damit Folgeprozesse getestet werden können. |
| `update_related.py` | Fügt Markdown-Dateien einen Related-Block hinzu. | `notes_stub/example.md` | Verhindert doppelte Blöcke durch Marker `<!-- related:auto:start -->`. |
| `export_insights.py` | Exportiert Tageszusammenfassungen für Dashboards. | `$VAULT_ROOT/.gewebe/insights/today.json` | Erwartet die Umgebungsvariable `VAULT_ROOT`; erzeugt strukturierte JSON-Stubs ≤10 KB. |

## Ausführung
```bash
make venv           # virtuelle Umgebung anlegen
. .venv/bin/activate
python scripts/build_index.py
python scripts/build_graph.py
python scripts/update_related.py
```

Die Skripte nutzen aktuell keine externen Abhängigkeiten und lassen sich direkt mit Python ≥3.10 ausführen. Für produktiven Einsatz sollten die Stub-Ausgaben durch echte Pipeline-Schritte ersetzt und mit `semantah.yml` parametrisiert werden.
