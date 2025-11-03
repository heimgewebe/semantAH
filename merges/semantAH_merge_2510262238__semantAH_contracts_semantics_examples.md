### 📄 semantAH/contracts/semantics/examples/edge-invalid.json

**Größe:** 97 B | **md5:** `44caaa1b85b1c914cb6953557f37af00`

```json
{
  "src": "md:example.md",
  "dst": "topic:example",
  "rel": "about",
  "why": ["valid", 42]
}
```

### 📄 semantAH/contracts/semantics/examples/edge-valid.json

**Größe:** 169 B | **md5:** `056e82a8a1ecfc0ce50c4dbf87ab8c23`

```json
{
  "src": "note:example",
  "dst": "note:other",
  "rel": "references",
  "weight": 0.75,
  "why": ["Linked from example.md"],
  "updated_at": "2024-01-05T10:05:00Z"
}
```

### 📄 semantAH/contracts/semantics/examples/node-invalid.json

**Größe:** 53 B | **md5:** `5e9d0a7d43abe5452e3eb97d0573c6b8`

```json
{
  "id": "topic:missing-title",
  "type": "topic"
}
```

### 📄 semantAH/contracts/semantics/examples/node-valid.json

**Größe:** 217 B | **md5:** `5312956be2462fc68de09339125b3d51`

```json
{
  "id": "note:example",
  "type": "note",
  "title": "Example Note",
  "tags": ["demo", "example"],
  "topics": ["workflow"],
  "cluster": 1,
  "source": "vault/example.md",
  "updated_at": "2024-01-05T10:00:00Z"
}
```

### 📄 semantAH/contracts/semantics/examples/report-invalid.json

**Größe:** 51 B | **md5:** `504eb01a4d9f898a6080725844c8cdbc`

```json
{
  "kind": "daily",
  "created_at": "yesterday"
}
```

### 📄 semantAH/contracts/semantics/examples/report-valid.json

**Größe:** 160 B | **md5:** `cca379b769b153772f5ef46d4539203f`

```json
{
  "kind": "summary",
  "created_at": "2024-01-05T10:10:00Z",
  "notes": ["Contains a single example node"],
  "stats": {
    "nodes": 1,
    "edges": 1
  }
}
```

