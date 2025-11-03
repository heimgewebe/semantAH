### 📄 .github/workflows/ci-tools.yml

**Größe:** 1 KB | **md5:** `d57f3917f914886e4076be1fdc8edb5e`

```yaml
name: ci-tools
permissions:
  # Allow cache usage (requires actions: write)
  contents: read
  actions: write

on:
  push:
    paths:
      - "scripts/**"
      - "pyproject.toml"
      - "uv.lock"
      - ".github/workflows/ci-tools.yml"
  pull_request:
    paths:
      - "scripts/**"
      - "pyproject.toml"
      - "uv.lock"
      - ".github/workflows/ci-tools.yml"
  workflow_dispatch:

jobs:
  tools:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install uv
        uses: astral-sh/setup-uv@v2

      - name: Cache uv downloads
        uses: actions/cache@v4
        with:
          path: ~/.cache/uv
          key: ${{ runner.os }}-uv-${{ hashFiles('**/uv.lock') }}
          restore-keys: |
            ${{ runner.os }}-uv-

      # Hinweis: Solange uv.lock nur ein Stub ist, schlagen gefrorene Syncs fehl.
      # Sobald ein echter Lockfile committed wurde, kann wieder `uv sync --frozen` verwendet werden.
      - name: Sync deps (non-frozen until lock is real)
        run: uv sync

      - name: Run index/graph/related (smoke)
        run: |
          set -euxo pipefail
          uv run scripts/build_index.py || true
          uv run scripts/build_graph.py || true
          uv run scripts/update_related.py || true
```

### 📄 .github/workflows/ci.yml

**Größe:** 12 KB | **md5:** `2b36c266ebd886ecd1aa7005372678a7`

```yaml
name: CI

permissions: read-all

on:
  push:
    branches: ["main"]
  pull_request:
  workflow_dispatch:
    inputs:
      toolchain:
        description: "Rust toolchain channel (for example, stable or nightly)"
        required: false
        default: stable
  workflow_call:
    inputs:
      toolchain:
        description: "Rust toolchain channel (for example, stable or nightly)"
        required: false
        type: string
        default: stable
  schedule:
    - cron: "17 4 * * 1"   # Mondays 04:17 UTC: weekly audit/smoke

env:
  DEFAULT_RUST_TOOLCHAIN: stable

jobs:
  rust:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    concurrency:
      group: ${{ github.workflow }}-${{ github.ref }}
      cancel-in-progress: true
    env:
      CARGO_TERM_COLOR: always
      RUST_BACKTRACE: 1
      RUST_TOOLCHAIN: ${{ inputs.toolchain || env.DEFAULT_RUST_TOOLCHAIN }}
    steps:
      - uses: actions/checkout@v4

      # Maintained toolchain action
      - name: Setup Rust toolchain
        uses: dtolnay/rust-toolchain@v1
        with:
          toolchain: ${{ env.RUST_TOOLCHAIN }}
          override: true
          components: clippy rustfmt

      - name: Rust cache
        uses: swatinem/rust-cache@v2

      - name: Cargo fmt
        run: cargo fmt --all -- --check

      - name: Cargo clippy
        run: cargo clippy --all-targets --all-features -- -D warnings

      - name: Build
        env:
          RUSTFLAGS: -D warnings
        run: cargo build --workspace --all-features --locked

      - name: Test
        env:
          RUSTFLAGS: -D warnings
        run: cargo test --workspace --all-features --locked -- --nocapture

      - name: indexd healthcheck smoke test
        run: |
          cargo run -p indexd --quiet &
          INDEXD_PID=$!
          cleanup() { kill $INDEXD_PID >/dev/null 2>&1 || true; }
          trap cleanup EXIT

          for _ in $(seq 1 30); do
            if curl -fsS http://127.0.0.1:8080/healthz >/dev/null; then
              READY=1
              break
            fi
            sleep 1
          done

          if [ -z "${READY:-}" ]; then
            echo "indexd healthz endpoint did not become ready" >&2
            exit 1
          fi

          curl -fsS http://127.0.0.1:8080/healthz

      - name: Cache cargo advisory DB
        uses: actions/cache@v4
        with:
          path: ~/.cargo/advisory-db
          key: advisory-${{ runner.os }}-${{ hashFiles('**/Cargo.lock') }}

      - name: Install cargo-audit
        uses: taiki-e/install-action@v2
        with:
          tool: cargo-audit

      - name: Security audit (with retry)
        uses: nick-fields/retry@v3
        with:
          timeout_minutes: 10
          max_attempts: 4
          retry_wait_seconds: 30
          command: cargo audit

  rust-coverage:
    name: Rust coverage (cargo llvm-cov)
    runs-on: ubuntu-latest
    permissions:
      contents: read
    concurrency:
      group: ${{ github.workflow }}-${{ github.ref }}-rustcov
    steps:
      - uses: actions/checkout@v4

      - name: Setup Rust toolchain
        uses: actions-rs/toolchain@v1
        with:
          profile: minimal
          toolchain: stable
          components: llvm-tools-preview

      - name: Cache cargo
        uses: actions/cache@v4
        with:
          path: |
            ~/.cargo/bin
            ~/.cargo/registry
            ~/.cargo/git
            target
          key: cargo-${{ runner.os }}-${{ hashFiles('**/Cargo.lock') }}
          restore-keys: |
            cargo-${{ runner.os }}-

      - name: Install cargo-llvm-cov
        uses: taiki-e/install-action@v2
        with:
          tool: cargo-llvm-cov

      - name: Build & run coverage
        env:
          RUSTFLAGS: ""
        run: cargo llvm-cov --workspace --lcov --output-path lcov.info

      - name: Upload Rust coverage to Codecov
        if: vars.CODECOV_UPLOAD == 'true'
        uses: codecov/codecov-action@v4
        with:
          files: lcov.info
          flags: rust
          fail_ci_if_error: true
          verbose: false

      - name: Store lcov artifact
        uses: actions/upload-artifact@v4
        with:
          name: rust-lcov
          path: lcov.info

  unit-tests:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    concurrency:
      group: ${{ github.workflow }}-${{ github.ref }}
      cancel-in-progress: true
    steps:
      - uses: actions/checkout@v4

      # --- Python Setup ---
      - name: Setup uv (Python)
        uses: astral-sh/setup-uv@v4
        with:
          python-version: "3.11"

      - name: uv cache
        uses: actions/cache@v4
        with:
          path: |
            ~/.cache/uv
            .venv
          key: uv-${{ runner.os }}-${{ hashFiles('**/pyproject.toml', '**/uv.lock') }}
          restore-keys: |
            uv-${{ runner.os }}-

      - name: Sync env
        run: uv sync --frozen

      - name: Ensure pyarrow available (CI bootstrap)
        run: |
          uv run python - <<'PY'
          import importlib, subprocess, sys
          try:
              importlib.import_module("pyarrow")
              print("pyarrow already present")
          except Exception:
              print("Installing pyarrow for CI…")
              subprocess.check_call([sys.executable, "-m", "pip", "install", "pyarrow"])
          PY

      - name: Prepare reports dir
        run: mkdir -p reports

      - name: Ensure pytest-cov available (bootstrap-in-CI only)
        run: |
          uv run python - <<'PY'
          import sys, subprocess
          try:
              import pytest_cov, coverage  # noqa: F401
              print("pytest-cov & coverage already present")
          except Exception:
              print("Installing pytest-cov & coverage just for CI…")
              subprocess.check_call([sys.executable, "-m", "pip", "install", "pytest-cov", "coverage"])
          PY

      # --- Unit-Tests + JUnit + Coverage ---
      - name: Unit tests (exclude integration)
        env:
          HYPOTHESIS_PROFILE: ci
        run: >
          uv run pytest -q -m "not integration"
          --junitxml=reports/unit-junit.xml
          --cov=.
          --cov-report=xml:reports/coverage-unit.xml
          --cov-report=term-missing:skip-covered

      - name: Move coverage data
        run: mv .coverage reports/.coverage.unit

      - name: Upload unit test report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: junit-unit
          path: reports/unit-junit.xml
          retention-days: 7

      - name: Upload unit coverage report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage-unit
          path: |
            reports/coverage-unit.xml
            reports/.coverage.unit
          retention-days: 7

      - name: Upload to Codecov (unit)
        if: always() && vars.CODECOV_UPLOAD == 'true'
        uses: codecov/codecov-action@v4
        with:
          files: reports/coverage-unit.xml
          flags: unit

      - name: Demo run (no network)
        if: github.event_name != 'schedule'
        env:
          PYTHONWARNINGS: ignore
        run: |
          make -n all
          make demo

      - name: Scheduled demo run (best effort)
        if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'
        continue-on-error: true
        env:
          PYTHONWARNINGS: ignore
        run: |
          make -n all
          make demo

  integration-tests:
    if: ${{ github.event_name == 'schedule' || github.event_name == 'workflow_dispatch' }}
    needs: [unit-tests]
    runs-on: ubuntu-latest
    permissions:
      contents: read
    concurrency:
      group: ${{ github.workflow }}-${{ github.ref }}-integration
      cancel-in-progress: true
    steps:
      - uses: actions/checkout@v4

      # --- Python Setup ---
      - name: Setup uv (Python)
        uses: astral-sh/setup-uv@v4
        with:
          python-version: "3.11"

      - name: uv cache
        uses: actions/cache@v4
        with:
          path: |
            ~/.cache/uv
            .venv
          key: uv-${{ runner.os }}-${{ hashFiles('**/pyproject.toml', '**/uv.lock') }}
          restore-keys: |
            uv-${{ runner.os }}-

      - name: Sync env
        run: uv sync --frozen

      - name: Ensure pyarrow available (CI bootstrap)
        run: |
          uv run python - <<'PY'
          import importlib, subprocess, sys
          try:
              importlib.import_module("pyarrow")
              print("pyarrow already present")
          except Exception:
              print("Installing pyarrow for CI…")
              subprocess.check_call([sys.executable, "-m", "pip", "install", "pyarrow"])
          PY

      - name: Prepare reports dir
        run: mkdir -p reports

      - name: Ensure pytest-cov available (bootstrap-in-CI only)
        run: |
          uv run python - <<'PY'
          import sys, subprocess
          try:
              import pytest_cov, coverage  # noqa: F401
              print("pytest-cov & coverage already present")
          except Exception:
              print("Installing pytest-cov & coverage just for CI…")
              subprocess.check_call([sys.executable, "-m", "pip", "install", "pytest-cov", "coverage"])
          PY

      # --- Integration-Tests + JUnit + Coverage ---
      - name: Integration tests
        env:
          PYTHONWARNINGS: ignore
        run: >
          uv run pytest -q -m integration -v
          --junitxml=reports/integration-junit.xml
          --cov=.
          --cov-report=xml:reports/coverage-integration.xml
          --cov-report=term:skip-covered

      - name: Move coverage data
        run: mv .coverage reports/.coverage.integration

      - name: Upload integration test report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: junit-integration
          path: reports/integration-junit.xml
          retention-days: 7

      - name: Upload integration coverage report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage-integration
          path: |
            reports/coverage-integration.xml
            reports/.coverage.integration
          retention-days: 7

      - name: Upload to Codecov (integration)
        if: always() && vars.CODECOV_UPLOAD == 'true'
        uses: codecov/codecov-action@v4
        with:
          files: reports/coverage-integration.xml
          flags: integration

  coverage-merge:
    name: Coverage (merge)
    runs-on: ubuntu-latest
    needs: [unit-tests, integration-tests]
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4

      - name: Setup uv (Python)
        uses: astral-sh/setup-uv@v4
        with:
          python-version: "3.11"

      - name: Prepare reports dir
        run: mkdir -p reports

      - name: Download unit coverage data
        uses: actions/download-artifact@v4
        with:
          name: coverage-unit
          path: reports

      - name: Download integration coverage data
        uses: actions/download-artifact@v4
        with:
          name: coverage-integration
          path: reports

      - name: Ensure coverage available
        run: |
          uv run python - <<'PY'
          import sys, subprocess
          try:
              import coverage  # noqa: F401
              print("coverage present")
          except Exception:
              print("Installing coverage just for CI…")
              subprocess.check_call([sys.executable, "-m", "pip", "install", "coverage"])
          PY

      - name: Combine .coverage files
        env:
          COVERAGE_FILE: reports/.coverage.merged
        run: |
          uv run coverage combine reports/.coverage.unit reports/.coverage.integration
          uv run coverage xml -i -o reports/coverage-merged.xml
          uv run coverage report -i --skip-covered || true

      - name: Upload merged coverage artifact
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage-merged
          path: reports/coverage-merged.xml
          retention-days: 7

      - name: Upload to Codecov (merged)
        if: always() && vars.CODECOV_UPLOAD == 'true'
        uses: codecov/codecov-action@v4
        with:
          files: reports/coverage-merged.xml
          flags: merged
```

### 📄 .github/workflows/contracts.yml

**Größe:** 353 B | **md5:** `6a693d908f898cd0ddc827d0e10e08a8`

```yaml
name: contracts-validate
on: [push, pull_request]

# Restrict the default permissions of the GITHUB_TOKEN.
# Adjust scopes as necessary for the jobs in this workflow.
permissions:
  contents: read

jobs:
  # Validate the contracts using a reusable workflow
  validate:
    uses: heimgewebe/metarepo/.github/workflows/contracts-validate.yml@contracts-v1
```

### 📄 .github/workflows/wgx-guard.yml

**Größe:** 2 KB | **md5:** `acf0681be6a19bb44341df6564fd4042`

```yaml
name: wgx-guard
permissions:
  contents: read

on:
  push:
    paths:
      - ".wgx/**"
      - ".github/workflows/wgx-guard.yml"
      - "pyproject.toml"
      - "Cargo.toml"
  pull_request:
    paths:
      - ".wgx/**"
      - ".github/workflows/wgx-guard.yml"
      - "pyproject.toml"
      - "Cargo.toml"
  workflow_dispatch:

jobs:
  guard:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4

      - name: Check .wgx/profile.yml presence
        run: |
          test -f .wgx/profile.yml || { echo "::error::.wgx/profile.yml missing"; exit 1; }
          echo "found .wgx/profile.yml"

      - name: Validate minimal schema keys
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install PyYAML
        run: python -m pip install --upgrade pip pyyaml
      - name: Run schema-lite check
        run: |
          python - <<'PY'
import sys, yaml, pathlib
p = pathlib.Path(".wgx/profile.yml")
data = yaml.safe_load(p.read_text(encoding="utf-8"))
required_top = ["version","env_priority","tooling","tasks"]
missing = [k for k in required_top if k not in data]
if missing:
    print(f"::error::missing keys: {missing}")
    sys.exit(1)
envp = data["env_priority"]
if not isinstance(envp, list) or not envp:
    print("::error::env_priority must be a non-empty list")
    sys.exit(1)
for t in ["up","lint","test","build","smoke"]:
    if t not in data["tasks"]:
        print(f"::error::task '{t}' missing")
        sys.exit(1)
print("schema-lite ok")
PY

      - name: Cache uv downloads
        if: ${{ hashFiles('pyproject.toml', 'uv.lock') != '' }}
        uses: actions/cache@v4
        with:
          path: ~/.cache/uv
          key: uv-${{ runner.os }}-${{ hashFiles('pyproject.toml', 'uv.lock') }}
          restore-keys: |
            uv-${{ runner.os }}-

      - name: (Optional) UV bootstrap (pyproject present)
        if: ${{ hashFiles('pyproject.toml') != '' }}
        run: |
          curl -LsSf https://astral.sh/uv/install.sh | sh
          echo "$HOME/.local/bin" >> $GITHUB_PATH
          export PATH="$HOME/.local/bin:$PATH"
          uv --version
          uv sync --frozen

      - name: Done
        run: echo "wgx-guard passed ✅"
```

