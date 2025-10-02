# ADR-0001: Semantik-Contract
Status: accepted

Beschluss:
- semantAH liefert Nodes/Edges/Reports im JSON-Format gemäß `contracts/semantics/*.schema.json`.
- Weltgewebe konsumiert diese Artefakte read-only und setzt eigene Events oben drauf.

Konsequenzen:
- Änderungen sind semver-minor kompatibel (nur additive Felder).
- Breaking Changes nur per neue Schemas mit neuer Datei.
