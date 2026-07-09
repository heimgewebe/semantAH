# RPU-V1-T013 RepoBrief chunk embedding bridge proof

Status: review_ready
Task: `RPU-V1-T013`
PR: `heimgewebe/semantAH#254`
Head: bind externally to current PR head before merge
Patch SHA256: bind externally to current PR diff before merge

## Acceptance mapping

| Acceptance | Evidence |
| --- | --- |
| Stable inputs | `scripts/repobrief_chunk_bridge.py` requires stable chunk id/id, byte range and content hash or derives content hash from text. Tests reject rows without stable range. |
| External layer | Report marks owner `semantAH`, `repo_brief_core_ranking_changed: false`, `default_use: false`, and does not touch Lenskit/RepoBrief core. |
| Evaluation before default use | Optional goldset path reports recall, MRR and miss taxonomy; default report status is `not_run` with `promotion_allowed: false`. |

## Validation

```bash
python -m pytest tests/test_repobrief_chunk_bridge.py tests/test_push_index.py -q
python -m ruff check scripts/repobrief_chunk_bridge.py tests/test_repobrief_chunk_bridge.py
git diff --check
```

Observed local result:

- `17 passed, 1 skipped` (`numpy` missing for one pre-existing optional `push_index` test path)
- Ruff passed
- Diff whitespace check passed

## Self-review

No blocker found in this bounded prototype. The main limitation is intentional: the default local embedding is a deterministic stand-in for bridge and evaluation mechanics. It is not evidence that semantic quality improves.

## Non-claims

This proof does not establish answer correctness, semantic correctness, runtime deployment, default-ranking improvement, RepoBrief-core promotion readiness, security correctness, full CI success, or absence of regressions.
