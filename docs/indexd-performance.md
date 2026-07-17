# indexd performance evidence

`indexd_real_workload` is a deterministic, dependency-light benchmark for the production `/index/search` handler and its shared `Tokio::RwLock<VectorStore>`.

## Run

```bash
cargo bench -p indexd --bench indexd_real_workload -- \
  --profile smoke \
  --source-commit "$(git rev-parse HEAD)" \
  --environment-id heim-pc-indexd-release-v1 \
  --output artifacts/indexd-benchmark-smoke.json
```

Profiles are explicit:

- `smoke`: two bounded scenarios for build and contract validation.
- `standard`: 5,000–10,000 vectors at 384, 768 and 1,536 dimensions.
- `full`: opt-in stress evidence up to 25,000 vectors at 1,536 dimensions.

Run release-built benchmarks on an otherwise quiet host. Do not compare reports from different profiles or materially different hosts.

## Search snapshot contract

The live store keeps each namespace in an immutable `Arc<NamespaceItems>`. `NamespaceItems` contains a contiguous vector of immutable `Arc<StoredItem>` entries for cache-friendly exact search and a key-to-index map for replacement and metadata lookup.

A search request:

1. normalizes its owned query before touching the store;
2. acquires the Tokio read lock only long enough to clone the selected namespace `Arc` and read the dimensionality;
3. releases the store lock;
4. performs exact ranking and snippet materialization on the request-local immutable snapshot in `spawn_blocking`.

Snapshot capture is O(1) and does not clone keys, embeddings or metadata. If a writer overlaps a retained snapshot, `Arc::make_mut` shallow-clones the namespace index and entry-pointer vector before mutation. Unchanged `StoredItem` values remain shared; embedding and metadata payloads are not deep-cloned. Each request therefore observes one internally consistent namespace version even when the live store subsequently replaces or deletes entries.

This is copy-on-write, not lock-free writing. The first overlapping writer may pay an O(namespace entries) shallow-clone cost. The benchmark reports writer end-to-end maximum latency in addition to lock-wait percentiles so this cost cannot be hidden by later cheap writes.

## Evidence contract

Each scenario reports:

- sequential in-process API latency at p50, p95 and p99;
- process-global allocation count and allocated bytes sampled around isolated API dispatch;
- concurrent API-search latency;
- idle and concurrent writer lock-wait latency;
- idle and concurrent writer end-to-end upsert latency, including maximum latency;
- writer lock-wait p95 inflation when the idle p95 baseline is at least 1 µs.

The search measurement uses the production Axum handler, including request deserialization, query normalization, O(1) namespace snapshot capture, `spawn_blocking`, exact ranking, snippet extraction and response construction. Writer measurements use direct `VectorStore::upsert` under the same Tokio write lock so lock-wait time can be separated from copy-on-write and update work.

Allocation counters are process-global. Isolated runs minimize contamination, but the report does not claim thread-local attribution. Concurrent metrics deliberately do not report per-request allocation pressure.

Every profile uses at least 20 writer operations. The `standard` profile uses 100 writer operations and increased search samples so percentile comparisons are less sensitive to individual scheduler outliers. Inflation is omitted when the idle p95 is below 1 µs because such a ratio is numerically unstable.

The binary records its own `measurement_contract.search_lock_mode`; callers cannot select or relabel it. The snapshot implementation emits `namespace-snapshot`. A controlled historical baseline must be built from the old held-lock production code with the same v2 benchmark harness and the harness constant set to `held-read-lock`.

## Regression budgets

A report can compare itself to a same-profile baseline:

```bash
cargo bench -p indexd --bench indexd_real_workload -- \
  --profile standard \
  --environment-id heim-pc-indexd-release-v1 \
  --baseline artifacts/indexd-benchmark-standard-baseline.json \
  --output artifacts/indexd-benchmark-standard-current.json
```

The command exits with status `2` after writing the report when any budget is exceeded:

| Metric | Maximum regression |
| --- | ---: |
| sequential p50 | 5% |
| sequential p95 | 10% |
| sequential p99 | 15% |
| allocated bytes per isolated search | 5% |
| concurrent search p95 | 10% |
| concurrent writer lock-wait p95 | 15% |
| concurrent writer end-to-end maximum | 15% |

For sequential p50, p95 and p99, a sub-millisecond measurement fails only when it exceeds both the relative limit above and a 150 µs absolute increase. This hybrid gate keeps scheduler jitter from deciding a merge while still rejecting larger absolute regressions.

For a `held-read-lock` → `namespace-snapshot` comparison at 768 dimensions or more, both writer lock-wait p95 and writer end-to-end maximum must improve by at least 75%. This prevents a design from merely moving wait time from lock acquisition into hidden copy-on-write work.

These are relative same-host budgets, not absolute service-level objectives. Baseline comparison requires an explicit, identical `--environment-id`; the benchmark also rejects package, runtime, report schema, invariant measurement, budget and scenario-contract mismatches. Report schema v2 is intentionally not comparable to the lower-sample v1 reports without a fresh controlled baseline.

## Persistence compatibility

The in-memory representation changed, but the JSONL persistence schema did not. Save operations still emit namespace, document ID, chunk ID, embedding and metadata. Load operations still validate dimensionality and rebuild normalized entries through `VectorStore::upsert`.

## Non-claims

The snapshot path does not establish production capacity, network latency, reverse-proxy behavior, ANN readiness, lock-free writes, zero-cost overlapping updates or cross-host comparability. It preserves exact linear ranking and is evidence for deciding later ANN thresholds, not proof that an ANN design is required.
