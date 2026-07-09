# RepoBrief chunk embedding bridge

Status: prototype
Task: `RPU-V1-T013`

This bridge lets SemantAH build an external semantic layer from existing RepoBrief
`chunk_index.jsonl` records.

## Boundary

The bridge consumes stable RepoBrief chunk records only:

- stable `chunk_id` / `id`;
- byte range: `file_path`, `start_byte`, `end_byte`;
- content hash, preferably `content_sha256` from the range reference.

It does not crawl repositories, refresh RepoBrief snapshots, mutate Git, write PRs,
or change RepoBrief core ranking.

## Outputs

`scripts/repobrief_chunk_bridge.py` can emit:

- external JSONL records suitable for SemantAH/indexd ingestion;
- optional parquet records;
- a bridge report with non-claims, optional goldset recall/MRR, and optional
  comparison against an existing RepoBrief retrieval-eval baseline.

Goldset evaluation ranks bridge records by deterministic query-token overlap when
`query` is present, otherwise by stable input order. This is a bounded evaluation
mechanic for the external layer, not a production semantic ranking claim.

## Baseline comparison

Use `--baseline-report <retrieval_eval.json>` with `--goldset <goldset.jsonl>` to
compare bridge metrics against existing RepoBrief retrieval metrics. The baseline
comparison checks recall, MRR and miss-count regression where the supplied report
contains those fields.

Missing baseline data leaves `baseline_comparison.status=not_run` or `warn`, and
`promotion_allowed` remains `false`.

## Promotion rule

The semantic layer is not a default ranking source. Promotion requires measured
recall/MRR and miss-taxonomy evidence against existing retrieval baselines plus a
later explicit promotion decision.
