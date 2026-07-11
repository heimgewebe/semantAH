# SemantAH dependency security hygiene — T001

Observed: 2026-07-11
Bureau task: `SEMANTAH-SECURITY-HYGIENE-V1-T001`
Repository: `heimgewebe/semantAH`

## Live alert state before the change

GitHub Dependabot reported ten open default-branch alerts:

| Severity | Dependency | Vulnerable lock | First patched version | Advisory |
|---|---|---:|---:|---|
| high | pyarrow | 21.0.0 | 23.0.1 | GHSA-rgxp-2hwp-jwgg |
| high | rustls-webpki | 0.103.8 | 0.103.13 | GHSA-82j2-j2ch-gfr8 |
| high | quinn-proto | 0.11.13 | 0.11.14 | GHSA-6xvm-j4wr-6v98 |
| medium | pytest | 8.4.2 | 9.0.3 | GHSA-6w46-j5rx-g56g |
| medium | rustls-webpki | 0.103.8 | 0.103.10 | GHSA-pwjx-qhcg-rvj4 |
| medium | bytes | 1.10.1 | 1.11.1 | GHSA-434x-w66g-qw3r |
| low | Pygments | 2.19.2 | 2.20.0 | GHSA-5239-wwwm-4pmq |
| low | rand | 0.9.2 | 0.9.3 | GHSA-cq8v-f236-94qc |
| low | rustls-webpki | 0.103.8 | 0.103.12 | GHSA-xgp8-3hg3-c2mh |
| low | rustls-webpki | 0.103.8 | 0.103.12 | GHSA-965h-392x-2mh5 |

## Remediation

- Python security floors are explicit in `pyproject.toml`:
  `pyarrow>=23.0.1`, `pytest>=9.0.3`, `pygments>=2.20.0`.
- `uv.lock` resolves exactly those first patched versions.
- `Cargo.lock` resolves `bytes 1.11.1`, `quinn-proto 0.11.14`,
  `rand 0.9.3`, and `rustls-webpki 0.103.13`.
- The workspace `reqwest` dependency moves from 0.11 to 0.12. This removes
  the duplicate legacy `rustls 0.21` / `rustls-webpki 0.101.7` chain rather
  than leaving an older TLS implementation in the graph.

## Verification

- 108 non-integration Python tests pass with pytest 9.0.3.
- The Rust workspace tests pass with the updated dependency graph.
- `uv lock --check`, Ruff lint, and `git diff --check` pass.
- Exact lock-version and dependency-tree checks confirm that the vulnerable
  versions listed above are absent.

Two local checks are not valid success evidence:

1. The isolated Connector runtime aborts inside the native PyArrow allocator
   when reading Parquet, for both patched PyArrow 23.0.1 and the tested 25.0.0
   alternative. The regular Python suite passes; the marked Parquet/HTTP
   integration test is therefore left as an explicit environment blocker and
   must be judged by GitHub CI or a non-sandboxed runtime.
2. The locally installed `cargo-audit` cannot parse a current RustSec advisory
   containing CVSS 4.0. GitHub Dependabot remains the live advisory source for
   this change; the stale audit client is not treated as a clean audit result.

## Non-claims

Closing the listed dependency alerts does not establish full security
correctness, runtime safety, exploit unreachability, or the absence of
non-Dependabot vulnerabilities.
