Canonical Artifact Names
========================

For CI stability and historical compatibility, the following artifact names are CANONICAL and MUST NOT be changed without a migration strategy:

* **Daily Insights**: `artifacts/insights.daily.json`
  * Contract: `contracts/insights.daily.schema.json`
  * Workflow: `insights-daily-drift.yml`

* **Knowledge Observatory**: `artifacts/knowledge.observatory.json`
  * Contract: `contracts/knowledge.observatory.schema.json`
  * Workflow: `knowledge-observatory-drift.yml`

Any deviation from this naming breaks the respective drift workflows and historical caches. Do not rename the canonical files.
