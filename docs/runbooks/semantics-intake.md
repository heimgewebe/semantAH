# Runbook: Semantics Intake

Dieser Leitfaden beschreibt, wie die im Vault erzeugten semantischen Artefakte manuell in nachgelagerte Systeme übernommen werden. Er richtet sich an Operatoren, die einen Export aus `.gewebe/` entgegennehmen und aufbereiten.

## Ausgangslage prüfen
1. **Letzten Pipeline-Lauf validieren**
   - Kontrolliere den Zeitstempel der Dateien unter `.gewebe/out/` (insb. `nodes.jsonl`, `edges.jsonl`, `reports.json`).
   - Öffne `.gewebe/logs/pipeline.log` und stelle sicher, dass der Lauf ohne Fehlermeldungen beendet wurde.
2. **Artefakt-Checksums erzeugen**
   - `sha256sum .gewebe/out/nodes.jsonl > checksums.txt`
   - `sha256sum .gewebe/out/edges.jsonl >> checksums.txt`
   - Die Prüfsummen werden später dem Intake-Protokoll beigefügt.

## Intake durchführen
1. **Export-Verzeichnis vorbereiten**
   - Leere ggf. den Staging-Ordner (z. B. `/var/tmp/semantah-intake`).
   - Kopiere alle Dateien aus `.gewebe/out/` sowie `checksums.txt` in den Staging-Ordner.
2. **Archiv erstellen**
   - `tar czf semantah-intake-$(date +%Y%m%d).tgz -C /var/tmp/semantah-intake .`
   - Prüfe die Archivgröße (sollte plausibel zu den Ursprungsdateien passen).
3. **Transfer**
   - Übertrage das Archiv gemäß Zielsystem (z. B. `scp`, Artefakt-Registry oder S3-Bucket).
   - Notiere Transfer-ID/URL im Intake-Protokoll.
4. **Import im Zielsystem**
   - Entpacke das Archiv in der vorgesehenen Import-Zone.
   - Führe das lokale Importskript oder die Pipeline des Zielsystems aus.
   - Dokumentiere Erfolg bzw. Fehlermeldungen.

## Validierung im Zielsystem
1. **Integritätsprüfung**
   - Vergleiche die übertragenen Checksums mit den lokal generierten.
   - Schlägt die Prüfung fehl, wiederhole den Transfer.
2. **Spot-Checks**
   - Öffne stichprobenartig einen Eintrag aus `nodes.jsonl` und `edges.jsonl`.
   - Stelle sicher, dass Pflichtfelder (`id`, `title`, `embedding_id`, `source_path`) vorhanden sind.
3. **Funktionaler Test**
   - Führe eine Suchanfrage mit bekannten Dokumenten durch und verifiziere, dass Ergebnisse zurückgegeben werden.

## Fehlerbehebung
| Symptom | Mögliche Ursache | Vorgehen |
| --- | --- | --- |
| Artefakte fehlen | Pipeline-Lauf fehlgeschlagen | `make all` erneut ausführen, Logs prüfen, Parameterwahl (`embedder.provider`, `index.top_k`) kontrollieren |
| Checksums stimmen nicht | Unvollständiger Transfer | Archiv neu erzeugen/übertragen, Netzwerk prüfen |
| Import-Skript bricht ab | Schema-Änderungen oder veraltete Contracts | Auf aktuelle `contracts/`-Schemen aktualisieren, Release-Notes prüfen |

## Rückmeldung & Dokumentation
- Erfasse Intake-Datum, Vault-Commit und Transferpfad im Betriebsprotokoll.
- Vermerke manuelle Eingriffe oder Sonderfälle, um Lessons Learned in die Automatisierung zu überführen.
