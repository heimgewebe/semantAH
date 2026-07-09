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
| Evaluation before default use | Goldset evaluation reports recall, MRR and miss taxonomy. `--baseline-report` compares those metrics against existing RepoBrief retrieval-eval metrics. Missing or regressed baseline comparison keeps `promotion_allowed: false`. |

## Validation

```bash
python -m pytest tests/test_repobrief_chunk_bridge.py tests/test_push_index.py -q
python -m ruff check scripts/repobrief_chunk_bridge.py tests/test_repobrief_chunk_bridge.py
python -m py_compile scripts/repobrief_chunk_bridge.py tests/test_repobrief_chunk_bridge.py
git diff --check
```

Observed local result before the latest self-review hardening:

- `17 passed, 1 skipped` (`numpy` missing for one pre-existing optional `push_index` test path)
- Ruff passed
- Diff whitespace check passed

Latest hardening added:

- query-aware deterministic goldset ranking for bridge evaluation;
- explicit `--baseline-report` ingestion;
- recall/MRR/miss-count regression comparison;
- tests that keep `promotion_allowed` false even when the comparison passes.

## Self-review

Initial self-review found one gap: optional MRR was derived from JSONL input order
and there was no explicit comparison against an existing RepoBrief retrieval
baseline. The hardening closes that gap at the bridge-report level.

Remaining limitation: the default local embedding is a deterministic stand-in for
bridge and evaluation mechanics. It is not evidence that semantic quality improves.

## Non-claims

This proof does not establish answer correctness, semantic correctness, runtime
deployment, default-ranking improvement, RepoBrief-core promotion readiness,
security correctness, full CI success, or absence of regressions.
