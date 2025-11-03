### 📄 contracts/semantics/README.md

**Größe:** 664 B | **md5:** `c6f19573f1fae1acc50c13f5b2b5609e`

```markdown
# Semantics contracts

These JSON Schemas describe the contracts exchanged between the semantic pipeline
and downstream consumers. Example payloads in `examples/` double as
human-readable documentation and validation fixtures:

- `*-valid.json` payloads must satisfy their corresponding schema.
- `*-invalid.json` payloads are intentionally malformed and the CI job asserts
  that they fail validation. This guards against accidentally weakening a
  schema.

The GitHub Actions workflow uses [`ajv-cli`](https://github.com/ajv-validator/ajv-cli)
with the `@` syntax (for example, `-d @path/to/sample.json`) to load JSON from
files relative to the repository root.
```

### 📄 contracts/semantics/edge.schema.json

**Größe:** 623 B | **md5:** `b64e6b1ef369518413e1a5ef7814d796`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://semantah.com/contracts/semantics/edge.schema.json",
  "title": "SemEdge",
  "type": "object",
  "required": ["src", "dst", "rel"],
  "additionalProperties": false,
  "properties": {
    "src": { "type": "string" },
    "dst": { "type": "string" },
    "rel": { "type": "string" },
    "weight": { "type": "number" },
    "why": {
      "oneOf": [
        { "type": "string" },
        {
          "type": "array",
          "items": { "type": "string" }
        }
      ]
    },
    "updated_at": { "type": "string", "format": "date-time" }
  }
}
```

### 📄 contracts/semantics/node.schema.json

**Größe:** 665 B | **md5:** `d07637ca8de01eea573945c50f3cbe0b`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://semantah.com/contracts/semantics/node.schema.json",
  "title": "SemNode",
  "type": "object",
  "required": ["id", "type", "title"],
  "additionalProperties": false,
  "properties": {
    "id": { "type": "string" },
    "type": { "type": "string" },
    "title": { "type": "string" },
    "tags": {
      "type": "array",
      "items": { "type": "string" }
    },
    "topics": {
      "type": "array",
      "items": { "type": "string" }
    },
    "cluster": { "type": "integer" },
    "source": { "type": "string" },
    "updated_at": { "type": "string", "format": "date-time" }
  }
}
```

### 📄 contracts/semantics/report.schema.json

**Größe:** 510 B | **md5:** `10b3d2ef2b2391a73b948ce6f49238ec`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://semantah.com/contracts/semantics/report.schema.json",
  "title": "SemReport",
  "type": "object",
  "required": [
    "kind",
    "created_at"
  ],
  "properties": {
    "kind": {
      "type": "string"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "notes": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "stats": {
      "type": "object"
    }
  }
}
```

