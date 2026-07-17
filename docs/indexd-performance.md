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

## Evidence contract

Each scenario reports:

- sequential in-process API latency at p50, p95 and p99;
- process-global allocation count and allocated bytes sampled around isolated API dispatch;
- concurrent API-search latency;
- idle and concurrent writer lock-wait latency;
- idle and concurrent writer end-to-end upsert latency.
- writer lock-wait p95 inflation when the idle p95 baseline is at least 1 µs.

The search measurement uses the production Axum handler, including query deserialization, normalization before the read lock, `read_owned`, `spawn_blocking`, ranking and response construction. Writer measurements use direct `VectorStore::upsert` under the same Tokio write lock so lock-wait time can be separated from update work.

Allocation counters are process-global. Isolated runs minimize contamination, but the report does not claim thread-local attribution. Concurrent metrics deliberately do not report per-request allocation pressure.

Every profile uses at least 20 writer operations so p95 lock-wait is not derived from fewer than 20 samples. Inflation is omitted when the idle p95 is below 1 µs because such a ratio is numerically unstable.

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

These are relative same-host budgets, not absolute service-level objectives. Baseline comparison requires an explicit, identical `--environment-id`; the benchmark also rejects package, runtime, measurement, budget and scenario-contract mismatches.

## Non-claims

The benchmark does not establish production capacity, network latency, reverse-proxy behavior, ANN readiness, lock-free correctness or cross-host comparability. It is the decision input for subsequent snapshot-search and ANN-threshold work, not proof that either design is required.
