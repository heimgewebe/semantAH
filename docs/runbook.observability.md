# Observability Runbook

Dieses Runbook beschreibt, wie du eine lokale Observability-Toolchain für semantAH einsetzt, um Fehler einzugrenzen und Laufzeiten zu überprüfen.

## Stack starten
1. Stelle sicher, dass Docker läuft.
2. Starte die Compose-Umgebung: `docker compose -f observability/docker-compose.yml up -d`.
   - Falls das Repository den Ordner `observability/` noch nicht enthält, kopiere die Vorlage aus `docs/blueprint.md` oder lege ihn nach eigenem Standard an.
3. Prüfe mit `docker compose -f observability/docker-compose.yml ps`, ob Grafana, Loki und Tempo im Status "healthy" sind.

## Endpunkte & Logins
- **Grafana:** [http://localhost:3000](http://localhost:3000), Standard-Login `admin` / `admin` (beim ersten Login Passwort ändern).
- **Loki:** [http://localhost:3100](http://localhost:3100), Pull-Endpunkt für Log-Queries.
- **Tempo:** [http://localhost:3200](http://localhost:3200), wird von Grafana zum Trace-Browsing genutzt.

## Typische Dashboards
- `SemantAH / Pipeline Overview`: Durchsatz, Laufzeiten der Python-Skripte, Fehlerquoten.
- `SemantAH / Indexd`: Request-Rate, Latenzen (`p50`, `p95`), Anzahl aktiver Sessions.
- `SemantAH / System`: CPU- und Speicherprofil der Container.

Falls Dashboards fehlen, importiere sie in Grafana über **Dashboards → Import** und verwende deine JSON-Dateien (siehe Blueprint oder eigene Exporte).

## Logs abfragen
1. Öffne in Grafana den **Explore**-Bereich und wähle die Datenquelle `Loki`.
2. Nutze beispielhafte Queries:
   - `{app="pipeline"} |= "error"`
   - `{service="indexd"} |= "WARN"`
3. Setze den Timepicker auf den Zeitraum des letzten Runs und speichere bei Bedarf die Query als Explorer-Ansicht.

## Traces untersuchen
1. Wähle in Grafana → Explore die Datenquelle `Tempo`.
2. Filtere nach `service.name="indexd"` oder `pipeline.stage="graph"`.
3. Öffne einzelne Traces und kontrolliere Spans mit hoher Dauer (>500 ms) auf Anomalien.

## Alarmierung (lokal)
- Lege Alert-Regeln als YAML/JSON unter `observability/rules/` ab und mounte sie in Prometheus bzw. Alertmanager.
- Verwende `docker compose logs alertmanager`, um Benachrichtigungen zu prüfen.
- Für Slack/Webhook-Integration: trage den Ziel-Webhook in der Alertmanager-Konfiguration ein und starte den Stack neu.

## Häufige Probleme
| Symptom | Diagnose | Behebung |
| --- | --- | --- |
| Keine Metriken sichtbar | Prometheus-Container gestoppt oder Scrape-Targets falsch | Compose-Stack neu starten, Prometheus-Logs prüfen |
| Loki-Queries leer | Log-Scraper nicht aktiv oder falscher Label-Selector | Prüfen, ob Promtail/Vector läuft und die Labels `app`/`service` setzt |
| Tempo-Trace fehlt | OpenTelemetry-Exporter deaktiviert | Instrumentierung prüfen (`telemetry.enabled` in `semantah.yml`, OTLP-Endpunkt erreichbar) |

## Shutdown
- `docker compose -f observability/docker-compose.yml down` stoppt alle Container.
- Lösche zum Reset die Volume-Verzeichnisse nach einem Backup (z. B. `rm -rf observability/data/*`).
