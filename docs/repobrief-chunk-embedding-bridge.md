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
- a bridge report with non-claims and optional goldset recall/MRR.

## Promotion rule

The semantic layer is not a default ranking source. Promotion requires measured
recall/MRR and miss-taxonomy evidence against existing retrieval baselines.
