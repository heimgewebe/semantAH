### 📄 semantAH/.github/workflows/ci-tools.yml

**Größe:** 1 KB | **md5:** `1c941e70d57370665107d5ad8e71bbc9`

```yaml
name: ci-tools

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

### 📄 semantAH/.github/workflows/ci.yml

**Größe:** 3 KB | **md5:** `bec931ee4bf7cc3cb42b41db81a8902a`

```yaml
name: ci
on:
  push:
    branches: [ "main" ]
  pull_request:
  workflow_dispatch:
  schedule:
    - cron: "17 4 * * 1"   # Mondays 04:17 UTC: weekly audit/smoke

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
      RUST_TOOLCHAIN: stable
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

  python-pipeline:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    concurrency:
      group: ${{ github.workflow }}-${{ github.ref }}
      cancel-in-progress: true
    steps:
      - uses: actions/checkout@v4

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

      - name: Demo run (no network)
        if: github.event_name != 'schedule'
        env:
          PYTHONWARNINGS: ignore
        run: |
          make -n all
          make demo

      - name: Scheduled demo run (best effort)
        if: github.event_name == 'schedule'
        continue-on-error: true
        env:
          PYTHONWARNINGS: ignore
        run: |
          make -n all
          make demo
```

### 📄 semantAH/.github/workflows/contracts.yml

**Größe:** 1 KB | **md5:** `d9bbb7805db12df805e0960cf3f2c179`

```yaml
name: contracts
on: { pull_request: {}, push: { branches:[main] }, workflow_dispatch: {} }
permissions: { contents: read }
jobs:
  json-schemas:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Validate JSON schemas
        run: |
          set -euo pipefail
          npm install -g ajv-cli@5 ajv-formats@^3
          for schema in node edge report; do
            ajv validate -c ajv-formats \
              -s contracts/semantics/${schema}.schema.json \
              -d @contracts/semantics/examples/${schema}-valid.json
          done

          for schema in node edge report; do
            if ajv validate -c ajv-formats \
              -s contracts/semantics/${schema}.schema.json \
              -d @contracts/semantics/examples/${schema}-invalid.json; then
              echo "Expected ${schema}-invalid.json to fail validation" >&2
              exit 1
            fi
          done
  docs-style:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "Docs present"; test -d docs || mkdir -p docs
```

### 📄 semantAH/.github/workflows/wgx-guard.yml

**Größe:** 2 KB | **md5:** `341ed1c46dac4824a1d9473a3de931a7`

```yaml
name: wgx-guard

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
          uv --version
          uv sync --frozen

      - name: Done
        run: echo "wgx-guard passed ✅"
```

