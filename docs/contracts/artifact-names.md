Canonical Artifact Names
========================

For CI stability and historical compatibility, the following artifact names are CANONICAL and MUST NOT be changed without a migration strategy:

* **Observatory Snapshot**: `artifacts/insights.daily.json`
  * Alias (semantic): `artifacts/knowledge.observatory.json`
  * Contract: `contracts/knowledge.observatory.schema.json`

Any deviation from this naming breaks the `insights-daily-drift.yml` or `knowledge-observatory-drift.yml` workflows and historical caches. Do not rename the canonical file.
