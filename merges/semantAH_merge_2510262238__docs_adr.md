### 📄 docs/adr/0001-semantics-contract.md

**Größe:** 382 B | **md5:** `cd35e79e053628ae631f3917415f6d61`

```markdown
# ADR-0001: Semantik-Contract
Status: accepted

Beschluss:
- semantAH liefert Nodes/Edges/Reports im JSON-Format gemäß `contracts/semantics/*.schema.json`.
- Weltgewebe konsumiert diese Artefakte read-only und setzt eigene Events oben drauf.

Konsequenzen:
- Änderungen sind semver-minor kompatibel (nur additive Felder).
- Breaking Changes nur per neue Schemas mit neuer Datei.
```

