# Namespaces

Namespaces trennen semantische Datenräume voneinander. Jeder Namespace besitzt eigene
Embeddings, Indexeinträge und Graph-Kanten, sodass z. B. private Notizen (`vault`) nicht mit
öffentlich gecrawlten Quellen (`web`) vermischt werden (siehe `README.md`, Abschnitt
„Architekturüberblick“ sowie `docs/indexd-api.md`, Abschnitt „Namespaces“).

## Standardaufteilung

| Namespace      | Zweck                                           | Persistenzpfad                          |
|----------------|--------------------------------------------------|-----------------------------------------|
| `vault`        | Obsidian-Vault bzw. lokale Primärquelle.         | `.gewebe/vault/…` (Embedding + Index). |
| `web` (geplant)| Externe Webseiten-Snapshots.                     | `.gewebe/web/…`.                       |
| `notes:private`| Feinere Unterteilung sensibler Notizen (optional).| `.gewebe/notes/private/…`.             |

- Ohne explizite Angabe landet alles im Namespace `vault`. Das ist auch der Default der
  REST-APIs (`search`, `upsert`, `delete`); Details finden sich in
  `docs/indexd-api.md`, Abschnitt „Namespace-Parameter“.
- Zusätzliche Namespaces können jederzeit ergänzt werden; Index und Embeddings arbeiten
  transparent mit dem angegebenen String.

## Konfiguration

```yaml
# semantah.yml
out_dir: .gewebe
namespaces:
  default: vault
  web:
    enabled: false    # Beispiel: Namespace vorbereiten, aber noch nicht befüllen
```

- `out_dir` definiert das Wurzelverzeichnis für alle Namespaces (Default: `.gewebe`),
  konfigurierbar in `semantah.yml` unter „Allgemeine Einstellungen“.
- Der Default-Namespace wird aus `namespaces.default` gelesen; falls der Block fehlt, wird
  `vault` angenommen.
- Weitere Namespaces können (z. B. durch Automatisierungen) in derselben Struktur
  angelegt werden. Die HausKI-Integration spiegelt das, indem sie unter
  `~/.local/state/hauski/index/<namespace>/` getrennte Stores anlegt (siehe
  `docs/hauski.md`, Abschnitt „Index-Struktur“).
- Die optionalen Flags (z. B. `namespaces.web.enabled`) dienen aktuell der Dokumentation
  und haben noch keine direkte Auswertung im Code.

## Verwendung im Betrieb

1. Adapter schreiben Embeddings und Indexdaten immer zusammen mit dem gewünschten Namespace.
2. Dienste wie `indexd` prüfen den Namespace und isolieren Operationen darauf (z. B. `delete`
   entfernt nur Dokumente innerhalb des angegebenen Namespace).【F:crates/indexd/src/store.rs†L25-L155】
3. Queries (`search`) müssen den Namespace übergeben, um im richtigen Datenraum zu suchen.

Mit dieser Trennung lassen sich mehrere Wissensquellen parallel betreiben, ohne dass
Synchronisations- oder Berechtigungsgrenzen verletzt werden.
