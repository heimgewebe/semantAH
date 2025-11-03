### 📄 contracts/insights.schema.json

**Größe:** 1 KB | **md5:** `cf67feaadbf5144f0650256e89457f11`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Daily Insights",
  "type": "object",
  "additionalProperties": false,
  "required": ["generated_at", "source", "items"],
  "properties": {
    "generated_at": {
      "type": "string",
      "format": "date-time"
    },
    "source": {
      "type": "string",
      "minLength": 1
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["title", "summary", "url", "tags"],
        "properties": {
          "title": {
            "type": "string",
            "minLength": 1
          },
          "summary": {
            "type": "string",
            "minLength": 1
          },
          "url": {
            "type": "string",
            "format": "uri"
          },
          "tags": {
            "type": "array",
            "items": {
              "type": "string",
              "minLength": 1
            }
          }
        }
      }
    }
  }
}
```

