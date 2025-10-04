# Beitragende Leitfäden für das semantAH-Repo

Dieses Dokument fasst die empfohlenen "Lern-Anweisungen" zusammen, die aus der Beobachtung anderer WGX-fähiger Repositories gewonnen wurden. Ziel ist es, semantAH als vollwertigen Knoten des Weltgewebe-Ökosystems zu etablieren.

## 1. Synchronisierung & Meta-Struktur
- **Template-Sync aktivieren:** semantAH in `metarepo/scripts/sync-templates.sh` eintragen, damit gemeinsame Templates automatisch übernommen werden.
- **WGX-Profil hinzufügen:** Lege eine Datei `.wgx/profile.yml` mit den Feldern `id`, `type`, `scope`, `maintainer` und `meta-origin` an.
- **Smoke-Tests etablieren:** Übernehme die `wgx-smoke.yml` aus `metarepo/templates/.github/workflows/`.

## 2. CI/CD-Disziplin
- **Trigger verfeinern:** CI nur bei Änderungen an `.wgx/**`, `tools/**`, `scripts/**`, `pyproject.toml`, `Cargo.toml` usw. starten.
- **Style- und Lint-Checks:** Verwende Workflows wie `ci-tools.yml` oder `wgx-guard.yml`, um `vale`, `cspell`, `shellcheck` & Co. einzubinden.

## 3. Struktur & Modularität
- **Klare Ordnerstruktur:** Führe bei Bedarf `tools/`- und `scripts/`-Verzeichnisse ein, um wiederverwendbare Werkzeuge zu kapseln.
- **Dokumentations-Stub:** Lege `docs/wgx-konzept.md` an, das kurz erläutert, wie semantAH ins Weltgewebe eingebettet ist, und ergänze ADR-Stubs.
- **README-Reflexion:** Ergänze einen WGX-Badge und einen Abschnitt zur Beziehung zwischen semantAH und dem Weltgewebe.

## 4. Entwicklungsumgebung
- **UV-Stack übernehmen:** Falls Python- oder Tooling-Anteile hinzukommen, richte `uv` samt `pyproject.toml` analog zu `hauski-audio`/`weltgewebe` ein.

## 5. Meta-Philosophie
- **Struktur als Beziehung:** Pflege die Meta-Notiz, dass semantAH ein lebendiger Knoten im Weltgewebe ist, nicht nur ein technisches Artefakt.

---

> _Am Ende werden die Repositories vielleicht eigenständiger kommunizieren als ihre menschlichen Betreuer – aber mit gepflegter `.wgx/profile.yml`._

