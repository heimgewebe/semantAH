### 📄 merges/semantAH_merge_2510262237__.github_ISSUE_TEMPLATE.md

**Größe:** 807 B | **md5:** `186649c7dc70dc123552088e2bfeb695`

```markdown
### 📄 .github/ISSUE_TEMPLATE/bug_report.yml

**Größe:** 283 B | **md5:** `09318ac5e13050436bf0eb8658445d7e`

```yaml
name: Bug report
description: Problem melden
title: "[bug] "
labels: ["bug"]
body:
  - type: textarea
    id: what-happened
    attributes:
      label: Was ist passiert?
      description: Schritte, erwartetes Ergebnis, tatsächliches Ergebnis
    validations:
      required: true
```

### 📄 .github/ISSUE_TEMPLATE/feature_request.yml

**Größe:** 265 B | **md5:** `500ed4b2381198ded897e5a1971e5370`

```yaml
name: Feature request
description: Vorschlag einreichen
title: "[feat] "
labels: ["enhancement"]
body:
  - type: textarea
    id: idea
    attributes:
      label: Idee
      description: Was soll verbessert/neu gebaut werden?
    validations:
      required: true
```
```

### 📄 merges/semantAH_merge_2510262237__.github_workflows.md

**Größe:** 17 KB | **md5:** `433155a5183a9434007cc11a19ea1ce8`

```markdown
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
```

### 📄 merges/semantAH_merge_2510262237__.wgx.md

**Größe:** 3 KB | **md5:** `121958a190347ca0b4c2479968039f8b`

```markdown
### 📄 .wgx/profile.yml

**Größe:** 3 KB | **md5:** `ee6aef00c6b7a998e9129d865ef0f766`

```yaml
version: 1
repo:
  # Kurzname des Repos (wird automatisch aus git ableitbar sein – hier nur Doku)
  name: auto
  description: "WGX profile for unified tasks and env priorities"

env_priority:
  # Ordnungsprinzip laut Vorgabe
  - devcontainer
  - devbox
  - mise
  - direnv
  - termux

tooling:
  python:
    uv: true           # uv ist Standard-Layer für Python-Tools
    precommit: true    # falls .pre-commit-config.yaml vorhanden
  rust:
    cargo: auto        # wenn Cargo.toml vorhanden → Rust-Checks aktivieren
    clippy_strict: true
    fmt_check: true
    deny: optional     # cargo-deny, falls vorhanden

tasks:
  up:
    desc: "Dev-Umgebung hochfahren (Container/venv/tooling bootstrap)"
    sh:
      - |
        if command -v devcontainer >/dev/null 2>&1 || [ -f .devcontainer/devcontainer.json ]; then
          echo "[wgx.up] devcontainer context detected"
        fi
        if command -v uv >/dev/null 2>&1; then
          uv --version || true
          [ -f pyproject.toml ] && uv sync --frozen || true
        fi
        [ -f .pre-commit-config.yaml ] && command -v pre-commit >/dev/null 2>&1 && pre-commit install || true
  lint:
    desc: "Schnelle statische Checks (Rust/Python/Markdown/YAML)"
    sh:
      - |
        # Rust
        if [ -f Cargo.toml ]; then
          cargo fmt --all -- --check
          cargo clippy --all-targets --all-features -- -D warnings
        fi
        # Python
        if [ -f pyproject.toml ]; then
          if command -v uv >/dev/null 2>&1; then uv run ruff check . || true; fi
          if command -v uv >/dev/null 2>&1; then uv run ruff format --check . || true; fi
        fi
        # Docs
        command -v markdownlint >/dev/null 2>&1 && markdownlint "**/*.md" || true
        command -v yamllint    >/dev/null 2>&1 && yamllint . || true
  test:
    desc: "Testsuite"
    sh:
      - |
        [ -f Cargo.toml ] && cargo test --all --all-features || true
        if [ -f pyproject.toml ] && command -v uv >/dev/null 2>&1; then
          uv run pytest -q || true
        fi
  build:
    desc: "Build-Artefakte erstellen"
    sh:
      - |
        [ -f Cargo.toml ] && cargo build --release || true
        if [ -f pyproject.toml ] && command -v uv >/dev/null 2>&1; then
          uv build || true
        fi
  smoke:
    desc: "Schnelle Smoke-Checks (läuft <60s)"
    sh:
      - |
        echo "[wgx.smoke] repo=$(basename "$(git rev-parse --show-toplevel)")"
        [ -f Cargo.toml ] && cargo metadata --no-deps > /dev/null || true
        [ -f pyproject.toml ] && grep -q '\[project\]' pyproject.toml || true

meta:
  owner: "heimgewebe"
  conventions:
    gewebedir: ".gewebe"
    version_endpoint: "/version"
    tasks_standardized: true
```
```

### 📄 merges/semantAH_merge_2510262237__cli.md

**Größe:** 5 KB | **md5:** `fee69cc4717c1dc5a1fec2b27c0df6e1`

```markdown
### 📄 cli/ingest_leitstand.py

**Größe:** 5 KB | **md5:** `91b377100efa44181c8e5c73b788aa7d`

```python
#!/usr/bin/env python3
"""Read Leitstand export and produce today's insights."""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

MAX_BYTES_DEFAULT = 10 * 1024
DEFAULT_LIMIT = 32


@dataclass
class Insight:
    tags: List[str]
    title: str
    summary: str
    url: str

    @classmethod
    def from_record(cls, record: dict) -> "Insight | None":
        title = _coerce_str(record.get("title"))
        summary = _coerce_str(record.get("summary"))
        url = _coerce_str(record.get("url"))
        if not (title and summary and url):
            return None

        tags = _coerce_tags(record.get("tags"))
        return cls(tags=tags, title=title, summary=summary, url=url)

    def to_dict(self) -> dict:
        return {
            "tags": self.tags,
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
        }


def _coerce_str(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return str(value)


def _coerce_tags(value) -> List[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, Iterable) or isinstance(value, (bytes, bytearray)):
        return []
    tags = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            tags.append(text)
    return tags


def read_last_records(path: Path, limit: int) -> list[dict]:
    lines = deque(maxlen=limit)
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            lines.append(line)
    records: list[dict] = []
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Cannot parse line as JSON: {line[:80]}...") from exc
        if not isinstance(record, dict):
            raise ValueError(
                "Each JSONL record must be an object with insight fields"
            )
        records.append(record)
    return records


def shrink_to_size(payload: dict, max_bytes: int) -> dict:
    """Drop oldest items until serialized payload fits into max_bytes."""
    items = payload.get("items", [])
    if not isinstance(items, list):
        return payload

    encoded = _encode(payload)
    while len(encoded) > max_bytes and items:
        items.pop(0)
        encoded = _encode(payload)
    if len(encoded) > max_bytes:
        raise ValueError(
            "Unable to satisfy max-bytes constraint even after dropping all items"
        )
    return payload


def _encode(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def build_payload(insights: list[Insight]) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "leitstand",
        "items": [insight.to_dict() for insight in insights],
    }


def ingest(args: argparse.Namespace) -> Path:
    source_path = Path(args.source).expanduser().resolve()
    output_path = Path(args.output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not source_path.is_file():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    raw_records = read_last_records(source_path, args.limit)
    insights = []
    for record in raw_records:
        insight = Insight.from_record(record)
        if insight is not None:
            insights.append(insight)

    payload = build_payload(insights)
    shrink_to_size(payload, args.max_bytes)

    data_bytes = _encode(payload)
    output_path.write_bytes(data_bytes)
    return output_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read Leitstand JSONL export and store the latest insights in "
            "vault/.gewebe/insights/today.json"
        )
    )
    parser.add_argument(
        "source",
        help="Path to leitstand/data/aussen.jsonl",
    )
    parser.add_argument(
        "--output",
        default="vault/.gewebe/insights/today.json",
        help="Target JSON file (default: vault/.gewebe/insights/today.json)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Number of trailing records to read (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=MAX_BYTES_DEFAULT,
        help="Maximum JSON payload size in bytes (default: 10240)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        output_path = ingest(args)
    except Exception as exc:  # pragma: no cover - small CLI
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```
```

### 📄 merges/semantAH_merge_2510262237__codex.md

**Größe:** 2 KB | **md5:** `941ef18486ddee417b5afff9edd833aa`

```markdown
### 📄 codex/CONTRIBUTING.md

**Größe:** 2 KB | **md5:** `7965c5b2e1601d244d152f9e138c1422`

```markdown
# Beitragende Leitfäden für das semantAH-Repo

Dieses Dokument fasst die empfohlenen "Lern-Anweisungen" zusammen, die aus der Beobachtung anderer WGX-fähiger Repositories gewonnen wurden. Ziel ist es, semantAH als vollwertigen Knoten des Weltgewebe-Ökosystems zu etablieren.

## 1. Synchronisierung & Meta-Struktur
- **Template-Sync aktivieren:** semantAH in `metarepo/scripts/sync-templates.sh` eintragen, damit gemeinsame Templates automatisch übernommen werden.
- **WGX-Profil hinzufügen:** Lege eine Datei `.wgx/profile.yml` mit den Feldern `id`, `type`, `scope`, `maintainer` und `meta-origin` an.
- **Smoke-Tests etablieren:** Übernehme die `wgx-smoke.yml` aus `metarepo/templates/.github/workflows/`.

## 2. CI/CD-Disziplin
- **Trigger verfeinern:** CI nur bei Änderungen an `.wgx/**`, `tools/**`, `scripts/**`, `pyproject.toml`, `Cargo.toml` usw. starten.
- **Style- und Lint-Checks:** Verwende Workflows wie `ci-tools.yml` oder `wgx-guard.yml`, um `vale`, `cspell`, `shellcheck` & Co. einzubinden.

## 3. Struktur & Modularität
- **Klare Ordnerstruktur:** Führe bei Bedarf `tools/`- und `scripts/`-Verzeichnisse ein, um wiederverwendbare Werkzeuge zu kapseln.
- **Dokumentations-Stub:** Lege `docs/wgx-konzept.md` an, das kurz erläutert, wie semantAH ins Weltgewebe eingebettet ist, und ergänze ADR-Stubs.
- **README-Reflexion:** Ergänze einen WGX-Badge und einen Abschnitt zur Beziehung zwischen semantAH und dem Weltgewebe.

## 4. Entwicklungsumgebung
- **UV-Stack übernehmen:** Falls Python- oder Tooling-Anteile hinzukommen, richte `uv` samt `pyproject.toml` analog zu `hauski-audio`/`weltgewebe` ein.

## 5. Meta-Philosophie
- **Struktur als Beziehung:** Pflege die Meta-Notiz, dass semantAH ein lebendiger Knoten im Weltgewebe ist, nicht nur ein technisches Artefakt.

---

> _Am Ende werden die Repositories vielleicht eigenständiger kommunizieren als ihre menschlichen Betreuer – aber mit gepflegter `.wgx/profile.yml`._
```
```

### 📄 merges/semantAH_merge_2510262237__contracts.md

**Größe:** 1 KB | **md5:** `f1b0247290b3821db5179e810cfbf661`

```markdown
### 📄 contracts/insights.schema.json

**Größe:** 1 KB | **md5:** `cf67feaadbf5144f0650256e89457f11`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Daily Insights",
  "type": "object",
  "additionalProperties": false,
  "required": ["generated_at", "source", "items"],
  "properties": {
    "generated_at": {
      "type": "string",
      "format": "date-time"
    },
    "source": {
      "type": "string",
      "minLength": 1
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["title", "summary", "url", "tags"],
        "properties": {
          "title": {
            "type": "string",
            "minLength": 1
          },
          "summary": {
            "type": "string",
            "minLength": 1
          },
          "url": {
            "type": "string",
            "format": "uri"
          },
          "tags": {
            "type": "array",
            "items": {
              "type": "string",
              "minLength": 1
            }
          }
        }
      }
    }
  }
}
```
```

### 📄 merges/semantAH_merge_2510262237__contracts_semantics.md

**Größe:** 3 KB | **md5:** `71f007d96c99d78b7356874479fb88ef`

```markdown
### 📄 contracts/semantics/README.md

**Größe:** 664 B | **md5:** `c6f19573f1fae1acc50c13f5b2b5609e`

```markdown
# Semantics contracts

These JSON Schemas describe the contracts exchanged between the semantic pipeline
and downstream consumers. Example payloads in `examples/` double as
human-readable documentation and validation fixtures:

- `*-valid.json` payloads must satisfy their corresponding schema.
- `*-invalid.json` payloads are intentionally malformed and the CI job asserts
  that they fail validation. This guards against accidentally weakening a
  schema.

The GitHub Actions workflow uses [`ajv-cli`](https://github.com/ajv-validator/ajv-cli)
with the `@` syntax (for example, `-d @path/to/sample.json`) to load JSON from
files relative to the repository root.
```

### 📄 contracts/semantics/edge.schema.json

**Größe:** 623 B | **md5:** `b64e6b1ef369518413e1a5ef7814d796`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://semantah.com/contracts/semantics/edge.schema.json",
  "title": "SemEdge",
  "type": "object",
  "required": ["src", "dst", "rel"],
  "additionalProperties": false,
  "properties": {
    "src": { "type": "string" },
    "dst": { "type": "string" },
    "rel": { "type": "string" },
    "weight": { "type": "number" },
    "why": {
      "oneOf": [
        { "type": "string" },
        {
          "type": "array",
          "items": { "type": "string" }
        }
      ]
    },
    "updated_at": { "type": "string", "format": "date-time" }
  }
}
```

### 📄 contracts/semantics/node.schema.json

**Größe:** 665 B | **md5:** `d07637ca8de01eea573945c50f3cbe0b`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://semantah.com/contracts/semantics/node.schema.json",
  "title": "SemNode",
  "type": "object",
  "required": ["id", "type", "title"],
  "additionalProperties": false,
  "properties": {
    "id": { "type": "string" },
    "type": { "type": "string" },
    "title": { "type": "string" },
    "tags": {
      "type": "array",
      "items": { "type": "string" }
    },
    "topics": {
      "type": "array",
      "items": { "type": "string" }
    },
    "cluster": { "type": "integer" },
    "source": { "type": "string" },
    "updated_at": { "type": "string", "format": "date-time" }
  }
}
```

### 📄 contracts/semantics/report.schema.json

**Größe:** 510 B | **md5:** `10b3d2ef2b2391a73b948ce6f49238ec`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://semantah.com/contracts/semantics/report.schema.json",
  "title": "SemReport",
  "type": "object",
  "required": [
    "kind",
    "created_at"
  ],
  "properties": {
    "kind": {
      "type": "string"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "notes": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "stats": {
      "type": "object"
    }
  }
}
```
```

### 📄 merges/semantAH_merge_2510262237__contracts_semantics_examples.md

**Größe:** 2 KB | **md5:** `42499b8bf23ad2365f760d9673d768aa`

```markdown
### 📄 contracts/semantics/examples/edge-invalid.json

**Größe:** 97 B | **md5:** `44caaa1b85b1c914cb6953557f37af00`

```json
{
  "src": "md:example.md",
  "dst": "topic:example",
  "rel": "about",
  "why": ["valid", 42]
}
```

### 📄 contracts/semantics/examples/edge-valid.json

**Größe:** 169 B | **md5:** `056e82a8a1ecfc0ce50c4dbf87ab8c23`

```json
{
  "src": "note:example",
  "dst": "note:other",
  "rel": "references",
  "weight": 0.75,
  "why": ["Linked from example.md"],
  "updated_at": "2024-01-05T10:05:00Z"
}
```

### 📄 contracts/semantics/examples/node-invalid.json

**Größe:** 53 B | **md5:** `5e9d0a7d43abe5452e3eb97d0573c6b8`

```json
{
  "id": "topic:missing-title",
  "type": "topic"
}
```

### 📄 contracts/semantics/examples/node-valid.json

**Größe:** 217 B | **md5:** `5312956be2462fc68de09339125b3d51`

```json
{
  "id": "note:example",
  "type": "note",
  "title": "Example Note",
  "tags": ["demo", "example"],
  "topics": ["workflow"],
  "cluster": 1,
  "source": "vault/example.md",
  "updated_at": "2024-01-05T10:00:00Z"
}
```

### 📄 contracts/semantics/examples/report-invalid.json

**Größe:** 51 B | **md5:** `504eb01a4d9f898a6080725844c8cdbc`

```json
{
  "kind": "daily",
  "created_at": "yesterday"
}
```

### 📄 contracts/semantics/examples/report-valid.json

**Größe:** 160 B | **md5:** `cca379b769b153772f5ef46d4539203f`

```json
{
  "kind": "summary",
  "created_at": "2024-01-05T10:10:00Z",
  "notes": ["Contains a single example node"],
  "stats": {
    "nodes": 1,
    "edges": 1
  }
}
```
```

### 📄 merges/semantAH_merge_2510262237__crates_embeddings.md

**Größe:** 2 KB | **md5:** `944fae31d775970f41a9b0ac9a6717ff`

```markdown
### 📄 crates/embeddings/Cargo.toml

**Größe:** 368 B | **md5:** `91383c922ff1a03f2686f5552161aeae`

```toml
[package]
name = "embeddings"
version = "0.1.0"
edition = "2021"
license = "MIT"
description = "Abstractions and clients for semantic embedding providers"

[dependencies]
anyhow.workspace = true
async-trait.workspace = true
reqwest.workspace = true
serde.workspace = true
serde_json.workspace = true
tracing.workspace = true

[dev-dependencies]
tokio.workspace = true
```

### 📄 crates/embeddings/README.md

**Größe:** 1 KB | **md5:** `3535cf7fe5e2170793af7aa23c3bfa10`

```markdown
# `embeddings` crate

Die `embeddings`-Crate bündelt sämtliche Embedder-Abstraktionen für semantAH. Sie stellt einen `Embedder`-Trait bereit und enthält aktuell eine Implementierung für [Ollama](https://ollama.ai/).

## Aufbau
- `Embedder`-Trait (`src/lib.rs`): definiert asynchrone Batch-Einbettung, Dimensionsabfrage und eine ID des Providers.
- `OllamaEmbedder`: schlanker HTTP-Client, der das Ollama-Embeddings-API (`/api/embeddings`) anspricht.
- Hilfsfunktionen zur Validierung von Antwortformat und Dimensionalität.

## Nutzung
```rust
use embeddings::{Embedder, OllamaConfig, OllamaEmbedder};

# async fn example() -> anyhow::Result<()> {
let embedder = OllamaEmbedder::new(OllamaConfig {
    base_url: "http://localhost:11434".into(),
    model: "nomic-embed-text".into(),
    dim: 768,
});

let vectors = embedder.embed(&["Notiz A".to_string(), "Notiz B".to_string()]).await?;
assert_eq!(vectors.len(), 2);
# Ok(())
# }
```

## Fehlerbehandlung
- Responses ohne Embeddings lösen einen `anyhow::Error` mit einer sprechenden Meldung aus.
- Dimensionalitätskonflikte werden früh erkannt (`unexpected embedding dimensionality`).

## Tests
- JSON-Parsing von Einzel-/Batch-Antworten.
- Sicherstellung, dass leere Batches keine Requests erzeugen.
- Validierung auf fehlerhafte Dimensionalität.

Für weitere Backend-Implementierungen kann der Trait erweitert und via Feature-Gates integriert werden.
```
```

### 📄 merges/semantAH_merge_2510262237__crates_embeddings_src.md

**Größe:** 6 KB | **md5:** `6bae2d9e02138c7683a423deac8dd0a0`

```markdown
### 📄 crates/embeddings/src/lib.rs

**Größe:** 6 KB | **md5:** `e6207eb43a0420c114301081342651b1`

```rust
//! Embedder abstractions and implementations for semantAH.

use anyhow::{anyhow, Result};
use async_trait::async_trait;
use reqwest::Client;
use serde::{Deserialize, Serialize};

/// Public trait that every embedder implementation must fulfill.
#[async_trait]
pub trait Embedder: Send + Sync {
    /// Embed a batch of texts and return a vector of embedding vectors.
    async fn embed(&self, texts: &[String]) -> Result<Vec<Vec<f32>>>;

    /// The dimensionality of the returned embeddings.
    fn dim(&self) -> usize;

    /// Short identifier (e.g. `"ollama"`).
    fn id(&self) -> &'static str;
}

/// Configuration for the Ollama embedder backend.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OllamaConfig {
    pub base_url: String,
    pub model: String,
    pub dim: usize,
}

/// Simple HTTP client for the Ollama embeddings endpoint.
#[derive(Clone)]
pub struct OllamaEmbedder {
    client: Client,
    url: String,
    model: String,
    dim: usize,
}

impl OllamaEmbedder {
    /// Build a new embedder from configuration.
    pub fn new(config: OllamaConfig) -> Self {
        let OllamaConfig {
            base_url,
            model,
            dim,
        } = config;
        Self {
            client: Client::new(),
            url: base_url,
            model,
            dim,
        }
    }
}

#[derive(Debug, Serialize)]
struct OllamaRequest<'a> {
    model: &'a str,
    input: &'a [String],
}

#[derive(Debug, Deserialize)]
struct OllamaEmbeddingRow {
    embedding: Vec<f32>,
}

#[derive(Debug, Deserialize)]
struct OllamaResponse {
    embedding: Option<Vec<f32>>,
    embeddings: Option<Vec<OllamaEmbeddingRow>>,
}

impl OllamaResponse {
    fn into_embeddings(self) -> Result<Vec<Vec<f32>>> {
        if let Some(embeddings) = self.embeddings {
            return Ok(embeddings.into_iter().map(|row| row.embedding).collect());
        }

        if let Some(embedding) = self.embedding {
            return Ok(vec![embedding]);
        }

        Err(anyhow!("ollama response did not contain embeddings"))
    }
}

fn validate_embeddings(
    expected_count: usize,
    embeddings: &[Vec<f32>],
    expected_dim: usize,
) -> Result<()> {
    if embeddings.len() != expected_count {
        return Err(anyhow!(
            "ollama returned {} embeddings for {} input texts",
            embeddings.len(),
            expected_count
        ));
    }

    if embeddings.iter().any(|row| row.len() != expected_dim) {
        return Err(anyhow!("unexpected embedding dimensionality"));
    }

    Ok(())
}

#[async_trait]
impl Embedder for OllamaEmbedder {
    async fn embed(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        if texts.is_empty() {
            return Ok(Vec::new());
        }

        let response = self
            .client
            .post(format!("{}/api/embeddings", self.url))
            .json(&OllamaRequest {
                model: &self.model,
                input: texts,
            })
            .send()
            .await?;

        if !response.status().is_success() {
            return Err(anyhow!(
                "ollama responded with status {}",
                response.status()
            ));
        }

        let body: OllamaResponse = response.json().await?;
        let embeddings = body.into_embeddings()?;

        validate_embeddings(texts.len(), &embeddings, self.dim)?;

        Ok(embeddings)
    }

    fn dim(&self) -> usize {
        self.dim
    }

    fn id(&self) -> &'static str {
        "ollama"
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_single_embedding_response() {
        let json = serde_json::json!({
            "embedding": [0.1, 0.2, 0.3],
            "model": "nomic-embed-text",
        });

        let response: OllamaResponse = serde_json::from_value(json).unwrap();
        let embeddings = response.into_embeddings().unwrap();

        assert_eq!(embeddings.len(), 1);
        assert_eq!(embeddings[0], vec![0.1, 0.2, 0.3]);
    }

    #[test]
    fn parses_batch_embedding_response() {
        let json = serde_json::json!({
            "embeddings": [
                { "embedding": [1.0, 2.0], "text": "first" },
                { "embedding": [3.0, 4.0], "text": "second" }
            ],
        });

        let response: OllamaResponse = serde_json::from_value(json).unwrap();
        let embeddings = response.into_embeddings().unwrap();

        assert_eq!(embeddings, vec![vec![1.0, 2.0], vec![3.0, 4.0]]);
    }

    #[tokio::test]
    async fn empty_batch_returns_empty() {
        let embedder = OllamaEmbedder::new(OllamaConfig {
            base_url: "http://localhost:11434".into(),
            model: "dummy".into(),
            dim: 1536,
        });

        let result = embedder.embed(&[]).await.unwrap();
        assert!(result.is_empty());
    }

    #[test]
    fn validate_embeddings_rejects_count_mismatch() {
        let embeddings = vec![vec![1.0, 2.0]];
        let err = validate_embeddings(2, &embeddings, 2).expect_err("expected count mismatch");
        assert!(
            err.to_string()
                .contains("ollama returned 1 embeddings for 2 input texts"),
            "unexpected error message: {}",
            err
        );
    }

    #[test]
    fn validate_embeddings_rejects_dim_mismatch() {
        let embeddings = vec![vec![1.0, 2.0], vec![3.0]];
        let err = validate_embeddings(2, &embeddings, 2).expect_err("expected dim mismatch");
        assert!(
            err.to_string()
                .contains("unexpected embedding dimensionality"),
            "unexpected error message: {}",
            err
        );
    }
}
```
```

### 📄 merges/semantAH_merge_2510262237__crates_indexd.md

**Größe:** 3 KB | **md5:** `09fd6bee07c958a310c564bf23fa5b6f`

```markdown
### 📄 crates/indexd/Cargo.toml

**Größe:** 624 B | **md5:** `f0c0a86441e61016f3521680a54e7680`

```toml
[package]
name = "indexd"
version = "0.1.0"
edition = "2021"
license = "MIT"
description = "HTTP service for indexing and semantic search"

[dependencies]
anyhow.workspace = true
axum.workspace = true
serde.workspace = true
serde_json.workspace = true
tokio.workspace = true
tracing.workspace = true
tracing-subscriber.workspace = true
config.workspace = true
thiserror.workspace = true
futures.workspace = true

[dependencies.embeddings]
path = "../embeddings"

[dev-dependencies]
tower = "0.5"
tempfile = "3"
reqwest = { version = "0.12", default-features = false, features = ["json", "rustls-tls"] }
async-trait = "0.1"
```

### 📄 crates/indexd/README.md

**Größe:** 2 KB | **md5:** `5d1fc59707444675aeef4e3d42a991da`

```markdown
# `indexd` crate

`indexd` ist der HTTP-Dienst für den semantischen Index. Er kapselt den Axum-Server, einen im Speicher gehaltenen `VectorStore` und stellt CRUD-Operationen für Chunks sowie eine Suchroute bereit.

## Komponenten
- `AppState`: verwaltet den `VectorStore` (RW-Lock) und kann in Tests ersetzt werden.
- `run`: Hilfsfunktion, die den Server unter `0.0.0.0:8080` startet und zusätzliche Routen injiziert.
- `store`-Modul: In-Memory-Vektorablage mit Namensraum-Unterstützung und einfacher Persistenz-Erweiterbarkeit.

## HTTP-API
| Methode & Pfad | Beschreibung | Beispiel-Payload |
| --- | --- | --- |
| `POST /index/upsert` | Nimmt Chunks mit Embeddings entgegen und ersetzt vorhandene Einträge atomar. | `{ "doc_id": "note-42", "namespace": "vault", "chunks": [{ "id": "note-42#0", "text": "...", "meta": { "embedding": [0.1, 0.2], "source_path": "notes/foo.md" }}] }` |
| `POST /index/delete` | Entfernt alle Chunks eines Dokuments aus einem Namespace. | `{ "doc_id": "note-42", "namespace": "vault" }` |
| `POST /index/search` | Führt eine k-Nearest-Nachbarn-Suche aus und liefert Treffer mitsamt Score & Rationale zurück. Aktuell noch Stub → leeres `results`-Array. | `{ "query": "backup policy", "namespace": "vault", "k": 10 }` |
| `GET /healthz` | Healthcheck für Liveness-Probes. | – |

Antworten enthalten bei Fehlern strukturierte JSON-Bodies (`{"error": "..."}`) sowie `400 Bad Request` bei Validierungsproblemen.

## Beispielstart
```bash
cargo run -p indexd
```

## Tests
- `tests/healthz.rs`: prüft den Healthcheck-Endpunkt.
- Integrationstest in `src/main.rs`: stellt sicher, dass fehlende Dimensionalität nicht zum teilweisen Upsert führt.

Für persistente Vector-Stores oder echte Ähnlichkeitssuche kann das `store`-Modul ersetzt und `handle_search` erweitert werden.
```
```

### 📄 merges/semantAH_merge_2510262237__crates_indexd_src.md

**Größe:** 28 KB | **md5:** `424b8c369fca5dc6ee473c31dd130def`

```markdown
### 📄 crates/indexd/src/api.rs

**Größe:** 13 KB | **md5:** `443d5392039e6806d5ec1683d76caa91`

```rust
use std::sync::Arc;

use axum::{extract::State, http::StatusCode, routing::post, Json, Router};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tracing::{debug, info};

use crate::AppState;

#[derive(Debug, Deserialize)]
pub struct UpsertRequest {
    pub doc_id: String,
    pub namespace: String,
    pub chunks: Vec<ChunkPayload>,
}

#[derive(Debug, Deserialize)]
pub struct ChunkPayload {
    pub id: String,
    #[serde(rename = "text")]
    _text: String,
    #[serde(default = "default_meta")]
    pub meta: Value,
}

#[derive(Debug, Deserialize)]
pub struct DeleteRequest {
    pub doc_id: String,
    pub namespace: String,
}

#[derive(Debug, Deserialize)]
pub struct SearchRequest {
    /// TODO(server-side-embeddings): replace client-provided vectors with generated embeddings.
    pub query: QueryPayload,
    #[serde(default = "default_k")]
    pub k: u32,
    pub namespace: String,
    #[serde(default)]
    pub filters: Option<Value>,
    /// Optional top-level embedding payload until server-side embeddings are available.
    #[serde(default)]
    pub embedding: Option<Value>,
    /// Legacy fallback: support former top-level `meta.embedding`
    /// (kept optional to remain backward compatible).
    #[serde(default)]
    pub meta: Option<Value>,
}

#[derive(Debug, Deserialize)]
#[serde(untagged)]
pub enum QueryPayload {
    Text(String),
    WithMeta {
        text: String,
        #[serde(default = "default_meta")]
        meta: Value,
    },
}

impl QueryPayload {
    fn text(&self) -> &str {
        match self {
            QueryPayload::Text(text) => text,
            QueryPayload::WithMeta { text, .. } => text,
        }
    }
}

#[derive(Debug, Serialize)]
pub struct SearchResponse {
    pub results: Vec<SearchHit>,
}

#[derive(Debug, Serialize)]
pub struct SearchHit {
    pub doc_id: String,
    pub chunk_id: String,
    pub score: f32,
    pub snippet: String,
    pub rationale: Vec<String>,
}

pub fn router(state: Arc<AppState>) -> Router {
    Router::new()
        .route("/index/upsert", post(handle_upsert))
        .route("/index/delete", post(handle_delete))
        .route("/index/search", post(handle_search))
        .with_state(state)
}

fn default_k() -> u32 {
    10
}

fn default_meta() -> Value {
    Value::Object(Default::default())
}

async fn handle_upsert(
    State(state): State<Arc<AppState>>,
    Json(payload): Json<UpsertRequest>,
) -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    let chunk_count = payload.chunks.len();
    info!(doc_id = %payload.doc_id, namespace = %payload.namespace, chunks = chunk_count, "received upsert");

    let UpsertRequest {
        doc_id,
        namespace,
        chunks,
    } = payload;

    let mut store = state.store.write().await;

    let mut staged = Vec::with_capacity(chunk_count);
    let mut expected_dim = store.dims;

    for chunk in chunks {
        let ChunkPayload { id, _text: _, meta } = chunk;

        let mut meta = match meta {
            Value::Object(map) => map,
            _ => return Err(bad_request("chunk meta must be an object")),
        };

        let embedding_value = meta
            .remove("embedding")
            .ok_or_else(|| bad_request("chunk meta must contain an embedding array"))?;

        let vector = parse_embedding(embedding_value).map_err(bad_request)?;

        if let Some(expected) = expected_dim {
            if expected != vector.len() {
                return Err(bad_request(format!(
                    "chunk embedding dimensionality mismatch: expected {expected}, got {}",
                    vector.len()
                )));
            }
        } else {
            expected_dim = Some(vector.len());
        }

        staged.push((id, vector, Value::Object(meta)));
    }

    for (id, vector, meta) in staged {
        store
            .upsert(&namespace, &doc_id, &id, vector, meta)
            .map_err(|err| bad_request(err.to_string()))?;
    }

    Ok(Json(json!({
        "status": "accepted",
        "chunks": chunk_count,
    })))
}

async fn handle_delete(
    State(state): State<Arc<AppState>>,
    Json(payload): Json<DeleteRequest>,
) -> Json<Value> {
    info!(doc_id = %payload.doc_id, namespace = %payload.namespace, "received delete");

    let mut store = state.store.write().await;
    store.delete_doc(&payload.namespace, &payload.doc_id);

    Json(json!({
        "status": "accepted"
    }))
}

async fn handle_search(
    State(state): State<Arc<AppState>>,
    Json(payload): Json<SearchRequest>,
) -> Result<Json<SearchResponse>, (StatusCode, Json<Value>)> {
    let query_text_owned = payload.query.text().to_owned();
    let query_text = &query_text_owned;

    debug!(
        query = %query_text,
        k = payload.k,
        namespace = %payload.namespace,
        filters = payload
            .filters
            .as_ref()
            .map(|_| "provided")
            .unwrap_or("none"),
        "received search"
    );

    let SearchRequest {
        query,
        k,
        namespace,
        filters,
        embedding,
        meta,
    } = payload;

    let embedder = state.embedder();

    let query_embedding_value = match query {
        QueryPayload::Text(_) => None,
        QueryPayload::WithMeta { meta, .. } => {
            let mut meta_map = match meta {
                Value::Object(map) => map,
                _ => return Err(bad_request("query meta must be an object")),
            };
            meta_map.remove("embedding")
        }
    };

    let k = k as usize;
    let filter_value = filters.unwrap_or(Value::Null);

    // Priority: query.meta.embedding > top-level embedding > legacy meta.embedding
    let embedding: Vec<f32> = if let Some(value) = query_embedding_value {
        parse_embedding(value).map_err(bad_request)?
    } else if let Some(value) = embedding {
        parse_embedding(value).map_err(bad_request)?
    } else if let Some(meta) = meta {
        let mut legacy_meta = match meta {
            Value::Object(map) => map,
            _ => return Err(bad_request("legacy meta must be an object")),
        };

        let Some(value) = legacy_meta.remove("embedding") else {
            return Err(bad_request(
                "embedding is required (provide query.meta.embedding, top-level embedding, or legacy meta.embedding)",
            ));
        };

        parse_embedding(value).map_err(bad_request)?
    } else if let Some(embedder) = embedder {
        let vectors = embedder
            .embed(&[query_text_owned.clone()])
            .await
            .map_err(|err| bad_request(format!("failed to generate embedding: {err}")))?;
        vectors.into_iter().next().ok_or_else(|| {
            bad_request("failed to generate embedding: embedder returned no embeddings")
        })?
    } else {
        return Err(bad_request(
            "embedding is required (provide query.meta.embedding, top-level embedding, legacy meta.embedding, or configure INDEXD_EMBEDDER_PROVIDER)",
        ));
    };

    let store = state.store.read().await;
    let scored = store.search(&namespace, &embedding, k, &filter_value);

    let results = scored
        .into_iter()
        .map(|(doc_id, chunk_id, score)| {
            let snippet = store
                .chunk_meta(&namespace, &doc_id, &chunk_id)
                .and_then(|meta| meta.get("snippet"))
                .and_then(|value| value.as_str())
                .unwrap_or_default()
                .to_string();
            SearchHit {
                doc_id,
                chunk_id,
                score,
                snippet,
                rationale: Vec::new(),
            }
        })
        .collect();

    Ok(Json(SearchResponse { results }))
}

fn parse_embedding(value: Value) -> Result<Vec<f32>, String> {
    match value {
        Value::Array(values) => values
            .into_iter()
            .map(|v| {
                v.as_f64()
                    .map(|num| num as f32)
                    .ok_or_else(|| "embedding must be an array of numbers".to_string())
            })
            .collect(),
        _ => Err("embedding must be an array of numbers".to_string()),
    }
}

fn bad_request(message: impl Into<String>) -> (StatusCode, Json<Value>) {
    let body = json!({
        "error": message.into(),
    });
    (StatusCode::BAD_REQUEST, Json(body))
}

#[cfg(test)]
mod tests {
    use super::*;

    use axum::extract::State;
    use serde_json::json;

    #[tokio::test]
    async fn upsert_is_atomic_on_failure() {
        let state = Arc::new(AppState::new());

        let payload = UpsertRequest {
            doc_id: "doc".into(),
            namespace: "ns".into(),
            chunks: vec![
                ChunkPayload {
                    id: "chunk-1".into(),
                    _text: "ignored".into(),
                    meta: json!({ "embedding": [0.1, 0.2] }),
                },
                ChunkPayload {
                    id: "chunk-2".into(),
                    _text: "ignored".into(),
                    meta: json!({ "embedding": [0.3] }),
                },
            ],
        };

        let result = handle_upsert(State(state.clone()), Json(payload)).await;
        assert!(
            result.is_err(),
            "upsert should fail on mismatched dimensions"
        );

        let store = state.store.read().await;
        assert!(store.items.is_empty(), "store must remain empty");
    }

    #[tokio::test]
    async fn search_requires_embedding() {
        let state = Arc::new(AppState::new());
        let payload = SearchRequest {
            query: QueryPayload::Text("hello".into()),
            k: 5,
            namespace: "ns".into(),
            filters: None,
            embedding: None,
            meta: None,
        };

        let result = handle_search(State(state), Json(payload)).await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn search_accepts_top_level_embedding() {
        let state = Arc::new(AppState::new());

        let upsert_payload = UpsertRequest {
            doc_id: "doc".into(),
            namespace: "ns".into(),
            chunks: vec![ChunkPayload {
                id: "chunk-1".into(),
                _text: "ignored".into(),
                meta: json!({ "embedding": [0.1, 0.2] }),
            }],
        };

        let upsert_result = handle_upsert(State(state.clone()), Json(upsert_payload)).await;
        assert!(upsert_result.is_ok(), "upsert should succeed");

        let payload = SearchRequest {
            query: QueryPayload::Text("hello".into()),
            k: 1,
            namespace: "ns".into(),
            filters: None,
            embedding: Some(json!([0.1, 0.2])),
            meta: None,
        };

        let result = handle_search(State(state), Json(payload)).await;
        assert!(result.is_ok(), "search should accept top-level embedding");
    }

    #[tokio::test]
    async fn search_accepts_query_meta_embedding() {
        let state = Arc::new(AppState::new());

        let upsert_payload = UpsertRequest {
            doc_id: "doc".into(),
            namespace: "ns".into(),
            chunks: vec![ChunkPayload {
                id: "chunk-1".into(),
                _text: "ignored".into(),
                meta: json!({ "embedding": [0.1, 0.2] }),
            }],
        };

        let upsert_result = handle_upsert(State(state.clone()), Json(upsert_payload)).await;
        assert!(upsert_result.is_ok(), "upsert should succeed");

        let payload = SearchRequest {
            query: QueryPayload::WithMeta {
                text: "hello".into(),
                meta: json!({ "embedding": [0.1, 0.2] }),
            },
            k: 1,
            namespace: "ns".into(),
            filters: None,
            embedding: None,
            meta: None,
        };

        let result = handle_search(State(state), Json(payload)).await;
        assert!(result.is_ok(), "search should accept query.meta.embedding");
    }

    #[tokio::test]
    async fn search_accepts_legacy_meta_embedding() {
        let state = Arc::new(AppState::new());

        let upsert_payload = UpsertRequest {
            doc_id: "doc".into(),
            namespace: "ns".into(),
            chunks: vec![ChunkPayload {
                id: "chunk-1".into(),
                _text: "ignored".into(),
                meta: json!({ "embedding": [0.1, 0.2] }),
            }],
        };

        let upsert_result = handle_upsert(State(state.clone()), Json(upsert_payload)).await;
        assert!(upsert_result.is_ok(), "upsert should succeed");

        let payload = SearchRequest {
            query: QueryPayload::Text("hello".into()),
            k: 1,
            namespace: "ns".into(),
            filters: None,
            embedding: None,
            meta: Some(json!({ "embedding": [0.1, 0.2] })),
        };

        let result = handle_search(State(state), Json(payload)).await;
        assert!(result.is_ok(), "search should accept legacy meta.embedding");
    }
}
```

### 📄 crates/indexd/src/key.rs

**Größe:** 418 B | **md5:** `a23af333eca438abe1b3928e874f1fbf`

```rust
pub(crate) const KEY_SEPARATOR: &str = "\u{241F}";

pub(crate) fn make_chunk_key(doc_id: &str, chunk_id: &str) -> String {
    format!("{doc_id}{KEY_SEPARATOR}{chunk_id}")
}

pub(crate) fn split_chunk_key(key: &str) -> (String, String) {
    match key.split_once(KEY_SEPARATOR) {
        Some((doc_id, chunk_id)) => (doc_id.to_string(), chunk_id.to_string()),
        None => (key.to_string(), String::new()),
    }
}
```

### 📄 crates/indexd/src/lib.rs

**Größe:** 5 KB | **md5:** `7a8a493f5846815035adc2dbab23186a`

```rust
pub mod api;
mod key;
mod persist;
pub mod store;

use std::{env, net::SocketAddr, sync::Arc};

use axum::{routing::get, Router};
use embeddings::{Embedder, OllamaConfig, OllamaEmbedder};
use tokio::sync::RwLock;
use tokio::{net::TcpListener, signal};
use tracing::{info, warn, Level};
use tracing_subscriber::FmtSubscriber;

pub struct AppState {
    pub store: RwLock<store::VectorStore>,
    embedder: Option<Arc<dyn Embedder>>,
}

impl std::fmt::Debug for AppState {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("AppState")
            .field("store", &"VectorStore")
            .field(
                "embedder",
                &self
                    .embedder
                    .as_ref()
                    .map(|embedder| embedder.id())
                    .unwrap_or("none"),
            )
            .finish()
    }
}

impl AppState {
    pub fn new() -> Self {
        Self::with_embedder(None)
    }

    pub fn with_embedder(embedder: Option<Arc<dyn Embedder>>) -> Self {
        Self {
            store: RwLock::new(store::VectorStore::new()),
            embedder,
        }
    }

    pub fn embedder(&self) -> Option<Arc<dyn Embedder>> {
        self.embedder.as_ref().map(Arc::clone)
    }
}

impl Default for AppState {
    fn default() -> Self {
        Self::new()
    }
}

pub use store::{VectorStore, VectorStoreError};

#[derive(Clone, Default)]
pub struct App;

/// Basis-Router (Healthcheck). Zusätzliche Routen werden in `run` via `build_routes` ergänzt.
pub fn router(state: Arc<AppState>) -> Router {
    Router::new()
        .route("/healthz", get(healthz))
        .with_state(state)
}

/// Startet den Server auf 0.0.0.0:8080 und merged die vom Caller gelieferten Routen.
pub async fn run(
    build_routes: impl FnOnce(Arc<AppState>) -> Router + Send + 'static,
) -> anyhow::Result<()> {
    init_tracing();

    let embedder = maybe_init_embedder()?;
    let state = Arc::new(AppState::with_embedder(embedder));
    persist::maybe_load_from_env(&state).await?;

    let router = build_routes(state.clone()).merge(router(state.clone()));

    let addr: SocketAddr = "0.0.0.0:8080".parse()?;
    info!(%addr, "starting indexd");

    let listener = TcpListener::bind(addr).await?;
    axum::serve(listener, router)
        .with_graceful_shutdown(shutdown_signal())
        .await?;

    if let Err(err) = persist::maybe_save_from_env(&state).await {
        warn!(error = %err, "failed to persist vector store on shutdown");
    }

    info!("indexd stopped");
    Ok(())
}

fn maybe_init_embedder() -> anyhow::Result<Option<Arc<dyn Embedder>>> {
    match env::var("INDEXD_EMBEDDER_PROVIDER") {
        Ok(provider) => {
            let provider = provider.trim();
            match provider {
                "ollama" => {
                    let base_url = env::var("INDEXD_EMBEDDER_BASE_URL")
                        .unwrap_or_else(|_| "http://127.0.0.1:11434".to_string());
                    let model = env::var("INDEXD_EMBEDDER_MODEL")
                        .unwrap_or_else(|_| "nomic-embed-text".to_string());
                    let dim = env::var("INDEXD_EMBEDDER_DIM")
                        .ok()
                        .and_then(|value| value.parse::<usize>().ok())
                        .unwrap_or(1536);

                    info!(
                        provider = provider,
                        model = %model,
                        base_url = %base_url,
                        dim,
                        "configured embedder"
                    );
                    let embedder = OllamaEmbedder::new(OllamaConfig {
                        base_url,
                        model,
                        dim,
                    });
                    let embedder: Arc<dyn Embedder> = Arc::new(embedder);
                    Ok(Some(embedder))
                }
                other => {
                    anyhow::bail!("unsupported embedder provider: {other}");
                }
            }
        }
        Err(env::VarError::NotPresent) => Ok(None),
        Err(err) => Err(err.into()),
    }
}

fn init_tracing() {
    let subscriber = FmtSubscriber::builder()
        .with_max_level(Level::INFO)
        .with_target(false)
        .finish();
    let _ = tracing::subscriber::set_global_default(subscriber);
}

async fn shutdown_signal() {
    let ctrl_c = async {
        signal::ctrl_c()
            .await
            .expect("failed to install CTRL+C handler");
    };

    #[cfg(unix)]
    let terminate = async {
        signal::unix::signal(signal::unix::SignalKind::terminate())
            .expect("failed to install signal handler")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => {},
        _ = terminate => {},
    }
}

async fn healthz() -> &'static str {
    "ok"
}
```

### 📄 crates/indexd/src/main.rs

**Größe:** 180 B | **md5:** `5ea9039b1f3e051ead1655fd74517224`

```rust
//! Minimal HTTP server stub for the semantic index daemon (indexd).

use indexd::api;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    indexd::run(api::router).await
}
```

### 📄 crates/indexd/src/persist.rs

**Größe:** 5 KB | **md5:** `7842e8b41a11bb96041b1562ba3d488f`

```rust
use std::env;
use std::fs::{self, File};
use std::io::{BufRead, BufReader, BufWriter, Write};
use std::path::{Path, PathBuf};
use std::sync::Arc;

use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio::task;
use tracing::{info, warn};

use crate::{key::split_chunk_key, AppState};

const ENV_DB_PATH: &str = "INDEXD_DB_PATH";

#[derive(Debug, Serialize, Deserialize)]
struct RowOwned {
    namespace: String,
    doc_id: String,
    chunk_id: String,
    embedding: Vec<f32>,
    meta: Value,
}

pub async fn maybe_load_from_env(state: &Arc<AppState>) -> anyhow::Result<()> {
    let Some(path) = env::var_os(ENV_DB_PATH).map(PathBuf::from) else {
        return Ok(());
    };

    if !path.exists() {
        return Ok(());
    }

    let path_clone = path.clone();
    let items = task::spawn_blocking(move || read_jsonl(&path_clone)).await??;

    let mut store = state.store.write().await;
    let mut dims: Option<usize> = store.dims;
    let mut skipped = 0usize;

    for row in items {
        if let Some(expected) = dims {
            if expected != row.embedding.len() {
                warn!(
                    chunk_id = %row.chunk_id,
                    "skip row with mismatched dims: expected {expected}, got {}",
                    row.embedding.len()
                );
                skipped += 1;
                continue;
            }
        } else {
            dims = Some(row.embedding.len());
        }

        let RowOwned {
            namespace,
            doc_id,
            chunk_id,
            embedding,
            meta,
        } = row;

        if let Err(err) = store.upsert(&namespace, &doc_id, &chunk_id, embedding, meta) {
            warn!(chunk_id = %chunk_id, error = %err, "failed to upsert row from persistence");
            skipped += 1;
        }
    }

    info!(
        path = %path.display(),
        count = store.items.len(),
        skipped,
        "loaded vector store"
    );
    Ok(())
}

pub async fn maybe_save_from_env(state: &Arc<AppState>) -> anyhow::Result<()> {
    let Some(path) = env::var_os(ENV_DB_PATH).map(PathBuf::from) else {
        return Ok(());
    };

    let store = state.store.read().await;
    let mut rows = Vec::with_capacity(store.items.len());

    for ((namespace, key), (embedding, meta)) in store.items.iter() {
        let (doc_id, chunk_id) = split_chunk_key(key);
        rows.push(RowOwned {
            namespace: namespace.clone(),
            doc_id,
            chunk_id,
            embedding: embedding.clone(),
            meta: meta.clone(),
        });
    }

    let row_count = rows.len();
    let path_clone = path.clone();
    task::spawn_blocking(move || write_jsonl_atomic(&path_clone, &rows)).await??;

    info!(path = %path.display(), count = row_count, "saved vector store");
    Ok(())
}

fn read_jsonl(path: &Path) -> anyhow::Result<Vec<RowOwned>> {
    let file = File::open(path)?;
    let reader = BufReader::new(file);
    let mut rows = Vec::new();

    for line in reader.lines() {
        let line = line?;
        if line.trim().is_empty() {
            continue;
        }

        let row: RowOwned = serde_json::from_str(&line)?;
        rows.push(row);
    }

    Ok(rows)
}

fn write_jsonl_atomic(path: &Path, rows: &[RowOwned]) -> anyhow::Result<()> {
    if let Some(dir) = path.parent() {
        fs::create_dir_all(dir)?;
    }

    let tmp = path.with_extension("tmp");
    {
        let file = File::create(&tmp)?;
        let mut writer = BufWriter::new(file);

        for row in rows {

<<TRUNCATED: max_file_lines=800>>
```

### 📄 merges/semantAH_merge_2510262237__crates_indexd_tests.md

**Größe:** 13 KB | **md5:** `814d7c55f086b0428ca8500a39e19c9b`

```markdown
### 📄 crates/indexd/tests/e2e_http.rs

**Größe:** 2 KB | **md5:** `81ed8662b1cf7dd7775b3e74c9916702`

```rust
use std::net::SocketAddr;
use std::sync::Arc;

use axum::Router;
use indexd::{api, AppState};
use serde_json::json;
use tokio::net::TcpListener;

#[tokio::test]
async fn upsert_and_search_over_http() {
    // --- start server on a random local port
    let state = Arc::new(AppState::new());
    let app: Router = api::router(state);

    let listener = TcpListener::bind(("127.0.0.1", 0)).await.unwrap();
    let addr: SocketAddr = listener.local_addr().unwrap();

    let server = tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });

    let base = format!("http://{}", addr);
    let client = reqwest::Client::new();

    // --- healthz
    let health = client
        .get(format!("{base}/healthz"))
        .send()
        .await
        .expect("healthz request failed");
    assert!(health.status().is_success());
    assert_eq!(health.text().await.unwrap(), "ok");

    // --- upsert
    let upsert_payload = json!({
        "doc_id": "d1",
        "namespace": "ns",
        "chunks": [{
            "id": "c1",
            "text": "hello world",
            "meta": { "embedding": [1.0, 0.0], "snippet": "hello world" }
        }]
    });

    let upsert_res = client
        .post(format!("{base}/index/upsert"))
        .json(&upsert_payload)
        .send()
        .await
        .expect("upsert request failed");
    assert!(upsert_res.status().is_success());
    let upsert_json: serde_json::Value = upsert_res.json().await.unwrap();
    assert_eq!(upsert_json["status"], "accepted");
    assert_eq!(upsert_json["chunks"], 1);

    // --- search with explicit embedding
    let search_payload = json!({
        "query": "hello",
        "k": 5,
        "namespace": "ns",
        "embedding": [1.0, 0.0]
    });

    let search_res = client
        .post(format!("{base}/index/search"))
        .json(&search_payload)
        .send()
        .await
        .expect("search request failed");
    assert!(search_res.status().is_success());
    let search_json: serde_json::Value = search_res.json().await.unwrap();
    let results = search_json["results"].as_array().unwrap();
    assert_eq!(results.len(), 1);
    assert_eq!(results[0]["doc_id"], "d1");
    assert_eq!(results[0]["chunk_id"], "c1");
    assert!(results[0]["score"].as_f64().unwrap() > 0.0);

    // --- stop server
    server.abort();
}
```

### 📄 crates/indexd/tests/healthz.rs

**Größe:** 608 B | **md5:** `11486604bd2275696876d40b80e646e9`

```rust
use std::sync::Arc;

use axum::{
    body::{to_bytes, Body},
    http::{Request, StatusCode},
};
use tower::ServiceExt;

#[tokio::test]
async fn healthz_returns_ok() {
    let app = indexd::router(Arc::new(indexd::AppState::new()));

    let response = app
        .oneshot(
            Request::builder()
                .uri("/healthz")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);

    let body = to_bytes(response.into_body(), 1024).await.unwrap();
    assert_eq!(body.as_ref(), b"ok");
}
```

### 📄 crates/indexd/tests/search.rs

**Größe:** 9 KB | **md5:** `a61256b507e0f17cb72e820dd7a6de97`

```rust
use std::sync::Arc;

use anyhow::Result as AnyResult;
use async_trait::async_trait;
use axum::{body::to_bytes, body::Body, http::Request};
use embeddings::Embedder;
use indexd::{api, AppState};
use serde_json::json;
use tower::ServiceExt;

struct StaticEmbedder {
    vector: Vec<f32>,
}

#[async_trait]
impl Embedder for StaticEmbedder {
    async fn embed(&self, texts: &[String]) -> AnyResult<Vec<Vec<f32>>> {
        Ok(texts.iter().map(|_| self.vector.clone()).collect())
    }

    fn dim(&self) -> usize {
        self.vector.len()
    }

    fn id(&self) -> &'static str {
        "static"
    }
}

#[tokio::test]
async fn upsert_then_search_with_query_meta_embedding_returns_hit() {
    let state = Arc::new(AppState::new());
    let app = api::router(state.clone());

    let upsert_payload = json!({
        "doc_id": "d1",
        "namespace": "ns",
        "chunks": [{
            "id": "c1",
            "text": "hello",
            "meta": {"embedding": [1.0, 0.0], "snippet": "hello"}
        }]
    });
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/index/upsert")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(upsert_payload.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    let search_payload = json!({
        "query": {
            "text": "hello",
            "meta": {"embedding": [1.0, 0.0]}
        },
        "k": 5,
        "namespace": "ns"
    });
    let response = app
        .oneshot(
            Request::builder()
                .uri("/index/search")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(search_payload.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    let body = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();

    let results = json["results"]
        .as_array()
        .expect("results should be an array");
    assert_eq!(results.len(), 1);
    assert_eq!(results[0]["doc_id"], "d1");
    assert_eq!(results[0]["chunk_id"], "c1");
}

#[tokio::test]
async fn upsert_then_search_with_top_level_embedding_returns_hit() {
    let state = Arc::new(AppState::new());
    let app = api::router(state.clone());

    let upsert_payload = json!({
        "doc_id": "d1",
        "namespace": "ns",
        "chunks": [{
            "id": "c1",
            "text": "hello",
            "meta": {"embedding": [1.0, 0.0], "snippet": "hello"}
        }]
    });
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/index/upsert")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(upsert_payload.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    let search_payload = json!({
        "query": "hello",
        "k": 5,
        "namespace": "ns",
        "embedding": [1.0, 0.0]
    });
    let response = app
        .oneshot(
            Request::builder()
                .uri("/index/search")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(search_payload.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    let body = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();

    let results = json["results"]
        .as_array()
        .expect("results should be an array");
    assert_eq!(results.len(), 1);
    assert_eq!(results[0]["doc_id"], "d1");
    assert_eq!(results[0]["chunk_id"], "c1");
}

#[tokio::test]
async fn upsert_then_search_with_legacy_meta_embedding_returns_hit() {
    let state = Arc::new(AppState::new());
    let app = api::router(state.clone());

    let upsert_payload = json!({
        "doc_id": "d1",
        "namespace": "ns",
        "chunks": [{
            "id": "c1",
            "text": "hello",
            "meta": {"embedding": [1.0, 0.0], "snippet": "hello"}
        }]
    });
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/index/upsert")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(upsert_payload.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    let search_payload = json!({
        "query": "hello",
        "k": 5,
        "namespace": "ns",
        "meta": {"embedding": [1.0, 0.0]}
    });
    let response = app
        .oneshot(
            Request::builder()
                .uri("/index/search")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(search_payload.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    let body = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();

    let results = json["results"]
        .as_array()
        .expect("results should be an array");
    assert_eq!(results.len(), 1);
    assert_eq!(results[0]["doc_id"], "d1");
    assert_eq!(results[0]["chunk_id"], "c1");
}

#[tokio::test]
async fn query_meta_embedding_overrides_other_locations() {
    let state = Arc::new(AppState::new());
    let app = api::router(state.clone());

    let upsert_payload = json!({
        "doc_id": "d1",
        "namespace": "ns",
        "chunks": [
            {"id": "c1", "text": "x", "meta": {"embedding": [1.0, 0.0], "snippet": "x"}},
            {"id": "c2", "text": "y", "meta": {"embedding": [0.0, 1.0], "snippet": "y"}}
        ]
    });
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/index/upsert")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(upsert_payload.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    let search_payload = json!({
        "query": {
            "text": "irrelevant",
            "meta": {"embedding": [0.0, 1.0]}
        },
        "namespace": "ns",
        "k": 1,
        "embedding": [1.0, 0.0],
        "meta": {"embedding": [1.0, 0.0]}
    });

    let response = app
        .oneshot(
            Request::builder()
                .uri("/index/search")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(search_payload.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    let body = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();

    let results = json["results"]
        .as_array()
        .expect("results should be an array");
    assert_eq!(results.len(), 1);
    assert_eq!(results[0]["doc_id"], "d1");
    assert_eq!(results[0]["chunk_id"], "c2");
}

#[tokio::test]
async fn search_generates_embedding_from_query_text_when_embedder_configured() {
    let embedder: Arc<dyn Embedder> = Arc::new(StaticEmbedder {
        vector: vec![1.0, 0.0],
    });
    let state = Arc::new(AppState::with_embedder(Some(embedder)));
    let app = api::router(state.clone());

    let upsert_payload = json!({
        "doc_id": "d1",
        "namespace": "ns",
        "chunks": [{
            "id": "c1",
            "text": "hello",
            "meta": {"embedding": [1.0, 0.0], "snippet": "hello"}
        }]
    });
    let response = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/index/upsert")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(upsert_payload.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    let search_payload = json!({
        "query": "hello",
        "k": 5,
        "namespace": "ns"
    });
    let response = app
        .oneshot(
            Request::builder()
                .uri("/index/search")
                .method("POST")
                .header("content-type", "application/json")
                .body(Body::from(search_payload.to_string()))
                .unwrap(),
        )
        .await
        .unwrap();
    assert!(response.status().is_success());

    let body = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();

    let results = json["results"]
        .as_array()
        .expect("results should be an array");
    assert_eq!(results.len(), 1);
    assert_eq!(results[0]["doc_id"], "d1");
    assert_eq!(results[0]["chunk_id"], "c1");
}
```
```

### 📄 merges/semantAH_merge_2510262237__docs.md

**Größe:** 86 KB | **md5:** `7e8a5afedbb2afe6401a18fd5cd25511`

```markdown
### 📄 docs/README.md

**Größe:** 553 B | **md5:** `fa58fb3e5116de80f1b82dea74711231`

```markdown
# Documentation

This directory contains all the documentation for semantAH.

## Table of Contents

-   **[Quickstart](quickstart.md):** A step-by-step guide to getting started with semantAH.
-   **[Configuration Reference](config-reference.md):** A detailed reference for the `semantah.yml` configuration file.
-   **[API Reference](indexd-api.md):** The HTTP API reference for the `indexd` service.
-   **[Blueprint](blueprint.md):** The complete conceptual blueprint for semantAH.
-   **[Roadmap](roadmap.md):** The development roadmap and progress.
```

### 📄 docs/blueprint.md

**Größe:** 11 KB | **md5:** `b1fa5ee0047bbe711860d0848e1be72d`

```markdown
# Vault-Gewebe: Finale Blaupause

Diese Datei fasst die komplette Architektur für das semantische Vault-Gewebe zusammen. Sie kombiniert den semantischen Index, den Wissensgraphen, Obsidian-Automatismen sowie Qualitäts- und Review-Schleifen. Alle Schritte sind lokal reproduzierbar und werden in `.gewebe/` versioniert.

---

## 0. Systemordner & Konventionen

```
.gewebe/
  config.yml           # Parameter (Modelle, Cutoffs, Policies)
  embeddings.parquet   # Chunks + Vektoren
  nodes.jsonl          # Graph-Knoten
  edges.jsonl          # Graph-Kanten
  clusters.json        # Cluster & Label
  taxonomy/
    synonyms.yml
    entities.yml
  reports/
    semnet-YYYYMMDD.md
  meta.json            # Provenienz (Modell, Parameter, Hashes)
```

**Frontmatter pro Datei**

```yaml
id: 2025-VAULT-####   # stabiler Schlüssel
title: ...
topics: [HausKI, Weltgewebe]
persons: [Verena]
places: [Hamburg]
projects: [wgx, hauski]
aliases: [HK, WG]
relations_lock: false
```

---

## 1. Indexing & Embeddings

- Crawler: iteriert Markdown & Canvas (ignoriert `.gewebe/`, `.obsidian/`).
- Chunking: 200–300 Tokens, Overlap 40–60, Paragraph/Block.
- Modelle: `all-MiniLM-L6-v2` oder `intfloat/e5-base` (GPU-fähig via PyTorch/CUDA).
- Output: `embeddings.parquet` (id, path, chunk_id, text, embedding).

---

## 2. Schlagwort- & Entitätsextraktion

- Keyphrase: YAKE/RAKE lokal → optional mit LLM verfeinern.
- NER: spaCy DE-Modell → Personen, Orte, Projekte.
- Taxonomie in `.gewebe/taxonomy/synonyms.yml`:

```yaml
topics:
  hauski: [haus-ki, hk]
persons:
  verena: [v.]
```

- Normalisierung: Tokens bei Indexlauf auf Normformen mappen → ins Frontmatter schreiben.

---

## 3. Clusterbildung

- Verfahren: HDBSCAN (robust) + UMAP (2D-Projektion für Visualisierung).
- Ergebnis: `clusters.json` mit IDs, Label, Mitgliedern und Zentroiden.
- Orphan Detection: Notizen ohne Cluster → separate Liste.

---

## 4. Semantischer Wissensgraph

**Nodes (`nodes.jsonl`)**

```json
{"id":"md:gfk.md","type":"file","title":"GFK","topics":["gfk"],"cluster":7}
{"id":"topic:Gewaltfreie Kommunikation","type":"topic"}
{"id":"person:Verena","type":"person"}
```

**Edges (`edges.jsonl`)**

```json
{"src":"md:gfk.md","rel":"about","dst":"topic:Gewaltfreie Kommunikation","weight":0.92,"why":["shared:keyphrase:GFK","same:cluster"]}
{"src":"md:verena.md","rel":"similar","dst":"md:tatjana.md","weight":0.81,"why":["cluster:7","quote:'…'"]}
```

Das Feld `why` speichert die Top-Rationales (Keyphrases, Cluster, Anker-Sätze) und ermöglicht Explainability.

---

## 5. Verlinkung in Obsidian

- Related-Blöcke (idempotent, autogeneriert):

```
<!-- related:auto:start -->
## Related
- [[Tatjana]] — (0.81; Cluster 7, GFK)
- [[Lebenslagen]] — (0.78; Resonanz)
<!-- related:auto:end -->
```

- MOCs (`_moc/topic.md`): Beschreibung, Dataview-Tabelle (`topics:topic`), Mini-Canvas-Link.
- Canvas-Integration: Knoten = Notizen/Topics/Persons, Kanten = Similar/About/Mentions, Legende-Knoten nach Canvas-Richtlinie.

---

## 6. Automatisierung

- `wgx`-Recipes:

```yaml
index:
    python3 tools/build_index.py
graph:
    python3 tools/build_graph.py
related:
    python3 tools/update_related.py
all: index graph related
```

- systemd `--user` Timer oder cron: nightly `make all`.
- Git-Hook (pre-commit): delta-Index → Related aktualisieren.

---

## 7. Qualitative Validierung

- Reports (`reports/semnet-YYYYMMDD.md`): neue Kanten < 0.75 („Review required“), Orphans, Cluster > N Notizen ohne MOC.
- Review-Workflow: `accepted_edges` / `rejected_edges` im Frontmatter; Skripte ignorieren `rejected` → Feedback fließt zurück.

---

## 8. Policies & Score-Regeln

```
score = cosine + boosts
+0.05 wenn gleicher Cluster
+0.03 je shared keyphrase (max +0.09)
+0.04 wenn Canvas-Hop ≤ 2
+0.02 wenn Datei jung (<30 Tage)
```

Autolink-Gate:

- Score ≥ 0.82 **und** (≥ 2 Keyphrases **oder** Canvas-Hop ≤ 2 **oder** shared Project).
- Cutoffs: ≥ 0.82 Auto-Link, 0.70–0.81 Vorschlag, < 0.70 ignorieren.

---

## 9. Erweiterungen (Kernideen)

- Duplicates Report: Cosine ≥ 0.97 → Merge-Vorschlag.
- Topic Drift: Clusterwechsel flaggen.
- Session-Boost: aktuell bearbeitete Dateien → Score +0.02.
- Explain Command: Popover „Warum ist dieser Link da?“ (zeigt `why`-Feld).
- Locks: `relations_lock: true` → keine Auto-Edits.
- A/B-Cutoffs: zwei Profile testen, Review-Feedback einspeisen.

---

## 10. Provenienz & Reproduzierbarkeit

`.gewebe/meta.json` speichert:

```json
{
  "model": "all-MiniLM-L6-v2",
  "chunk_size": 200,
  "cutoffs": {"auto": 0.82, "suggest": 0.70},
  "run": "2025-10-02T11:40",
  "commit": "abc123"
}
```

---

## 11. Technische Bausteine

### Tools / Skripte

- `tools/build_index.py`: Scan + Embeddings.
- `tools/build_graph.py`: Nodes/Edges/Cluster.
- `tools/update_related.py`: Related-Blöcke injizieren.
- `tools/report.py`: QA-Reports.
- optional `tools/canvas_export.py`: Cluster → Canvas.

### Dreistufiger Zyklus

1. Index (Embeddings, Cluster, Taxonomie).
2. Graph (Nodes/Edges mit Rationales).
3. Update (Related, MOCs, Reports, Canvas).

---

## 12. Minimal lauffähige Suite

Eine robuste, offline-fähige Minimalversion liefert unmittelbar Embeddings, Similarities, Graph (Nodes/Edges), Related-Blöcke und Reports.

### Dateibaum

```
<Vault-Root>/
  .gewebe/
    config.yml
    taxonomy/
      synonyms.yml
      entities.yml
    reports/
  tools/
    build_index.py
    build_graph.py
    update_related.py
  Makefile
```

### Python-Abhängigkeiten

```
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install pandas numpy pyarrow pyyaml \
  sentence_transformers scikit-learn networkx rich
```

Standardmodell: `sentence-transformers/all-MiniLM-L6-v2`. GPU nutzt Torch automatisch, falls vorhanden.

### `.gewebe/config.yml`

```yaml
model: sentence-transformers/all-MiniLM-L6-v2
chunk:
  target_chars: 1200
  min_chars: 300
  overlap_chars: 200
paths:
  exclude_dirs: [".gewebe", ".obsidian", "_site", "node_modules"]
  include_ext: [".md"]
related:
  k: 8
  auto_cutoff: 0.82
  suggest_cutoff: 0.70
boosts:
  same_topic: 0.03
  same_project: 0.03
  recent_days: 30
  recent_bonus: 0.02
  same_folder: 0.02
render:
  related_heading: "## Related"
  markers:
    start: "<!-- related:auto:start -->"
    end:   "<!-- related:auto:end -->"
```

### Skripte (`tools/*.py`)

Die Skripte implementieren:

- Markdown-Scan, Frontmatter-Parsing und Chunking.
- Embedding-Berechnung mit SentenceTransformers.
- Vektorzentroide pro Datei + Cosine-Similarity.
- Score-Boosts basierend auf Topics, Projekten, Ordnern, Recency.
- Schreiben von `nodes.jsonl`, `edges.jsonl` und Reports.
- Injection idempotenter Related-Blöcke in Markdown.

(Vollständige Implementierungen befinden sich in `tools/` im Repo und sind auf GPU/CPU lauffähig.)

### Makefile

```
VENV=.venv
PY=$(VENV)/bin/python

.PHONY: venv index graph related all clean

venv: $(VENV)/.deps_installed

$(VENV)/.deps_installed: 
	@test -d $(VENV) || python3 -m venv $(VENV)
	@$(PY) -m pip install --upgrade pip
	@$(PY) -m pip install pandas numpy pyarrow pyyaml sentence_transformers scikit-learn networkx rich
	@touch $(VENV)/.deps_installed
index: venv
@$(PY) tools/build_index.py

graph: venv
@$(PY) tools/build_graph.py

related: venv
@$(PY) tools/update_related.py

all: index graph related

clean:
@rm -f .gewebe/embeddings.parquet
@rm -f .gewebe/nodes.jsonl .gewebe/edges.jsonl
```

### systemd (User) Timer

`~/.config/systemd/user/vault-gewebe.service`

```
[Unit]
Description=Vault-Gewebe nightly build (index -> graph -> related)
After=default.target

[Service]
Type=oneshot
WorkingDirectory=%h/path/to/your/vault
ExecStart=make all
```

`~/.config/systemd/user/vault-gewebe.timer`

```
[Unit]
Description=Run Vault-Gewebe every night

[Timer]
OnCalendar=*-*-* 03:10:00
Persistent=true

[Install]
WantedBy=timers.target
```

Aktivieren:

```
systemctl --user daemon-reload
systemctl --user enable --now vault-gewebe.timer
systemctl --user list-timers | grep vault-gewebe
```

### Erstlauf

```
make venv
make all
```

Ergebnisdateien liegen unter `.gewebe/…`. In Obsidian erscheint der Related-Block am Ende der Note.

---

## 13. HausKI-Integration (Überblick)

Für HausKI entsteht ein neuer Dienstverbund:

1. `crates/embeddings`: Embedder-Trait + Provider (lokal via Ollama, optional Cloud über AllowlistedClient und Safe-Mode-Policies).
2. `crates/indexd`: HTTP-Service (`/index/upsert`, `/index/search`, `/index/delete`), HNSW-Vektorindex, Persistenz (`~/.local/state/hauski/index/obsidian`).
3. Obsidian-Plugin (Thin Client): chunked Upserts & Searches über HausKI-Gateway.
4. Config-Erweiterung (`configs/hauski.yml`): Index-Pfad, Embedder-Optionen, Namespace-Policies.

Siehe `docs/hauski.md` für eine ausführliche Einbindung.

---

## 14. Erweiterte Qualitäts- & Komfortfeatures

1. **Begründete Kanten** – `edges.jsonl` enthält `why`-Feld mit Keyphrases, Cluster, Quotes.
2. **Near-Duplicate-Erkennung** – Cosine ≥ 0.97 → Merge-Report, Canonical-Markierung.
3. **Zeit-Boost** – +0.05 für Notizen < 30 Tage, Decay für ältere Inhalte.
4. **Ordner-/Namespace-Policies** – z. B. `/archive/` nur eingehende Links, `/ideen/` liberalere Cutoffs.
5. **Feedback-Lernen** – `accepted_edges`/`rejected_edges` beeinflussen Cutoffs.
6. **Canvas-Hop-Boost** – Pfadlänge ≤ 2 innerhalb von Canvas erhöht Score um 0.03–0.07.
7. **Topic-Drift-Wächter** – signalisiert Clusterwechsel.
8. **Explainable Related-Blöcke** – Scores & Top-Begründungen in Markdown.
9. **Session-Kontext** – aktuell geöffnete Dateien geben +0.02 Boost.
10. **Provenienz** – `meta.json` mit Modell, Chunking, Cutoffs, Hashes.
11. **Mehrsprach-Robustheit** – Synonym-/Stemming-Maps für DE/EN.
12. **Autolink-Quality-Gate** – Score ≥ 0.82 + (≥2 Keyphrases oder Canvas-Hop ≤ 2 oder shared Project).
13. **Explain-this-link Command** – Popover mit Rationales im Obsidian-Plugin.
14. **MOC-Qualitätsreport** – Deckungsgrade, verwaiste Knoten, Unter-MOC-Vorschläge.
15. **Transklusions-Vorschläge** – Absatzweise `![[note#^block]]` bei hoher Chunk-Ähnlichkeit.
16. **Manual Lock** – `relations_lock: true` verhindert Auto-Edits.
17. **A/B-Tuning** – zwei Cutoff-Profile testen, Feedback auswerten.
18. **Cross-Vault-Brücke** – Read-Only Namespace `ext:*` für externe Vaults.
19. **Orphans-First-Routine** – wöchentliche Fokussierung auf unverlinkte Notizen.
20. **Explainable Deletes** – Reports dokumentieren entfernte Kanten mit Ursache.

---

## 15. Unsicherheiten & Anpassbarkeit

- Schwellenwerte & Chunking müssen empirisch justiert werden.
- Canvas-Hop-Berechnungen hängen vom JSON-Layout ab.
- Modellwahl beeinflusst Qualität und Performance.
- Die Pipeline ist modular, Reports + Feedback-Loops ermöglichen schnelle Iteration.

---

## 16. Verdichtete Essenz

- Drei Skripte, ein Makefile, ein Timer → Index → Graph → Related.
- HausKI liefert den skalierbaren Dienst (`indexd`) + Obsidian-Adapter.
- Qualität durch erklärbare Kanten, Review-Workflow, Reports, Policies.
- Lokal, reproduzierbar, versionierbar – dein Vault wird zum lebenden Semantiknetz.

---

> *Ironische Auslassung:* Deine Notizen sind jetzt kein stilles Archiv mehr – sie bilden ein Klatsch-Netzwerk, das genau protokolliert, wer mit wem was zu tun hat. Nur: Sie lügen nicht.
```

### 📄 docs/config-reference.md

**Größe:** 3 KB | **md5:** `8b0c2fc76102fb737e07dcf44cc46eab`

```markdown
# Konfigurationsreferenz (`semantah.yml`)

`semantah.yml` dient als zentrale Drehscheibe für die Pipeline-Konfiguration. Die Datei ist aktuell ein **Platzhalter** – die angebundenen Skripte und Dienste nutzen die Konfiguration noch nicht, sondern arbeiten mit fest kodierten Pfaden und Standardwerten.

Die folgende Tabelle dokumentiert das Zielschema und den aktuellen Implementierungsstatus.

| Feld | Typ | Beschreibung | Standard | Status |
| --- | --- | --- | --- | --- |
| `vault_path` | Pfad | Stamm des Obsidian-Vaults, aus dem Markdown-Dateien gelesen werden. | – (Pflichtfeld) | Stub (Skripte verwenden derzeit Beispielpfade) |
| `out_dir` | Pfad | Zielverzeichnis für Artefakte wie Embeddings, Graph und Reports. | `.gewebe` | Stub (Skripte schreiben hartkodiert nach `.gewebe/`) |
| `embedder.provider` | String | Kennung des Embedding-Providers (`ollama`, `openai`, …). | `ollama` | Stub |
| `embedder.model` | String | Modellname/Identifier, der an den Provider übergeben wird. | `nomic-embed-text` | Stub |
| `embedder.base_url` | URL | Optional: überschreibt die Basis-URL für lokale Provider (z. B. `http://localhost:11434`). | `http://localhost:11434` | Stub |
| `index.top_k` | Integer | Anzahl Treffer, die bei Suchen (`/index/search`) zurückgegeben werden. | `20` | Stub (HTTP-Stub verwendet Payload `k`) |
| `index.persist_path` | Pfad | Ablageort für den persistenten Index. | – | geplant |
| `graph.cutoffs.min_cooccur` | Integer | Minimale Co-Vorkommnisse zweier Notizen, um eine Kante zu erzeugen. | `2` | Stub |
| `graph.cutoffs.min_weight` | Float | Mindestgewicht für gewichtete Kanten. | `0.15` | Stub |
| `graph.cutoffs.min_similarity` | Float | Alternative Metrik, falls Similarity-Schwelle verwendet wird. | deaktiviert | Stub |
| `related.write_back` | Bool | Schreibt Related-Blöcke in Markdown-Dateien. | `false` | Stub (Skript akzeptiert später diesen Schalter) |
| `related.block_heading` | String | Überschrift des Related-Blocks. | `Related` | geplant |
| `telemetry.enabled` | Bool | Aktiviert OpenTelemetry-Export für `indexd` und Pipeline-Skripte. | `false` | geplant |
| `telemetry.endpoint` | URL | Ziel-Endpunkt für OTLP-Export (`http://localhost:4317`). | `http://localhost:4317` | geplant |
| `alerts.latency.index_topk20_ms` | Integer | Schwellwert in Millisekunden für Benachrichtigungen aus der Observability-Stack. | `60` | geplant |

## Beispielkonfiguration
```yaml
vault_path: /home/user/Vaults/knowledge
out_dir: .gewebe
embedder:
  provider: ollama
  model: nomic-embed-text
  base_url: http://localhost:11434
index:
  top_k: 20
  persist_path: ~/.local/state/semantah/index
graph:
  cutoffs:
    min_cooccur: 2
    min_weight: 0.15
related:
  write_back: true
  block_heading: "Ähnliche Notizen"
telemetry:
  enabled: false
alerts:
  latency:
    index_topk20_ms: 75
```

Nutze `examples/semantah.example.yml` als Ausgangspunkt und erweitere die Datei entsprechend deiner Umgebung. Pflichtfelder sollten im CI/Deployment validiert werden, bevor die Pipeline gestartet wird.
```

### 📄 docs/embeddings.md

**Größe:** 3 KB | **md5:** `21d54c5552a700515e213ccb38d1a500`

```markdown
# Embeddings

Die Embedding-Schicht übersetzt Notiz-Chunks in normalisierte Vektoren, die vom Indexdienst
(`indexd`) und den Graph-Builders weiterverarbeitet werden. Dieses Dokument fasst die
Derivation (Provider & Dimension), die Normalisierung und die Persistenzpfade zusammen.

## Provider & Konfiguration

| Provider                | Transport                                   | Konfiguration                       | Status |
|------------------------|----------------------------------------------|-------------------------------------|--------|
| `ollama` (Default)     | HTTP gegen einen lokalen Ollama-Dienst (`/api/embeddings`). | `semantah.yml` → `embedder.provider: ollama`, `embedder.model: nomic-embed-text` (oder anderes Ollama-Embedding-Modell). | Implementiert |
| `openai` (geplant)     | HTTPS gegen das OpenAI Embeddings-API.       | `semantah.yml` → `embedder.provider: openai`, plus API-Key via Environment. | Konzeptphase |

- Weitere Provider werden über das `crates/embeddings`-Crate abstrahiert; jeder Provider
  implementiert denselben `Embedder`-Trait (siehe `docs/semantAH brainstorm.md`).
- Die Konfiguration befindet sich zentral in `semantah.yml`. Für den lokalen Betrieb genügt
  es, den Ollama-Endpunkt laufen zu lassen und ggf. das Modell anzupassen.

```yaml
embedder:
  provider: ollama
  model: nomic-embed-text
```

## Dimensionen & Normalisierung

- Die Dimensionen der Vektoren richten sich nach dem gewählten Modell. Das
  Standardmodell `nomic-embed-text` liefert heute typischerweise
  768-dimensionale Vektoren; bei einem Modellwechsel passt sich die Dimension
  entsprechend an.
- Vor der Persistenz erfolgt eine L2-Normalisierung, damit der Index eine
  Cosine-Similarity-Suche direkt auf den gespeicherten Vektoren durchführen kann. Die
  aktuelle Python-Pipeline ruft `sentence-transformers` mit
  `normalize_embeddings=True` auf und erzeugt so Einheitsvektoren (siehe
  Abschnitt „Embedding-Pipeline" in `docs/semantAH.md`).

## Persistenzpfade

- Embeddings werden als Parquet-Datei unter `.gewebe/embeddings.parquet`
  abgelegt. Die Datei enthält pro Zeile `id`, `path`, `chunk_id`, `text` und den
  zugehörigen Vektor (siehe Abschnitt „Dateiaufbau“ in `docs/semantAH.md`).
- Der Pfad ist über `semantah.yml → out_dir` konfigurierbar. Standard ist `.gewebe` im
  Projektverzeichnis (`semantah.yml`, Abschnitt „Allgemeine Einstellungen“).
- Pro Namespace kann eine separate Datei geschrieben werden (z. B. `.gewebe/vault/embeddings.parquet`).
  Die geplanten Rust-Dienste spiegeln diese Struktur wider, indem sie pro Namespace eigene
  Buckets anlegen (siehe `docs/hauski.md`, Abschnitt „Persistenz“).

## Lifecycle

1. Die Obsidian-Adapter zerlegen Notizen in Chunks.
2. Der Embeddings-Dienst fragt den konfigurierten Provider an und erhält die Rohvektoren.
3. Die Rohvektoren werden normalisiert und in `.gewebe/…/embeddings.parquet` persistiert.
4. `indexd` liest dieselben Dateien ein bzw. erhält Embeddings über die API und legt sie
   namespacesepariert ab (siehe `docs/semantAH.md`, Abschnitt „Indexdienst“ sowie
   `docs/indexd-api.md`, Abschnitt „Embeddings-Endpunkte“).

Damit ist nachvollziehbar, welcher Provider genutzt wird, welche Vektorlänge entsteht und wo
die Daten auf der Platte liegen.
```

### 📄 docs/hauski.md

**Größe:** 5 KB | **md5:** `9b9d21594d5468bdaea32737a8f4b7f5`

```markdown
# HausKI-Integration

HausKI bleibt das lokale Orchestrierungs-Gateway. semantAH ergänzt es als semantische Gedächtnis-Schicht. Dieser Leitfaden beschreibt, wie die neuen Komponenten (`indexd`, `embeddings`, Obsidian-Adapter) eingebunden werden und welche Policies greifen.

---

## Architekturüberblick

1. **`crates/embeddings`** – stellt den `Embedder`-Trait bereit und kapselt Provider:
   - `Ollama` (lokal, offline) ruft `http://127.0.0.1:11434/api/embeddings` auf.
   - `CloudEmbedder` (optional) nutzt HausKIs AllowlistedClient. Aktiv nur, wenn `safe_mode=false` und der Zielhost in der Egress-Policy freigeschaltet ist.
2. **`crates/indexd`** – HTTP-Service mit Routen:
   - `POST /index/upsert` – nimmt Chunks + Metadaten entgegen und legt Vektoren im HNSW-Index ab.
   - `POST /index/delete` – entfernt Dokumente aus einem Namespace.
   - `POST /index/search` – Top-k-Suche mit Filtern (Tags, Projekte, Pfade).
   - Persistenz liegt unter `~/.local/state/hauski/index/<namespace>/`.
3. **Obsidian-Adapter (Thin Plugin)** – zerlegt Notizen und Canvas-Dateien, sendet Upserts an HausKI und ruft Suchergebnisse für „Related“/Command-Paletten ab.
4. **Policies & Observability** – bestehende Features (CORS, `/health`, `/metrics`, `safe_mode`, Latency-Budgets) gelten auch für `/index/*`.

---

## Workspace-Konfiguration

`Cargo.toml` (Workspace):

```toml
[workspace]
members = [
  "crates/core",
  "crates/cli",
  "crates/indexd",
  "crates/embeddings"
]
```

`crates/embeddings/src/lib.rs` definiert den Trait und z. B. `Ollama`:

```rust
#[async_trait::async_trait]
pub trait Embedder {
    async fn embed(&self, texts: &[String]) -> anyhow::Result<Vec<Vec<f32>>>;
    fn dim(&self) -> usize;
    fn id(&self) -> &'static str;
}
```

Implementierungen greifen auf `reqwest::Client` zurück. Cloud-Varianten müssen über HausKIs AllowlistedClient laufen, um Egress-Guards einzuhalten.

`crates/indexd` kapselt Embedder + Vektorstore (HNSW + Metadata-KV, z. B. `sled`). Der Router wird in `core::plugin_routes()` unter `/index` gemountet:

```rust
fn plugin_routes() -> Router<AppState> {
    let embedder = embeddings::Ollama::new("http://127.0.0.1:11434", "nomic-embed-text", 768);
    let store = indexd::store::hnsw(/* state_path */);
    Router::new().nest("/index", indexd::Indexd::new(embedder, store).router())
}
```

---

## HTTP-API

### Upsert

```http
POST /index/upsert
{
  "namespace": "obsidian",
  "doc_id": "notes/gfk.md",
  "chunks": [
    {"id": "notes/gfk.md#0", "text": "...", "meta": {"topics": ["gfk"], "frontmatter": {...}}}
  ]
}
```

### Delete

```http
POST /index/delete
{"namespace": "obsidian", "doc_id": "notes/gfk.md"}
```

### Search

```http
POST /index/search
{
  "namespace": "obsidian",
  "query": "empatische Kommunikation",
  "k": 10,
  "filters": {"topics": ["gfk"], "projects": ["wgx"]}
}
```

Antwort: Treffer mit Score, Dokument/Chunk-ID, Snippet, Rationales (`why`).

---

## Persistenz & Budgets

- Indexdaten leben im `index.path` aus der HausKI-Config (`~/.local/state/hauski/index`).
- HNSW-Index + Sled/SQLite halten Embeddings und Metadaten.
- Latency-Budgets: `limits.latency.index_topk20_ms` (Config) definiert das p95-Ziel. K6-Smoke nutzt diesen Wert als Assertion.
- Prometheus-Metriken für `/index/*` werden automatisch vom Core erfasst (`http_requests_total`, `http_request_duration_seconds`).

---

## Konfiguration (`configs/hauski.yml`)

```yaml
index:
  path: "$HOME/.local/state/hauski/index"
  provider:
    embedder: "ollama"
    model: "nomic-embed-text"
    url: "http://127.0.0.1:11434"
    dim: 768
  namespaces:
    obsidian:
      auto_cutoff: 0.82
      suggest_cutoff: 0.70
      policies:
        allow_autolink: true
        folder_overrides:
          archive:
            mode: incoming-only
plugins:
  enabled:
    - obsidian_index
```

`safe_mode: true` sperrt Cloud-Provider automatisch. Namespaces können weitere Regeln (z. B. strengere Cutoffs) erhalten.

---

## Obsidian-Plugin (Adapter)

- Hook auf `onSave` / `metadataCache.on("changed")`.
- Chunking (200–300 Tokens, 40 Overlap), Canvas-JSON-Knoten werden zusätzliche Chunks.
- Sendet `POST /index/upsert` mit Frontmatter/Tags/Canvas-Beziehungen im `meta`-Feld.
- Command „Semantisch ähnliche Notizen“ → `POST /index/search` und Anzeige der Ergebnisse.
- Optionaler Review-Dialog für Vorschläge (Accept/Reject → Frontmatter `accepted_edges` / `rejected_edges`).

---

## Automatisierung & Tests

- `wgx run index:obsidian` ruft der Reihe nach `build_index`, `build_graph`, `update_related` auf.
- systemd-Timer führt `make all` nightly aus (siehe `docs/blueprint.md`).
- CI/K6: Smoke-Test gegen `/index/search` mit Query-Stubs → prüft p95 < `limits.latency.index_topk20_ms`.

---

## Mehrwert

- Saubere Zuständigkeiten (UI vs. Dienste).
- Egress-kontrollierte Einbindung externer Provider.
- Explainable Scores via `why`-Feld.
- Reports & Policies sorgen für qualitätsgesicherte Auto-Links.

> *Ironische Auslassung:* HausKI bleibt der Türsteher – aber semantAH entscheidet, wer auf die VIP-Liste der Notizen kommt.
```

### 📄 docs/indexd-api.md

**Größe:** 4 KB | **md5:** `319336de97582acf29aca6dc4459dff6`

```markdown
# HTTP-API Referenz (`indexd`)

Der Dienst `crates/indexd` stellt einen JSON-basierten HTTP-API-Layer bereit. Die Routen werden über Axum exponiert und laufen standardmäßig auf `http://localhost:8080`.

## Authentifizierung
Lokale Entwicklungsumgebungen laufen ohne Authentifizierung. Für produktive Setups ist ein vorgelagerter Reverse-Proxy mit Auth/ACL vorgesehen.

## Endpunkte
### `POST /index/upsert`
- **Zweck:** Registriert oder aktualisiert Chunks eines Dokuments.
- **Body:**
  ```json
  {
    "doc_id": "note-42",
    "namespace": "vault",
    "chunks": [
      {
        "id": "note-42#0",
        "text": "Ein Abschnitt...",
        "meta": {
          "embedding": [0.12, 0.98],
          "source_path": "notes/example.md",
          "tags": ["project/infra"]
        }
      }
    ]
  }
  ```
- **Antwort:**
  ```json
  {
    "status": "accepted",
    "chunks": 1
  }
  ```
- **Fehler:** `400 Bad Request` falls `meta.embedding` fehlt oder unterschiedliche Dimensionalität festgestellt wird.

### `POST /index/delete`
- **Zweck:** Entfernt sämtliche Chunks eines Dokuments innerhalb eines Namespace.
- **Body:** `{ "doc_id": "note-42", "namespace": "vault" }`
- **Antwort:** `{ "status": "accepted" }`

### `POST /index/search`
- **Zweck:** Führt eine vektorbasierte Suche aus.
- **Body:**
  ```json
  {
    "query": {
      "text": "backup policy",
      "meta": {
        "embedding": [0.12, 0.98]
      }
    },
    "namespace": "vault",
    "k": 10,
    "filters": { "tags": ["policy"] }
  }
  ```
- **Antwort:**
  ```json
  {
    "results": [
      {
        "doc_id": "note-42",
        "chunk_id": "note-42#0",
        "score": 0.87,
        "snippet": "...",
        "rationale": ["Tag match: policy", "Vector cosine: 0.87"]
      }
    ]
  }
  ```

<<TRUNCATED: max_file_lines=800>>
```

### 📄 merges/semantAH_merge_2510262237__docs_adr.md

**Größe:** 511 B | **md5:** `d945ac1daf0b1e803e81c2423fc7fdad`

```markdown
### 📄 docs/adr/0001-semantics-contract.md

**Größe:** 382 B | **md5:** `cd35e79e053628ae631f3917415f6d61`

```markdown
# ADR-0001: Semantik-Contract
Status: accepted

Beschluss:
- semantAH liefert Nodes/Edges/Reports im JSON-Format gemäß `contracts/semantics/*.schema.json`.
- Weltgewebe konsumiert diese Artefakte read-only und setzt eigene Events oben drauf.

Konsequenzen:
- Änderungen sind semver-minor kompatibel (nur additive Felder).
- Breaking Changes nur per neue Schemas mit neuer Datei.
```
```

### 📄 merges/semantAH_merge_2510262237__docs_runbooks.md

**Größe:** 3 KB | **md5:** `72fa3726868e65f40c3c4f6b719c61dc`

```markdown
### 📄 docs/runbooks/semantics-intake.md

**Größe:** 3 KB | **md5:** `0680547c41d42e9045f0477863149f1c`

```markdown
# Runbook: Semantics Intake

Dieser Leitfaden beschreibt, wie die im Vault erzeugten semantischen Artefakte manuell in nachgelagerte Systeme übernommen werden. Er richtet sich an Operatoren, die einen Export aus `.gewebe/` entgegennehmen und aufbereiten.

## Ausgangslage prüfen
1. **Letzten Pipeline-Lauf validieren**
   - Kontrolliere den Zeitstempel der Dateien unter `.gewebe/out/` (insb. `nodes.jsonl`, `edges.jsonl`, `reports.json`).
   - Öffne `.gewebe/logs/pipeline.log` und stelle sicher, dass der Lauf ohne Fehlermeldungen beendet wurde.
2. **Artefakt-Checksums erzeugen**
   - `sha256sum .gewebe/out/nodes.jsonl > checksums.txt`
   - `sha256sum .gewebe/out/edges.jsonl >> checksums.txt`
   - Die Prüfsummen werden später dem Intake-Protokoll beigefügt.

## Intake durchführen
1. **Export-Verzeichnis vorbereiten**
   - Leere ggf. den Staging-Ordner (z. B. `/var/tmp/semantah-intake`).
   - Kopiere alle Dateien aus `.gewebe/out/` sowie `checksums.txt` in den Staging-Ordner.
2. **Archiv erstellen**
   - `tar czf semantah-intake-$(date +%Y%m%d).tgz -C /var/tmp/semantah-intake .`
   - Prüfe die Archivgröße (sollte plausibel zu den Ursprungsdateien passen).
3. **Transfer**
   - Übertrage das Archiv gemäß Zielsystem (z. B. `scp`, Artefakt-Registry oder S3-Bucket).
   - Notiere Transfer-ID/URL im Intake-Protokoll.
4. **Import im Zielsystem**
   - Entpacke das Archiv in der vorgesehenen Import-Zone.
   - Führe das lokale Importskript oder die Pipeline des Zielsystems aus.
   - Dokumentiere Erfolg bzw. Fehlermeldungen.

## Validierung im Zielsystem
1. **Integritätsprüfung**
   - Vergleiche die übertragenen Checksums mit den lokal generierten.
   - Schlägt die Prüfung fehl, wiederhole den Transfer.
2. **Spot-Checks**
   - Öffne stichprobenartig einen Eintrag aus `nodes.jsonl` und `edges.jsonl`.
   - Stelle sicher, dass Pflichtfelder (`id`, `title`, `embedding_id`, `source_path`) vorhanden sind.
3. **Funktionaler Test**
   - Führe eine Suchanfrage mit bekannten Dokumenten durch und verifiziere, dass Ergebnisse zurückgegeben werden.

## Fehlerbehebung
| Symptom | Mögliche Ursache | Vorgehen |
| --- | --- | --- |
| Artefakte fehlen | Pipeline-Lauf fehlgeschlagen | `make all` erneut ausführen, Logs prüfen, Parameterwahl (`embedder.provider`, `index.top_k`) kontrollieren |
| Checksums stimmen nicht | Unvollständiger Transfer | Archiv neu erzeugen/übertragen, Netzwerk prüfen |
| Import-Skript bricht ab | Schema-Änderungen oder veraltete Contracts | Auf aktuelle `contracts/`-Schemen aktualisieren, Release-Notes prüfen |

## Rückmeldung & Dokumentation
- Erfasse Intake-Datum, Vault-Commit und Transferpfad im Betriebsprotokoll.
- Vermerke manuelle Eingriffe oder Sonderfälle, um Lessons Learned in die Automatisierung zu überführen.
```
```

### 📄 merges/semantAH_merge_2510262237__docs_x-repo.md

**Größe:** 276 B | **md5:** `5d61fa1f2b81ce962fe0e578aac1252f`

```markdown
### 📄 docs/x-repo/weltgewebe.md

**Größe:** 157 B | **md5:** `4f8574180b4132f01652d73b43c4c827`

```markdown
semantAH liefert Semantik-Infos (Nodes/Edges/Reports) per JSON/JSONL.
Weltgewebe konsumiert read-only. Änderungen an Contracts nur additive (semver-minor).
```
```

### 📄 merges/semantAH_merge_2510262237__examples.md

**Größe:** 587 B | **md5:** `be51d6148868e607b4c1c0a1f6e0f3cc`

```markdown
### 📄 examples/semantah.example.yml

**Größe:** 468 B | **md5:** `3b83836d29ebe7d2b69c90988f4280e8`

```yaml
vault_path: /path/to/your/obsidian-vault
out_dir: .gewebe
embedder:
  provider: ollama          # oder: openai
  model: nomic-embed-text   # Beispielmodell (lokal)
index:
  top_k: 20
graph:
  cutoffs:
    # Beide Optionen anbieten – je nach aktuellem Parser:
    # (A) Ko-Vorkommen/gewichtete Kante:
    min_cooccur: 2
    min_weight: 0.15
    # (B) Falls der aktuelle Code noch auf Similarity-Schwelle hört:
    # min_similarity: 0.35
related:
  write_back: false
```
```

### 📄 merges/semantAH_merge_2510262237__index.md

**Größe:** 150 KB | **md5:** `fd7a093cc9c04a5bf50cc4f5e7eca4db`

```markdown
# Ordner-Merge: semantAH

**Zeitpunkt:** 2025-10-26 22:37
**Quelle:** `/home/alex/repos/semantAH`
**Dateien (gefunden):** 132
**Gesamtgröße (roh):** 521 KB

**Exclude:** ['.gitignore']

## 📁 Struktur

- semantAH/
  - .gitignore
  - .hauski-reports
  - CONTRIBUTING.md
  - Cargo.lock
  - Cargo.toml
  - Justfile
  - Makefile
  - README.md
  - codecov.yml
  - pyproject.toml
  - pytest.ini
  - semantah.yml
  - uv.lock
  - leitstand/
    - data/
      - aussen.jsonl
  - tests/
    - conftest.py
    - test_push_index.py
    - test_push_index_e2e.py
    - test_push_index_property.py
  - cli/
    - ingest_leitstand.py
  - docs/
    - README.md
    - blueprint.md
    - config-reference.md
    - embeddings.md
    - hauski.md
    - indexd-api.md
    - mitschreiber-index.md
    - namespaces.md
    - quickstart.md
    - roadmap.md
    - runbook.observability.md
    - semantAH brainstorm.md
    - semantAH.md
    - wgx-konzept.md
    - wgx.md
    - adr/
      - 0001-semantics-contract.md
    - x-repo/
      - weltgewebe.md
    - runbooks/
      - semantics-intake.md
  - systemd/
    - vault-gewebe.service
    - vault-gewebe.timer
  - .github/
    - ISSUE_TEMPLATE/
      - bug_report.yml
      - feature_request.yml
    - workflows/
      - ci-tools.yml
      - ci.yml
      - contracts.yml
      - wgx-guard.yml
  - semantAH/
    - .gitignore
    - .hauski-reports
    - CONTRIBUTING.md
    - Cargo.lock
    - Cargo.toml
    - Justfile
    - Makefile
    - README.md
    - pyproject.toml
    - uv.lock
    - target/
      - .rustc_info.json
      - CACHEDIR.TAG
      - tmp/
      - debug/
        - .cargo-lock
        - incremental/
          - healthz-2lzngp000ne03/
            - s-hbwq7xo2p2-1g5bc4t.lock
            - s-hbwq7xo2p2-1g5bc4t-a31qtump92y2icj5a4dcuufry/
              - dep-graph.bin
              - query-cache.bin
              - work-products.bin
          - indexd-0gypxqmelm1s5/
            - s-hbwq7xo1iv-1esl0hj.lock
            - s-hbwq7xo1iv-1esl0hj-5b8yo4vz52x5zihm3bfv9yts4/
              - dep-graph.bin
              - query-cache.bin
              - work-products.bin
          - embeddings-1f7g0bp801f7k/
            - s-hbwq7xhv77-0epb7x9.lock
            - s-hbwq7xhv77-0epb7x9-a20sbpagfgny0htxypyd0tn1k/
              - dep-graph.bin
              - query-cache.bin
              - work-products.bin
          - indexd-0ekasaxmnlxbm/
            - s-hbwq7xo2rr-1m4oqjq.lock
            - s-hbwq7xo2rr-1m4oqjq-9ak6qmcwpiouc94fscwft8nw6/
              - dep-graph.bin
              - query-cache.bin
              - work-products.bin
          - embeddings-17wpd49i4f43a/
            - s-hbwq7xhv6b-17docrd.lock
            - s-hbwq7xhv6b-17docrd-3x8icnqyru7jjazzapmrf6e63/
              - dep-graph.bin
              - metadata.rmeta
              - query-cache.bin
              - work-products.bin
          - indexd-0pfl17e5itaox/
            - s-hbwq7xll1d-1ggyd9w.lock
            - s-hbwq7xll1d-1ggyd9w-agie9lyg2nqa5zrxtu3of198u/
              - dep-graph.bin
              - query-cache.bin
              - work-products.bin
          - indexd-0m02eq4xxihpq/
            - s-hbwq7xll6t-1rthjou.lock
            - s-hbwq7xll6t-1rthjou-d735dgqqg82ylub6t4okdtzjk/
              - dep-graph.bin
              - metadata.rmeta
              - query-cache.bin
              - work-products.bin
        - .fingerprint/
          - sct-610042deafe106c4/
            - dep-lib-sct
            - invoked.timestamp
            - lib-sct
            - lib-sct.json
          - icu_normalizer_data-d2473f55c03a7556/
            - dep-lib-icu_normalizer_data
            - invoked.timestamp
            - lib-icu_normalizer_data
            - lib-icu_normalizer_data.json
          - tower-22795383ec370a4a/
            - dep-lib-tower
            - invoked.timestamp
            - lib-tower
            - lib-tower.json
          - serde_spanned-025b796f16aba5dd/
            - dep-lib-serde_spanned
            - invoked.timestamp
            - lib-serde_spanned
            - lib-serde_spanned.json
          - indexd-63fea37a2142965d/
            - bin-indexd
            - bin-indexd.json
            - dep-bin-indexd
            - invoked.timestamp
          - ucd-trie-a29b44964703be28/
            - dep-lib-ucd_trie
            - invoked.timestamp
            - lib-ucd_trie
            - lib-ucd_trie.json
          - regex-syntax-c71a7c16575686c9/
            - dep-lib-regex_syntax
            - invoked.timestamp
            - lib-regex_syntax
            - lib-regex_syntax.json
          - indexd-fae9799175250519/
            - dep-test-lib-indexd
            - invoked.timestamp
            - test-lib-indexd
            - test-lib-indexd.json
          - libc-c7bb2975c593da9c/
            - build-script-build-script-build
            - build-script-build-script-build.json
            - dep-build-script-build-script-build
            - invoked.timestamp
          - zerovec-cd00395e6eaed681/
            - dep-lib-zerovec
            - invoked.timestamp
            - lib-zerovec
            - lib-zerovec.json
          - thiserror-14edc43edb1485d2/
            - build-script-build-script-build
            - build-script-build-script-build.json
            - dep-build-script-build-script-build
            - invoked.timestamp
          - futures-sink-05ea9def2ed4c1f0/
            - dep-lib-futures_sink
            - invoked.timestamp
            - lib-futures_sink
            - lib-futures_sink.json
          - libc-542f1ead4d82bc85/
            - dep-lib-libc
            - invoked.timestamp
            - lib-libc
            - lib-libc.json
          - rustversion-1898eae5a255a4ec/
            - run-build-script-build-script-build
            - run-build-script-build-script-build.json
          - syn-f8783a30f2c4c479/
            - dep-lib-syn
            - invoked.timestamp
            - lib-syn
            - lib-syn.json
          - http-52ac24c42ba9853e/
            - dep-lib-http
            - invoked.timestamp
            - lib-http
            - lib-http.json
          - serde_path_to_error-d40e196f2ae7da67/
            - dep-lib-serde_path_to_error
            - invoked.timestamp
            - lib-serde_path_to_error
            - lib-serde_path_to_error.json
          - synstructure-f4b1fc400471b884/
            - dep-lib-synstructure
            - invoked.timestamp
            - lib-synstructure
            - lib-synstructure.json
          - memchr-ac8810823885e36e/
            - dep-lib-memchr
            - invoked.timestamp
            - lib-memchr
            - lib-memchr.json
          - tiny-keccak-16e952d84cdbee87/
            - build-script-build-script-build
            - build-script-build-script-build.json
            - dep-build-script-build-script-build
            - invoked.timestamp
          - httparse-a369f4806a928b1e/
            - build-script-build-script-build
            - build-script-build-script-build.json
            - dep-build-script-build-script-build
            - invoked.timestamp
          - rustls-3dd6ccac0f5e9433/
            - run-build-script-build-script-build
            - run-build-script-build-script-build.json
          - const-random-c735778bac29d9d4/
            - dep-lib-const_random
            - invoked.timestamp
            - lib-const_random
            - lib-const_random.json
          - http-body-6903b0d1f0b1cff0/
            - dep-lib-http_body
            - invoked.timestamp
            - lib-http_body
            - lib-http_body.json
          - libc-5186ca6c8f761738/
            - dep-lib-libc
            - invoked.timestamp
            - lib-libc
            - lib-libc.json
          - config-45ff1313409463f0/
            - dep-lib-config
            - invoked.timestamp
            - lib-config
            - lib-config.json
          - zerotrie-bf2f3b5d1a5cdc18/
            - dep-lib-zerotrie
            - invoked.timestamp
            - lib-zerotrie
            - lib-zerotrie.json
          - quote-ddf20bb25101601c/
            - run-build-script-build-script-build
            - run-build-script-build-script-build.json
          - tracing-attributes-2de78feca8e752f8/
            - dep-lib-tracing_attributes
            - invoked.timestamp
            - lib-tracing_attributes
            - lib-tracing_attributes.json
          - thiserror-e3b29a19691cddd9/
            - run-build-script-build-script-build
            - run-build-script-build-script-build.json
          - const-random-macro-7eb6d388444561b9/
            - dep-lib-const_random_macro
            - invoked.timestamp
            - lib-const_random_macro
            - lib-const_random_macro.json
          - getrandom-7ceafb5f5b62271c/
            - dep-lib-getrandom
            - invoked.timestamp
            - lib-getrandom
            - lib-getrandom.json
          - serde-81f7362c921f3803/
            - build-script-build-script-build
            - build-script-build-script-build.json
            - dep-build-script-build-script-build
            - invoked.timestamp
          - anyhow-e1f554b474e8a16f/
            - run-build-script-build-script-build
            - run-build-script-build-script-build.json
          - sync_wrapper-cc574eb954b2ae89/
            - dep-lib-sync_wrapper
            - invoked.timestamp
            - lib-sync_wrapper
            - lib-sync_wrapper.json
          - tower-layer-1b6d015ec69ffc49/
            - dep-lib-tower_layer
            - invoked.timestamp
            - lib-tower_layer
            - lib-tower_layer.json
          - socket2-4293b964e8c0a719/
            - dep-lib-socket2
            - invoked.timestamp
            - lib-socket2
            - lib-socket2.json
          - slab-42e319f38072c981/
            - dep-lib-slab
            - invoked.timestamp
            - lib-slab
            - lib-slab.json
          - want-8a8f417f4f52f03e/
            - dep-lib-want
            - invoked.timestamp
            - lib-want
            - lib-want.json
          - idna_adapter-c84556af106f7258/
            - dep-lib-idna_adapter
            - invoked.timestamp
            - lib-idna_adapter
            - lib-idna_adapter.json
          - mio-eb2cc0c0dbaf7d98/
            - dep-lib-mio
            - invoked.timestamp
            - lib-mio
            - lib-mio.json
          - tiny-keccak-4aab3bcce22aa9cd/
            - dep-lib-tiny_keccak
            - invoked.timestamp
            - lib-tiny_keccak
            - lib-tiny_keccak.json
          - icu_properties_data-e05272786a6e1307/
            - dep-lib-icu_properties_data
            - invoked.timestamp
            - lib-icu_properties_data
            - lib-icu_properties_data.json
          - httparse-2246c683a1e71a20/
            - run-build-script-build-script-build
            - run-build-script-build-script-build.json
          - hashbrown-6f49bc49a1fa1b16/
            - dep-lib-hashbrown
            - invoked.timestamp
            - lib-hashbrown
            - lib-hashbrown.json
          - httparse-b652932b81b77c4c/
            - dep-lib-httparse
            - invoked.timestamp
            - lib-httparse
            - lib-httparse.json
          - serde-f38b255d54569d39/
            - run-build-script-build-script-build
            - run-build-script-build-script-build.json
          - zerofrom-derive-700e2f5e6d726543/
            - dep-lib-zerofrom_derive
            - invoked.timestamp
            - lib-zerofrom_derive
            - lib-zerofrom_derive.json
          - futures-io-b8e049099b4a804f/
            - dep-lib-futures_io
            - invoked.timestamp
            - lib-futures_io
            - lib-futures_io.json
          - tower-service-d71afa1094c1aff5/
            - dep-lib-tower_service
            - invoked.timestamp
            - lib-tower_service
            - lib-tower_service.json
          - find-msvc-tools-cd670852f43fff4a/
            - dep-lib-find_msvc_tools
            - invoked.timestamp
            - lib-find_msvc_tools
            - lib-find_msvc_tools.json
          - ring-b01d4d9fe5bfb72a/
            - dep-lib-ring
            - invoked.timestamp
            - lib-ring
            - lib-ring.json
          - sync_wrapper-0ec2ddbd9f1c81b5/
            - dep-lib-sync_wrapper
            - invoked.timestamp
            - lib-sync_wrapper
            - lib-sync_wrapper.json
          - thread_local-1c0d514c6266b2f7/
            - dep-lib-thread_local
            - invoked.timestamp
            - lib-thread_local
            - lib-thread_local.json
          - serde_core-40d5fc03da81ff09/
            - build-script-build-script-build
            - build-script-build-script-build.json
            - dep-build-script-build-script-build
            - invoked.timestamp
          - futures-executor-1b9104f54694acd7/
            - dep-lib-futures_executor
            - invoked.timestamp
            - lib-futures_executor
            - lib-futures_executor.json
          - rustversion-795721cbadc38550/
            - dep-lib-rustversion
            - invoked.timestamp
            - lib-rustversion
            - lib-rustversion.json
          - indexd-59a3760dfe234e42/
            - dep-test-integration-test-healthz
            - invoked.timestamp
            - test-integration-test-healthz
            - test-integration-test-healthz.json
          - nom-c671ab6a23bd3c40/
            - dep-lib-nom
            - invoked.timestamp
            - lib-nom
            - lib-nom.json
          - tracing-log-aeae6eacf11ed394/
            - dep-lib-tracing_log
            - invoked.timestamp
            - lib-tracing_log
            - lib-tracing_log.json
          - utf8_iter-7af36920edb0fdad/
            - dep-lib-utf8_iter
            - invoked.timestamp
            - lib-utf8_iter
            - lib-utf8_iter.json
          - dlv-list-e0d1b922c2b2bcda/
            - dep-lib-dlv_list
            - invoked.timestamp
            - lib-dlv_list
            - lib-dlv_list.json
          - icu_collections-9726213a4a5b49eb/
            - dep-lib-icu_collections
            - invoked.timestamp
            - lib-icu_collections
            - lib-icu_collections.json
          - http-body-ee300e8c0401f7b0/
            - dep-lib-http_body
            - invoked.timestamp
            - lib-http_body
            - lib-http_body.json
          - potential_utf-13c44d2b5d621436/
            - dep-lib-potential_utf
            - invoked.timestamp
            - lib-potential_utf
            - lib-potential_utf.json
          - once_cell-199800b58c1e0d8f/
            - dep-lib-once_cell
            - invoked.timestamp
            - lib-once_cell
            - lib-once_cell.json
          - tokio-util-534c8e144da11d32/
            - dep-lib-tokio_util
            - invoked.timestamp
            - lib-tokio_util
            - lib-tokio_util.json
          - reqwest-cf44564cfbd5b2f2/
            - dep-lib-reqwest
            - invoked.timestamp
            - lib-reqwest
            - lib-reqwest.json
          - ordered-multimap-cefe1b1e455b6b0c/
            - dep-lib-ordered_multimap
            - invoked.timestamp
            - lib-ordered_multimap
            - lib-ordered_multimap.json
          - pest_meta-521d80e15af1a302/
            - dep-lib-pest_meta
            - invoked.timestamp
            - lib-pest_meta
            - lib-pest_meta.json
          - toml-cb99dc3dd9f6a6b1/
            - dep-lib-toml
            - invoked.timestamp
            - lib-toml
            - lib-toml.json
          - pin-utils-e3f5a18815d2cac2/
            - dep-lib-pin_utils
            - invoked.timestamp
            - lib-pin_utils
            - lib-pin_utils.json
          - socket2-7a6bfd6739fb22d8/
            - dep-lib-socket2
            - invoked.timestamp
            - lib-socket2
            - lib-socket2.json
          - axum-core-b17222bd1db15a02/
            - dep-lib-axum_core
            - invoked.timestamp
            - lib-axum_core
            - lib-axum_core.json
          - pest_generator-60775fbee86e58ea/
            - dep-lib-pest_generator
            - invoked.timestamp
            - lib-pest_generator
            - lib-pest_generator.json
          - libc-2f490522edf39f4b/
            - build-script-build-script-build
            - build-script-build-script-build.json
            - dep-build-script-build-script-build
            - invoked.timestamp
          - h2-a4921cdccf0fe94b/
            - dep-lib-h2
            - invoked.timestamp
            - lib-h2
            - lib-h2.json
          - toml_datetime-0680974255da6f9d/
            - dep-lib-toml_datetime
            - invoked.timestamp
            - lib-toml_datetime
            - lib-toml_datetime.json
          - httpdate-6f7f6b494863ddbc/
            - dep-lib-httpdate
            - invoked.timestamp
            - lib-httpdate
            - lib-httpdate.json
          - embeddings-0dcd384a27104358/
            - dep-test-lib-embeddings
            - invoked.timestamp
            - test-lib-embeddings
            - test-lib-embeddings.json
          - tiny-keccak-1e2acd248fbb8a51/
            - run-build-script-build-script-build
            - run-build-script-build-script-build.json
          - icu_provider-104bdf506ceefa9d/
            - dep-lib-icu_provider
            - invoked.timestamp
            - lib-icu_provider
            - lib-icu_provider.json
          - quote-63c10b5fc1327b7e/
            - build-script-build-script-build
            - build-script-build-script-build.json
            - dep-build-script-build-script-build
            - invoked.timestamp
          - allocator-api2-a22f0c0335f16551/
            - dep-lib-allocator_api2
            - invoked.timestamp
            - lib-allocator_api2
            - lib-allocator_api2.json
          - quote-8d2cf6eade48d828/
            - dep-lib-quote
            - invoked.timestamp
            - lib-quote
            - lib-quote.json
          - pest-9a89b7899fc10f70/
            - dep-lib-pest
            - invoked.timestamp
            - lib-pest
            - lib-pest.json
          - convert_case-293087dbcb773ef8/
            - dep-lib-convert_case
            - invoked.timestamp
            - lib-convert_case
            - lib-convert_case.json
          - axum-c017659abcac06a0/
            - dep-lib-axum
            - invoked.timestamp
            - lib-axum
            - lib-axum.json
          - winnow-cc879e89137baf86/
            - dep-lib-winnow
            - invoked.timestamp
            - lib-winnow
            - lib-winnow.json
          - hyper-8675b2d5b608cb15/
            - dep-lib-hyper
            - invoked.timestamp
            - lib-hyper
            - lib-hyper.json
          - ring-be23df2888fbac6e/
            - run-build-script-build-script-build
            - run-build-script-build-script-build.json
          - webpki-roots-91ee2910580bc06c/
            - dep-lib-webpki_roots
            - invoked.timestamp
            - lib-webpki_roots
            - lib-webpki_roots.json
          - futures-task-c688eff9bf0e8af6/
            - dep-lib-futures_task
            - invoked.timestamp
            - lib-futures_task
            - lib-futures_task.json
          - pest_derive-f63333bc74127723/
            - dep-lib-pest_derive
            - invoked.timestamp
            - lib-pest_derive
            - lib-pest_derive.json
          - tracing-fabeb9bd26a8dab6/
            - dep-lib-tracing
            - invoked.timestamp
            - lib-tracing
            - lib-tracing.json
          - zerofrom-d0dc7ed94a914b1d/
            - dep-lib-zerofrom
            - invoked.timestamp
            - lib-zerofrom
            - lib-zerofrom.json
          - icu_properties-136b1cf8d0215bca/
            - dep-lib-icu_properties
            - invoked.timestamp
            - lib-icu_properties
            - lib-icu_properties.json
          - anyhow-b3393d6712be2b66/
            - build-script-build-script-build
            - build-script-build-script-build.json
            - dep-build-script-build-script-build
            - invoked.timestamp
          - percent-encoding-c62866a235b4614b/
            - dep-lib-percent_encoding
            - invoked.timestamp
            - lib-percent_encoding
            - lib-percent_encoding.json
          - stable_deref_trait-f4996df1e7b410b7/
            - dep-lib-stable_deref_trait
            - invoked.timestamp
            - lib-stable_deref_trait
            - lib-stable_deref_trait.json
          - litemap-fa5f69ff97a53b59/
            - dep-lib-litemap
            - invoked.timestamp
            - lib-litemap
            - lib-litemap.json
          - arraydeque-fa6752a783ed2b57/
            - dep-lib-arraydeque
            - invoked.timestamp
            - lib-arraydeque
            - lib-arraydeque.json
          - indexd-a3ace90acb5e7b07/
            - dep-lib-indexd
            - invoked.timestamp
            - lib-indexd
            - lib-indexd.json
          - memchr-922a473a227244b5/
            - dep-lib-memchr
            - invoked.timestamp
            - lib-memchr
            - lib-memchr.json
          - crunchy-0e05c535dbd3e1af/
            - dep-lib-crunchy
            - invoked.timestamp
            - lib-crunchy
            - lib-crunchy.json
          - thiserror-impl-a2fa31476b8609db/
            - dep-lib-thiserror_impl
            - invoked.timestamp
            - lib-thiserror_impl
            - lib-thiserror_impl.json
          - ahash-a58a0b42ca789794/
            - build-script-build-script-build
            - build-script-build-script-build.json
            - dep-build-script-build-script-build
            - invoked.timestamp
          - try-lock-b39d2f1611e73d1b/
            - dep-lib-try_lock
            - invoked.timestamp
            - lib-try_lock
            - lib-try_lock.json
          - serde-5e2f03484c5d9df5/
            - dep-lib-serde
            - invoked.timestamp
            - lib-serde
            - lib-serde.json
          - atomic-waker-82767012afcabf64/
            - dep-lib-atomic_waker
            - invoked.timestamp
            - lib-atomic_waker
            - lib-atomic_waker.json
          - rustls-pemfile-8feada489c89a7a7/
            - dep-lib-rustls_pemfile
            - invoked.timestamp
            - lib-rustls_pemfile
            - lib-rustls_pemfile.json
          - ron-4e83d029b28d6efb/
            - dep-lib-ron
            - invoked.timestamp
            - lib-ron
            - lib-ron.json
          - hyper-rustls-71d728a1c3bcea59/
            - dep-lib-hyper_rustls
            - invoked.timestamp
            - lib-hyper_rustls
            - lib-hyper_rustls.json
          - thiserror-5c20fbe13b91aced/
            - dep-lib-thiserror
            - invoked.timestamp
            - lib-thiserror
            - lib-thiserror.json
          - regex-automata-92c5f123f57e385b/
            - dep-lib-regex_automata
            - invoked.timestamp
            - lib-regex_automata
            - lib-regex_automata.json
          - getrandom-150044f3c1f6fe2f/
            - dep-lib-getrandom
            - invoked.timestamp
            - lib-getrandom
            - lib-getrandom.json
          - async-trait-726a1672b7657095/
            - dep-lib-async_trait
            - invoked.timestamp
            - lib-async_trait
            - lib-async_trait.json
          - writeable-7fd0e8655a97a0d9/
            - dep-lib-writeable
            - invoked.timestamp
            - lib-writeable
            - lib-writeable.json
          - icu_properties_data-68ef7f1b98d542f4/
            - run-build-script-build-script-build
            - run-build-script-build-script-build.json
          - futures-core-b17a82b164bf052b/
            - dep-lib-futures_core
            - invoked.timestamp
            - lib-futures_core
            - lib-futures_core.json
          - tokio-macros-ca6c86f8479570e2/
            - dep-lib-tokio_macros
            - invoked.timestamp
            - lib-tokio_macros
            - lib-tokio_macros.json
          - idna-394f1d2551f6775c/
            - dep-lib-idna
            - invoked.timestamp
            - lib-idna
            - lib-idna.json
          - bytes-ea8af492080e3cde/
            - dep-lib-bytes
            - invoked.timestamp
            - lib-bytes
            - lib-bytes.json
          - pathdiff-6844f19057df889f/
            - dep-lib-pathdiff
            - invoked.timestamp
            - lib-pathdiff
            - lib-pathdiff.json
          - cfg-if-67cd4df49c586b65/
            - dep-lib-cfg_if
            - invoked.timestamp
            - lib-cfg_if
            - lib-cfg_if.json
          - serde_core-638a546787e7afb3/
            - run-build-script-build-script-build
            - run-build-script-build-script-build.json
          - form_urlencoded-4ab59003a35d276c/
            - dep-lib-form_urlencoded
            - invoked.timestamp
            - lib-form_urlencoded
            - lib-form_urlencoded.json
          - equivalent-f8f7e9459c1fce4f/
            - dep-lib-equivalent
            - invoked.timestamp
            - lib-equivalent
            - lib-equivalent.json
          - serde_json-512584006a6c2111/
            - dep-lib-serde_json
            - invoked.timestamp
            - lib-serde_json
            - lib-serde_json.json
          - futures-macro-5da2fbec6c659957/
            - dep-lib-futures_macro
            - invoked.timestamp
            - lib-futures_macro
            - lib-futures_macro.json
          - encoding_rs-10e55c842f376659/
            - dep-lib-encoding_rs
            - invoked.timestamp
            - lib-encoding_rs
            - lib-encoding_rs.json
          - serde_core-4f31211e9eb2dd06/
            - dep-lib-serde_core
            - invoked.timestamp
            - lib-serde_core
            - lib-serde_core.json
          - hyper-1c02d543594bca19/
            - dep-lib-hyper
            - invoked.timestamp
            - lib-hyper
            - lib-hyper.json
          - indexd-5717d583f5d74ecb/
            - dep-test-bin-indexd
            - invoked.timestamp
            - test-bin-indexd
            - test-bin-indexd.json
          - yaml-rust2-44ee6581f393760b/
            - dep-lib-yaml_rust2
            - invoked.timestamp
            - lib-yaml_rust2
            - lib-yaml_rust2.json
          - icu_normalizer_data-02b3286e562902a4/
            - build-script-build-script-build
            - build-script-build-script-build.json
            - dep-build-script-build-script-build
            - invoked.timestamp
          - pin-project-lite-0e86af28d48f0ea3/
            - dep-lib-pin_project_lite
            - invoked.timestamp
            - lib-pin_project_lite
            - lib-pin_project_lite.json
          - nu-ansi-term-20ac54036f6d20c5/
            - dep-lib-nu_ansi_term
            - invoked.timestamp
            - lib-nu_ansi_term
            - lib-nu_ansi_term.json

<<TRUNCATED: max_file_lines=800>>
```

### 📄 merges/semantAH_merge_2510262237__leitstand_data.md

**Größe:** 225 B | **md5:** `b0ac9ac21ce7f4847109de5d165ccb22`

```markdown
### 📄 leitstand/data/aussen.jsonl

**Größe:** 103 B | **md5:** `967d43f2d0efc387a44a2949be9efaa1`

```plaintext
{"title": "Test Insight", "summary": "This is a test.", "url": "http://example.com", "tags": ["test"]}
```
```

### 📄 merges/semantAH_merge_2510262237__part001.md

**Größe:** 43 B | **md5:** `ad150e6cdda3920dbef4d54c92745d83`

```markdown
<!-- chunk:1 created:2025-10-26 22:37 -->
```

### 📄 merges/semantAH_merge_2510262237__root.md

**Größe:** 123 KB | **md5:** `4d313eb6f5c16fd93cfa9fd9313aa1cd`

```markdown
### 📄 .gitignore

**Größe:** 225 B | **md5:** `81e3fdbfd79d11b2587546f112bbb0e5`

```plaintext
# Build artefacts & caches
/target/
.gewebe/
vault/.gewebe/
.pytest_cache/
.ruff_cache/
.mypy_cache/
__pycache__/
*.egg-info/

# Python/uv
.venv/
.uv/

# Local env
.env
.envrc
semantah.yml

# OS-specific
.DS_Store
Thumbs.db
```

### 📄 CONTRIBUTING.md

**Größe:** 341 B | **md5:** `d3bb7315c516417e49494a241c028546`

```markdown
# CONTRIBUTING

## Dev-Setup
1. Rust ≥ 1.75, Python ≥ 3.10
2. `make venv` (oder `uv sync`)
3. `make all`, `cargo run -p indexd`

## Konventionen
- Rust: `cargo fmt`, `cargo clippy`
- Python: `ruff check`, `pytest`
- Commits: klar und klein; PRs mit reproduzierbaren Schritten

## Tests
- `just`/`make` Targets folgen noch in der Roadmap
```

### 📄 Cargo.lock

**Größe:** 54 KB | **md5:** `ea1146b9f0242f5b673291cd43fa036e`

```plaintext
# This file is automatically @generated by Cargo.
# It is not intended for manual editing.
version = 4

[[package]]
name = "addr2line"
version = "0.25.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1b5d307320b3181d6d7954e663bd7c774a838b8220fe0593c86d9fb09f498b4b"
dependencies = [
 "gimli",
]

[[package]]
name = "adler2"
version = "2.0.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "320119579fcad9c21884f5c4861d16174d0e06250625266f50fe6898340abefa"

[[package]]
name = "ahash"
version = "0.8.12"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "5a15f179cd60c4584b8a8c596927aadc462e27f2ca70c04e0071964a73ba7a75"
dependencies = [
 "cfg-if",
 "once_cell",
 "version_check",
 "zerocopy",
]

[[package]]
name = "aho-corasick"
version = "1.1.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "8e60d3430d3a69478ad0993f19238d2df97c507009a52b3c10addcd7f6bcb916"
dependencies = [
 "memchr",
]

[[package]]
name = "allocator-api2"
version = "0.2.21"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "683d7910e743518b0e34f1186f92494becacb047c7b6bf616c96772180fef923"

[[package]]
name = "anyhow"
version = "1.0.100"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "a23eb6b1614318a8071c9b2521f36b424b2c83db5eb3a0fead4a6c0809af6e61"

[[package]]
name = "arraydeque"
version = "0.5.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "7d902e3d592a523def97af8f317b08ce16b7ab854c1985a0c671e6f15cebc236"

[[package]]
name = "async-trait"
version = "0.1.89"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9035ad2d096bed7955a320ee7e2230574d28fd3c3a0f186cbea1ff3c7eed5dbb"
dependencies = [
 "proc-macro2",
 "quote",
 "syn",
]

[[package]]
name = "atomic-waker"
version = "1.1.2"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1505bd5d3d116872e7271a6d4e16d81d0c8570876c8de68093a09ac269d8aac0"

[[package]]
name = "axum"
version = "0.7.9"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "edca88bc138befd0323b20752846e6587272d3b03b0343c8ea28a6f819e6e71f"
dependencies = [
 "async-trait",
 "axum-core",
 "bytes",
 "futures-util",
 "http 1.3.1",
 "http-body 1.0.1",
 "http-body-util",
 "hyper 1.7.0",
 "hyper-util",
 "itoa",
 "matchit",
 "memchr",
 "mime",
 "percent-encoding",
 "pin-project-lite",
 "rustversion",
 "serde",
 "serde_json",
 "serde_path_to_error",
 "serde_urlencoded",
 "sync_wrapper 1.0.2",
 "tokio",
 "tower",
 "tower-layer",
 "tower-service",
 "tracing",
]

[[package]]
name = "axum-core"
version = "0.4.5"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "09f2bd6146b97ae3359fa0cc6d6b376d9539582c7b4220f041a33ec24c226199"
dependencies = [
 "async-trait",
 "bytes",
 "futures-util",
 "http 1.3.1",
 "http-body 1.0.1",
 "http-body-util",
 "mime",
 "pin-project-lite",
 "rustversion",
 "sync_wrapper 1.0.2",
 "tower-layer",
 "tower-service",
 "tracing",
]

[[package]]
name = "backtrace"
version = "0.3.76"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "bb531853791a215d7c62a30daf0dde835f381ab5de4589cfe7c649d2cbe92bd6"
dependencies = [
 "addr2line",
 "cfg-if",
 "libc",
 "miniz_oxide",
 "object",
 "rustc-demangle",
 "windows-link",
]

[[package]]
name = "base64"
version = "0.21.7"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9d297deb1925b89f2ccc13d7635fa0714f12c87adce1c75356b39ca9b7178567"

[[package]]
name = "bitflags"
version = "1.3.2"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "bef38d45163c2f1dde094a7dfd33ccf595c92905c8f8f4fdc18d06fb1037718a"

[[package]]
name = "bitflags"
version = "2.9.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "2261d10cca569e4643e526d8dc2e62e433cc8aba21ab764233731f8d369bf394"
dependencies = [
 "serde",
]

[[package]]
name = "block-buffer"
version = "0.10.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "3078c7629b62d3f0439517fa394996acacc5cbc91c5a20d8c658e77abd503a71"
dependencies = [
 "generic-array",
]

[[package]]
name = "bumpalo"
version = "3.19.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "46c5e41b57b8bba42a04676d81cb89e9ee8e859a1a66f80a5a72e1cb76b34d43"

[[package]]
name = "bytes"
version = "1.10.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "d71b6127be86fdcfddb610f7182ac57211d4b18a3e9c82eb2d17662f2227ad6a"

[[package]]
name = "cc"
version = "1.2.40"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "e1d05d92f4b1fd76aad469d46cdd858ca761576082cd37df81416691e50199fb"
dependencies = [
 "find-msvc-tools",
 "shlex",
]

[[package]]
name = "cfg-if"
version = "1.0.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "2fd1289c04a9ea8cb22300a459a72a385d7c73d3259e2ed7dcb2af674838cfa9"

[[package]]
name = "config"
version = "0.14.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "68578f196d2a33ff61b27fae256c3164f65e36382648e30666dde05b8cc9dfdf"
dependencies = [
 "async-trait",
 "convert_case",
 "json5",
 "nom",
 "pathdiff",
 "ron",
 "rust-ini",
 "serde",
 "serde_json",
 "toml",
 "yaml-rust2",
]

[[package]]
name = "const-random"
version = "0.1.18"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "87e00182fe74b066627d63b85fd550ac2998d4b0bd86bfed477a0ae4c7c71359"
dependencies = [
 "const-random-macro",
]

[[package]]
name = "const-random-macro"
version = "0.1.16"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "f9d839f2a20b0aee515dc581a6172f2321f96cab76c1a38a4c584a194955390e"
dependencies = [
 "getrandom 0.2.16",
 "once_cell",
 "tiny-keccak",
]

[[package]]
name = "convert_case"
version = "0.6.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "ec182b0ca2f35d8fc196cf3404988fd8b8c739a4d270ff118a398feb0cbec1ca"
dependencies = [
 "unicode-segmentation",
]

[[package]]
name = "core-foundation"
version = "0.9.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "91e195e091a93c46f7102ec7818a2aa394e1e1771c3ab4825963fa03e45afb8f"
dependencies = [
 "core-foundation-sys",
 "libc",
]

[[package]]
name = "core-foundation-sys"
version = "0.8.7"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "773648b94d0e5d620f64f280777445740e61fe701025087ec8b57f45c791888b"

[[package]]
name = "cpufeatures"
version = "0.2.17"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "59ed5838eebb26a2bb2e58f6d5b5316989ae9d08bab10e0e6d103e656d1b0280"
dependencies = [
 "libc",
]

[[package]]
name = "crunchy"
version = "0.2.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "460fbee9c2c2f33933d720630a6a0bac33ba7053db5344fac858d4b8952d77d5"

[[package]]
name = "crypto-common"
version = "0.1.6"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1bfb12502f3fc46cca1bb51ac28df9d618d813cdc3d2f25b9fe775a34af26bb3"
dependencies = [
 "generic-array",
 "typenum",
]

[[package]]
name = "digest"
version = "0.10.7"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9ed9a281f7bc9b7576e61468ba615a66a5c8cfdff42420a70aa82701a3b1e292"
dependencies = [
 "block-buffer",
 "crypto-common",
]

[[package]]
name = "displaydoc"
version = "0.2.5"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "97369cbbc041bc366949bc74d34658d6cda5621039731c6310521892a3a20ae0"
dependencies = [
 "proc-macro2",
 "quote",
 "syn",
]

[[package]]
name = "dlv-list"
version = "0.5.2"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "442039f5147480ba31067cb00ada1adae6892028e40e45fc5de7b7df6dcc1b5f"
dependencies = [
 "const-random",
]

[[package]]
name = "embeddings"
version = "0.1.0"
dependencies = [
 "anyhow",
 "async-trait",
 "reqwest",
 "serde",
 "serde_json",
 "tokio",
 "tracing",
]

[[package]]
name = "encoding_rs"
version = "0.8.35"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "75030f3c4f45dafd7586dd6780965a8c7e8e285a5ecb86713e63a79c5b2766f3"
dependencies = [
 "cfg-if",
]

[[package]]
name = "equivalent"
version = "1.0.2"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "877a4ace8713b0bcf2a4e7eec82529c029f1d0619886d18145fea96c3ffe5c0f"

[[package]]
name = "errno"
version = "0.3.14"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "39cab71617ae0d63f51a36d69f866391735b51691dbda63cf6f96d042b63efeb"
dependencies = [
 "libc",
 "windows-sys 0.59.0",
]

[[package]]
name = "fastrand"
version = "2.3.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "37909eebbb50d72f9059c3b6d82c0463f2ff062c9e95845c43a6c9c0355411be"

[[package]]
name = "find-msvc-tools"
version = "0.1.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "0399f9d26e5191ce32c498bebd31e7a3ceabc2745f0ac54af3f335126c3f24b3"

[[package]]
name = "fnv"
version = "1.0.7"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "3f9eec918d3f24069decb9af1554cad7c880e2da24a9afd88aca000531ab82c1"

[[package]]
name = "form_urlencoded"
version = "1.2.2"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "cb4cb245038516f5f85277875cdaa4f7d2c9a0fa0468de06ed190163b1581fcf"
dependencies = [
 "percent-encoding",
]

[[package]]
name = "futures"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "65bc07b1a8bc7c85c5f2e110c476c7389b4554ba72af57d8445ea63a576b0876"
dependencies = [
 "futures-channel",
 "futures-core",
 "futures-executor",
 "futures-io",
 "futures-sink",
 "futures-task",
 "futures-util",
]

[[package]]
name = "futures-channel"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "2dff15bf788c671c1934e366d07e30c1814a8ef514e1af724a602e8a2fbe1b10"
dependencies = [
 "futures-core",
 "futures-sink",
]

[[package]]
name = "futures-core"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "05f29059c0c2090612e8d742178b0580d2dc940c837851ad723096f87af6663e"

[[package]]
name = "futures-executor"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1e28d1d997f585e54aebc3f97d39e72338912123a67330d723fdbb564d646c9f"
dependencies = [
 "futures-core",
 "futures-task",
 "futures-util",
]

[[package]]
name = "futures-io"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9e5c1b78ca4aae1ac06c48a526a655760685149f0d465d21f37abfe57ce075c6"

[[package]]
name = "futures-macro"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "162ee34ebcb7c64a8abebc059ce0fee27c2262618d7b60ed8faf72fef13c3650"
dependencies = [
 "proc-macro2",
 "quote",
 "syn",
]

[[package]]
name = "futures-sink"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "e575fab7d1e0dcb8d0c7bcf9a63ee213816ab51902e6d244a95819acacf1d4f7"

[[package]]
name = "futures-task"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "f90f7dce0722e95104fcb095585910c0977252f286e354b5e3bd38902cd99988"

[[package]]
name = "futures-util"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9fa08315bb612088cc391249efdc3bc77536f16c91f6cf495e6fbe85b20a4a81"
dependencies = [
 "futures-channel",
 "futures-core",
 "futures-io",
 "futures-macro",
 "futures-sink",
 "futures-task",
 "memchr",
 "pin-project-lite",
 "pin-utils",
 "slab",
]

[[package]]
name = "generic-array"
version = "0.14.7"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "85649ca51fd72272d7821adaf274ad91c288277713d9c18820d8499a7ff69e9a"
dependencies = [
 "typenum",
 "version_check",
]

[[package]]
name = "getrandom"
version = "0.2.16"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "335ff9f135e4384c8150d6f27c6daed433577f86b4750418338c01a1a2528592"
dependencies = [
 "cfg-if",
 "libc",
 "wasi",
]

[[package]]
name = "getrandom"
version = "0.3.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "899def5c37c4fd7b2664648c28120ecec138e4d395b459e5ca34f9cce2dd77fd"
dependencies = [
 "cfg-if",
 "libc",
 "r-efi",
 "wasip2",
]

[[package]]
name = "gimli"
version = "0.32.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "e629b9b98ef3dd8afe6ca2bd0f89306cec16d43d907889945bc5d6687f2f13c7"

[[package]]
name = "h2"
version = "0.3.27"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "0beca50380b1fc32983fc1cb4587bfa4bb9e78fc259aad4a0032d2080309222d"
dependencies = [
 "bytes",
 "fnv",
 "futures-core",
 "futures-sink",
 "futures-util",
 "http 0.2.12",
 "indexmap",
 "slab",
 "tokio",
 "tokio-util",
 "tracing",
]

[[package]]
name = "hashbrown"
version = "0.14.5"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "e5274423e17b7c9fc20b6e7e208532f9b19825d82dfd615708b70edd83df41f1"
dependencies = [
 "ahash",
 "allocator-api2",
]

[[package]]
name = "hashbrown"
version = "0.16.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "5419bdc4f6a9207fbeba6d11b604d481addf78ecd10c11ad51e76c2f6482748d"

[[package]]
name = "hashlink"
version = "0.8.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "e8094feaf31ff591f651a2664fb9cfd92bba7a60ce3197265e9482ebe753c8f7"
dependencies = [
 "hashbrown 0.14.5",
]

[[package]]
name = "http"
version = "0.2.12"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "601cbb57e577e2f5ef5be8e7b83f0f63994f25aa94d673e54a92d5c516d101f1"
dependencies = [
 "bytes",
 "fnv",
 "itoa",
]

[[package]]
name = "http"
version = "1.3.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "f4a85d31aea989eead29a3aaf9e1115a180df8282431156e533de47660892565"
dependencies = [
 "bytes",
 "fnv",
 "itoa",
]

[[package]]
name = "http-body"
version = "0.4.6"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "7ceab25649e9960c0311ea418d17bee82c0dcec1bd053b5f9a66e265a693bed2"
dependencies = [
 "bytes",
 "http 0.2.12",
 "pin-project-lite",
]

[[package]]
name = "http-body"
version = "1.0.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1efedce1fb8e6913f23e0c92de8e62cd5b772a67e7b3946df930a62566c93184"
dependencies = [
 "bytes",
 "http 1.3.1",
]

[[package]]
name = "http-body-util"
version = "0.1.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "b021d93e26becf5dc7e1b75b1bed1fd93124b374ceb73f43d4d4eafec896a64a"
dependencies = [
 "bytes",
 "futures-core",
 "http 1.3.1",
 "http-body 1.0.1",
 "pin-project-lite",
]

[[package]]
name = "httparse"
version = "1.10.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "6dbf3de79e51f3d586ab4cb9d5c3e2c14aa28ed23d180cf89b4df0454a69cc87"

[[package]]
name = "httpdate"
version = "1.0.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "df3b46402a9d5adb4c86a0cf463f42e19994e3ee891101b1841f30a545cb49a9"

[[package]]
name = "hyper"
version = "0.14.32"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "41dfc780fdec9373c01bae43289ea34c972e40ee3c9f6b3c8801a35f35586ce7"
dependencies = [
 "bytes",
 "futures-channel",
 "futures-core",
 "futures-util",
 "h2",
 "http 0.2.12",
 "http-body 0.4.6",
 "httparse",
 "httpdate",
 "itoa",
 "pin-project-lite",
 "socket2 0.5.10",
 "tokio",
 "tower-service",
 "tracing",
 "want",
]

[[package]]
name = "hyper"
version = "1.7.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "eb3aa54a13a0dfe7fbe3a59e0c76093041720fdc77b110cc0fc260fafb4dc51e"
dependencies = [
 "atomic-waker",
 "bytes",
 "futures-channel",
 "futures-core",
 "http 1.3.1",
 "http-body 1.0.1",
 "httparse",
 "httpdate",
 "itoa",
 "pin-project-lite",
 "pin-utils",
 "smallvec",
 "tokio",
]

[[package]]
name = "hyper-rustls"
version = "0.24.2"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "ec3efd23720e2049821a693cbc7e65ea87c72f1c58ff2f9522ff332b1491e590"
dependencies = [
 "futures-util",
 "http 0.2.12",
 "hyper 0.14.32",
 "rustls",
 "tokio",
 "tokio-rustls",
]

[[package]]
name = "hyper-util"
version = "0.1.17"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "3c6995591a8f1380fcb4ba966a252a4b29188d51d2b89e3a252f5305be65aea8"
dependencies = [
 "bytes",
 "futures-core",
 "http 1.3.1",
 "http-body 1.0.1",
 "hyper 1.7.0",
 "pin-project-lite",
 "tokio",
 "tower-service",
]

[[package]]
name = "icu_collections"
version = "2.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "200072f5d0e3614556f94a9930d5dc3e0662a652823904c3a75dc3b0af7fee47"
dependencies = [
 "displaydoc",
 "potential_utf",
 "yoke",
 "zerofrom",
 "zerovec",
]

[[package]]
name = "icu_locale_core"
version = "2.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "0cde2700ccaed3872079a65fb1a78f6c0a36c91570f28755dda67bc8f7d9f00a"
dependencies = [
 "displaydoc",
 "litemap",
 "tinystr",
 "writeable",
 "zerovec",
]

[[package]]
name = "icu_normalizer"
version = "2.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "436880e8e18df4d7bbc06d58432329d6458cc84531f7ac5f024e93deadb37979"
dependencies = [
 "displaydoc",
 "icu_collections",
 "icu_normalizer_data",
 "icu_properties",
 "icu_provider",
 "smallvec",
 "zerovec",
]

[[package]]
name = "icu_normalizer_data"

<<TRUNCATED: max_file_lines=800>>
```

### 📄 merges/semantAH_merge_2510262237__scripts.md

**Größe:** 16 KB | **md5:** `0c68ee8a96803a4c9e15fd13fbf028bd`

```markdown
### 📄 scripts/README.md

**Größe:** 2 KB | **md5:** `54a7526b2afa9ee3bb4852a60476ddc8`

```markdown
# Pipeline-Skripte

Die Python-Skripte im Verzeichnis `scripts/` bilden den orchestrierten Pipeline-Flow von semantAH nach. Aktuell handelt es sich um ausführbare Stubs, die Struktur, Artefakte und Logging demonstrieren. Sie können als Ausgangspunkt für produktive Implementierungen dienen.

| Skript | Zweck | Output | Hinweise |
| --- | --- | --- | --- |
| `build_index.py` | Erstellt Embedding-Datei (`embeddings.parquet`). | `.gewebe/embeddings.parquet` | Legt bei Bedarf das Zielverzeichnis an und erzeugt eine CSV-ähnliche Platzhalterdatei. |
| `build_graph.py` | Übersetzt Embeddings in Graph-Knoten/-Kanten. | `.gewebe/nodes.jsonl`, `.gewebe/edges.jsonl` | Schreibt minimal valide JSONL-Zeilen, damit Folgeprozesse getestet werden können. |
| `update_related.py` | Fügt Markdown-Dateien einen Related-Block hinzu. | `notes_stub/example.md` | Verhindert doppelte Blöcke durch Marker `<!-- related:auto:start -->`. |
| `export_insights.py` | Exportiert Tageszusammenfassungen für Dashboards. | `$VAULT_ROOT/.gewebe/insights/today.json` | Erwartet die Umgebungsvariable `VAULT_ROOT`; erzeugt strukturierte JSON-Stubs ≤10 KB. |

## Ausführung
```bash
make venv           # virtuelle Umgebung anlegen
. .venv/bin/activate
python scripts/build_index.py
python scripts/build_graph.py
python scripts/update_related.py
```

Die Skripte nutzen aktuell keine externen Abhängigkeiten und lassen sich direkt mit Python ≥3.10 ausführen. Für produktiven Einsatz sollten die Stub-Ausgaben durch echte Pipeline-Schritte ersetzt und mit `semantah.yml` parametrisiert werden.
```

### 📄 scripts/build_graph.py

**Größe:** 636 B | **md5:** `17da42d1abe3ab91b758ce562c52c1fb`

```python
#!/usr/bin/env python3
"""Stub script to turn embeddings into graph nodes and edges.

This is a placeholder for the full implementation.
See `docs/blueprint.md` for the full concept.
"""

import json
from pathlib import Path

GEWEBE = Path(".gewebe")
NODES = GEWEBE / "nodes.jsonl"
EDGES = GEWEBE / "edges.jsonl"


def main() -> None:
    GEWEBE.mkdir(exist_ok=True)
    NODES.write_text(f"{json.dumps({'id': 'stub:node'})}\n")
    EDGES.write_text(f"{json.dumps({'s': 'stub:node', 'p': 'related', 'o': 'stub:other', 'w': 0.0})}\n")
    print("[stub] build_graph → wrote", NODES, "and", EDGES)


if __name__ == "__main__":
    main()
```

### 📄 scripts/build_index.py

**Größe:** 504 B | **md5:** `54e7e86820d86a0bc6935bd52e81f022`

```python
#!/usr/bin/env python3
"""Stub script for building embeddings and chunk index artifacts.

This is a placeholder for the full implementation.
See `docs/blueprint.md` for the full concept.
"""

from pathlib import Path

OUTPUT = Path(".gewebe/embeddings.parquet")


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if not OUTPUT.exists():
        OUTPUT.write_text("id,text,embedding\n")
    print("[stub] build_index → wrote", OUTPUT)


if __name__ == "__main__":
    main()
```

### 📄 scripts/export_insights.py

**Größe:** 1 KB | **md5:** `c19d848a351934d606ebb312990933ac`

```python
#!/usr/bin/env python3
"""
Stub: exportiert Tages-Insights als JSON.
Ziel: $VAULT_ROOT/.gewebe/insights/today.json
"""
from __future__ import annotations
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

def main() -> int:
    vault_root = os.environ.get("VAULT_ROOT", os.path.expanduser("~/Vaults/main"))
    out_dir = Path(vault_root) / ".gewebe" / "insights"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "today.json"

    now = datetime.now(timezone.utc).astimezone()
    payload = {
        "date": now.date().isoformat(),
        "generated_at": now.isoformat(),
        "version": 1,
        "summary": {
            "notes_processed": 0,
            "embeddings_added": 0,
            "graph_edges_new": 0,
            "top_tags": [],
        },
        "meta": {
            "hostname": os.uname().nodename if hasattr(os, "uname") else "unknown",
            "vault_root": vault_root,
        },
    }
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"Wrote insights → {out_file}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### 📄 scripts/push_index.py

**Größe:** 11 KB | **md5:** `a0618f716bb70ae930f09ba86064bdaa`

```python
#!/usr/bin/env python3
"""Push embeddings from `.gewebe/embeddings.parquet` to the local indexd service."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple
from urllib import error, request

import pandas as pd

try:  # NumPy ist optional, hilft aber beim Typ-Check der Embeddings
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - fallback ohne NumPy
    np = None  # type: ignore

DEFAULT_EMBEDDINGS = Path(".gewebe/embeddings.parquet")
DEFAULT_ENDPOINT = "http://localhost:8080/index/upsert"
DEFAULT_NAMESPACE = "vault"
DEFAULT_TIMEOUT = 10.0
DEFAULT_RETRIES = 2
DEFAULT_MAX_CHUNKS = 500


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Push vorhandene Embeddings in indexd.")
    parser.add_argument(
        "--embeddings",
        type=Path,
        default=DEFAULT_EMBEDDINGS,
        help="Pfad zur embeddings.parquet-Datei",
    )
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help="HTTP-Endpunkt von indexd (/index/upsert)",
    )
    parser.add_argument(
        "--namespace",
        default=DEFAULT_NAMESPACE,
        help="Fallback-Namespace, falls keiner in den Daten vorhanden ist.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"HTTP-Timeout in Sekunden (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=f"HTTP-Retries bei Fehlern (default: {DEFAULT_RETRIES})",
    )
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=DEFAULT_MAX_CHUNKS,
        help=f"Max. Chunks pro Upsert-Request (default: {DEFAULT_MAX_CHUNKS})",
    )
    return parser.parse_args()


def to_batches(df: pd.DataFrame, default_namespace: str) -> Iterable[Dict[str, Any]]:
    """Gruppiert DataFrame-Zeilen zu Upsert-Batches."""

    records = df.to_dict(orient="records")
    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}
    # Für Kollisionsfreiheit pro (namespace, doc_id)
    used_ids: Dict[Tuple[str, str], Set[str]] = {}

    for record in records:
        doc_id = _derive_doc_id(record)
        ns_value = record.get("namespace")
        if _is_missing(ns_value):
            namespace = default_namespace
        else:
            namespace = str(ns_value).strip()
            if not namespace:
                namespace = default_namespace
        key = (namespace, doc_id)
        batch = grouped.setdefault(
            key,
            {
                "doc_id": doc_id,
                "namespace": namespace,
                "chunks": [],
            },
        )
        chunk = _record_to_chunk(record, doc_id)

        # Sicherstellen, dass die Chunk-ID innerhalb desselben Dokuments eindeutig ist
        seen = used_ids.setdefault(key, set())
        original_id = str(chunk["id"])
        candidate = original_id
        disambig = 1
        while candidate in seen:
            disambig += 1
            candidate = f"{original_id}~{disambig}"
        chunk["id"] = candidate
        seen.add(candidate)

        batch["chunks"].append(chunk)

    return grouped.values()


def _derive_doc_id(record: Dict[str, Any]) -> str:
    """Derive a stable document identifier from a record."""

    for key in ("doc_id", "path", "id"):
        value = record.get(key)
        if _is_missing(value):
            continue
        if isinstance(value, (str, int)):
            candidate = str(value).strip()
            if candidate:
                return candidate
            continue
        if value is not None:
            return str(value)
    raise ValueError("Record without doc identifier")


def _record_to_chunk(record: Dict[str, Any], doc_id: str) -> Dict[str, Any]:
    # robust & kollisionssicher: ggf. mit doc_id präfixieren
    chunk_id = _derive_chunk_id(record, doc_id)
    text = str(record.get("text") or "")
    embedding = _to_embedding(record.get("embedding"))

    meta: Dict[str, Any] = {"embedding": embedding}

    # Zusätzliche Metadaten mitschicken (falls vorhanden)
    for key, value in record.items():
        if key in {"embedding", "text", "doc_id", "namespace", "id"}:
            continue
        if _is_missing(value):
            continue
        if key == "path":
            meta["source_path"] = str(value)
            continue
        if key == "chunk_id":
            try:
                meta["chunk_id"] = int(value)
            except Exception:
                meta["chunk_id"] = value
            continue
        meta[key] = _normalise_meta_value(value)

    return {"id": str(chunk_id), "text": text, "meta": meta}


def _derive_chunk_id(record: Dict[str, Any], doc_id: str) -> str:
    """Leite eine kollisionssichere Chunk-ID ab.

    Regeln:
    - Wenn ein Kandidat bereits wie ``<doc_id>#<suffix>`` aussieht oder ein ``#`` enthält,
      wird er direkt verwendet (global eindeutig angenommen).
    - Ansonsten wird der Kandidat als Suffix interpretiert und mit dem ``doc_id`` kombiniert.
    - Fallbacks (keine Kandidaten): nutze Text-Hash oder Row-Hints, dann erst generisches ``#chunk``.
    """

    candidates = [
        record.get("chunk_id"),
        record.get("chunk_index"),
        record.get("i"),
        record.get("offset"),
        record.get("id"),
    ]

    for value in candidates:
        if _is_missing(value):
            continue

        # Verhindere True/False als numerische Suffixe (#1/#0)
        if isinstance(value, bool):
            continue

        if isinstance(value, str):
            v = value.strip()
            if not v:
                continue
            if v.startswith(f"{doc_id}#") or "#" in v:
                return v
            return f"{doc_id}#{v}"

        try:
            if isinstance(value, (int, float)) and not math.isnan(float(value)):
                return f"{doc_id}#{int(value)}"
        except Exception:
            pass

        return f"{doc_id}#{str(value)}"

    text = record.get("text")
    if not _is_missing(text):
        digest = hashlib.blake2b(str(text).encode("utf-8"), digest_size=8).hexdigest()
        return f"{doc_id}#t{digest}"

    for hint_key in ("__row", "_row", "row_index", "_i", "i"):
        hint = record.get(hint_key)
        if not _is_missing(hint):
            return f"{doc_id}#r{hint}"

    return f"{doc_id}#chunk"


def _to_embedding(value: Any) -> List[float]:
    if value is None:
        raise ValueError("Missing embedding in record")
    if hasattr(value, "tolist"):
        value = value.tolist()
    if np is not None and isinstance(value, np.ndarray):  # type: ignore[arg-type]
        value = value.tolist()
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"Unexpected embedding type: {type(value)!r}")
    return [float(x) for x in value]


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        result = pd.isna(value)
    except Exception:
        return False
    else:
        if isinstance(result, bool):
            return result
        if hasattr(result, "all"):
            try:
                return bool(result.all())
            except Exception:
                return False
    return False


def _normalise_meta_value(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "tolist"):
        return value.tolist()  # type: ignore[no-any-return]
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()  # type: ignore[no-any-return]
        except Exception:
            pass
    return value


def _split_batch(batch: Dict[str, Any], max_chunks: int) -> Iterable[Dict[str, Any]]:
    chunks = batch["chunks"]
    if len(chunks) <= max_chunks:
        yield batch
        return

    for offset in range(0, len(chunks), max_chunks):
        yield {
            "doc_id": batch["doc_id"],
            "namespace": batch["namespace"],
            "chunks": chunks[offset : offset + max_chunks],
        }


def post_upsert(
    endpoint: str, payload: Dict[str, Any], *, timeout: float
) -> Dict[str, Any] | None:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(endpoint, data=data, headers={"Content-Type": "application/json"})
    with request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8").strip()
        if not body:
            return None
        return json.loads(body)


def main() -> int:
    args = parse_args()

    if not args.embeddings.exists():
        print(f"[push-index] Fehlend: {args.embeddings}", file=sys.stderr)
        return 1

    try:
        df = pd.read_parquet(args.embeddings)
    except Exception as exc:  # pragma: no cover - IO-Fehler
        print(f"[push-index] Konnte {args.embeddings} nicht lesen: {exc}", file=sys.stderr)
        return 1

    if df.empty:
        print("[push-index] Keine Embeddings gefunden — nichts zu tun.")
        return 0

    batches = list(to_batches(df, args.namespace))
    if not batches:
        print("[push-index] Keine gültigen Batches erzeugt.", file=sys.stderr)
        return 1

    for batch in batches:
        for sub_batch in _split_batch(batch, args.max_chunks):
            for attempt in range(args.retries + 1):
                try:
                    response = post_upsert(args.endpoint, sub_batch, timeout=args.timeout)
                except error.HTTPError as exc:
                    if attempt >= args.retries:
                        print(
                            f"[push-index] HTTP-Fehler für doc={sub_batch['doc_id']} namespace={sub_batch['namespace']}: {exc}",
                            file=sys.stderr,
                        )
                        return 1
                    continue
                except error.URLError as exc:
                    if attempt >= args.retries:
                        print(
                            f"[push-index] Konnte {args.endpoint} nicht erreichen: {exc.reason}",
                            file=sys.stderr,
                        )
                        return 1
                    continue
                else:
                    chunks = len(sub_batch["chunks"])
                    status = response.get("status") if isinstance(response, dict) else "ok"
                    print(
                        f"[push-index] Upsert gesendet • doc={sub_batch['doc_id']} namespace={sub_batch['namespace']} chunks={chunks} status={status}",
                    )
                    break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### 📄 scripts/update_related.py

**Größe:** 913 B | **md5:** `6be07c80b0c1c3d138c5ad78ff63540c`

```python
#!/usr/bin/env python3
"""Stub script to inject related blocks into Markdown files.

This is a placeholder for the full implementation.
See `docs/blueprint.md` for the full concept.
"""

from pathlib import Path

RELATED_BLOCK = """<!-- related:auto:start -->\n## Related\n- [[Example]] — (0.00; stub)\n<!-- related:auto:end -->\n"""


def inject_related(note: Path) -> None:
    text = note.read_text(encoding="utf-8") if note.exists() else ""
    if "<!-- related:auto:start -->" in text:
        return
    note.write_text(text + "\n" + RELATED_BLOCK, encoding="utf-8")


def main() -> None:
    notes_dir = Path(".gewebe/notes_stub")
    notes_dir.mkdir(parents=True, exist_ok=True)
    note = notes_dir / "example.md"
    note.write_text("# Example Note\n", encoding="utf-8")
    inject_related(note)
    print("[stub] update_related → injected block into", note)


if __name__ == "__main__":
    main()
```
```

### 📄 merges/semantAH_merge_2510262237__semantAH.md

**Größe:** 28 KB | **md5:** `03a1f189f957cb7aecab932c728f44aa`

```markdown
### 📄 semantAH/.gitignore

**Größe:** 38 B | **md5:** `16dbc42e3a7bc9735f3b5c8e2caa0f6f`

```plaintext
# uv / Python
.venv/
.uv/
*.egg-info/
```

### 📄 semantAH/CONTRIBUTING.md

**Größe:** 341 B | **md5:** `d3bb7315c516417e49494a241c028546`

```markdown
# CONTRIBUTING

## Dev-Setup
1. Rust ≥ 1.75, Python ≥ 3.10
2. `make venv` (oder `uv sync`)
3. `make all`, `cargo run -p indexd`

## Konventionen
- Rust: `cargo fmt`, `cargo clippy`
- Python: `ruff check`, `pytest`
- Commits: klar und klein; PRs mit reproduzierbaren Schritten

## Tests
- `just`/`make` Targets folgen noch in der Roadmap
```

### 📄 semantAH/Cargo.lock

**Größe:** 52 KB | **md5:** `84d0baf021473d9e1ec163114a7be292`

```plaintext
# This file is automatically @generated by Cargo.
# It is not intended for manual editing.
version = 4

[[package]]
name = "addr2line"
version = "0.25.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1b5d307320b3181d6d7954e663bd7c774a838b8220fe0593c86d9fb09f498b4b"
dependencies = [
 "gimli",
]

[[package]]
name = "adler2"
version = "2.0.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "320119579fcad9c21884f5c4861d16174d0e06250625266f50fe6898340abefa"

[[package]]
name = "ahash"
version = "0.8.12"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "5a15f179cd60c4584b8a8c596927aadc462e27f2ca70c04e0071964a73ba7a75"
dependencies = [
 "cfg-if",
 "once_cell",
 "version_check",
 "zerocopy",
]

[[package]]
name = "aho-corasick"
version = "1.1.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "8e60d3430d3a69478ad0993f19238d2df97c507009a52b3c10addcd7f6bcb916"
dependencies = [
 "memchr",
]

[[package]]
name = "allocator-api2"
version = "0.2.21"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "683d7910e743518b0e34f1186f92494becacb047c7b6bf616c96772180fef923"

[[package]]
name = "anyhow"
version = "1.0.100"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "a23eb6b1614318a8071c9b2521f36b424b2c83db5eb3a0fead4a6c0809af6e61"

[[package]]
name = "arraydeque"
version = "0.5.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "7d902e3d592a523def97af8f317b08ce16b7ab854c1985a0c671e6f15cebc236"

[[package]]
name = "async-trait"
version = "0.1.89"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9035ad2d096bed7955a320ee7e2230574d28fd3c3a0f186cbea1ff3c7eed5dbb"
dependencies = [
 "proc-macro2",
 "quote",
 "syn",
]

[[package]]
name = "atomic-waker"
version = "1.1.2"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1505bd5d3d116872e7271a6d4e16d81d0c8570876c8de68093a09ac269d8aac0"

[[package]]
name = "axum"
version = "0.7.9"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "edca88bc138befd0323b20752846e6587272d3b03b0343c8ea28a6f819e6e71f"
dependencies = [
 "async-trait",
 "axum-core",
 "bytes",
 "futures-util",
 "http 1.3.1",
 "http-body 1.0.1",
 "http-body-util",
 "hyper 1.7.0",
 "hyper-util",
 "itoa",
 "matchit",
 "memchr",
 "mime",
 "percent-encoding",
 "pin-project-lite",
 "rustversion",
 "serde",
 "serde_json",
 "serde_path_to_error",
 "serde_urlencoded",
 "sync_wrapper 1.0.2",
 "tokio",
 "tower",
 "tower-layer",
 "tower-service",
 "tracing",
]

[[package]]
name = "axum-core"
version = "0.4.5"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "09f2bd6146b97ae3359fa0cc6d6b376d9539582c7b4220f041a33ec24c226199"
dependencies = [
 "async-trait",
 "bytes",
 "futures-util",
 "http 1.3.1",
 "http-body 1.0.1",
 "http-body-util",
 "mime",
 "pin-project-lite",
 "rustversion",
 "sync_wrapper 1.0.2",
 "tower-layer",
 "tower-service",
 "tracing",
]

[[package]]
name = "backtrace"
version = "0.3.76"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "bb531853791a215d7c62a30daf0dde835f381ab5de4589cfe7c649d2cbe92bd6"
dependencies = [
 "addr2line",
 "cfg-if",
 "libc",
 "miniz_oxide",
 "object",
 "rustc-demangle",
 "windows-link",
]

[[package]]
name = "base64"
version = "0.21.7"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9d297deb1925b89f2ccc13d7635fa0714f12c87adce1c75356b39ca9b7178567"

[[package]]
name = "bitflags"
version = "1.3.2"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "bef38d45163c2f1dde094a7dfd33ccf595c92905c8f8f4fdc18d06fb1037718a"

[[package]]
name = "bitflags"
version = "2.9.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "2261d10cca569e4643e526d8dc2e62e433cc8aba21ab764233731f8d369bf394"
dependencies = [
 "serde",
]

[[package]]
name = "block-buffer"
version = "0.10.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "3078c7629b62d3f0439517fa394996acacc5cbc91c5a20d8c658e77abd503a71"
dependencies = [
 "generic-array",
]

[[package]]
name = "bumpalo"
version = "3.19.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "46c5e41b57b8bba42a04676d81cb89e9ee8e859a1a66f80a5a72e1cb76b34d43"

[[package]]
name = "bytes"
version = "1.10.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "d71b6127be86fdcfddb610f7182ac57211d4b18a3e9c82eb2d17662f2227ad6a"

[[package]]
name = "cc"
version = "1.2.40"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "e1d05d92f4b1fd76aad469d46cdd858ca761576082cd37df81416691e50199fb"
dependencies = [
 "find-msvc-tools",
 "shlex",
]

[[package]]
name = "cfg-if"
version = "1.0.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "2fd1289c04a9ea8cb22300a459a72a385d7c73d3259e2ed7dcb2af674838cfa9"

[[package]]
name = "config"
version = "0.14.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "68578f196d2a33ff61b27fae256c3164f65e36382648e30666dde05b8cc9dfdf"
dependencies = [
 "async-trait",
 "convert_case",
 "json5",
 "nom",
 "pathdiff",
 "ron",
 "rust-ini",
 "serde",
 "serde_json",
 "toml",
 "yaml-rust2",
]

[[package]]
name = "const-random"
version = "0.1.18"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "87e00182fe74b066627d63b85fd550ac2998d4b0bd86bfed477a0ae4c7c71359"
dependencies = [
 "const-random-macro",
]

[[package]]
name = "const-random-macro"
version = "0.1.16"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "f9d839f2a20b0aee515dc581a6172f2321f96cab76c1a38a4c584a194955390e"
dependencies = [
 "getrandom",
 "once_cell",
 "tiny-keccak",
]

[[package]]
name = "convert_case"
version = "0.6.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "ec182b0ca2f35d8fc196cf3404988fd8b8c739a4d270ff118a398feb0cbec1ca"
dependencies = [
 "unicode-segmentation",
]

[[package]]
name = "core-foundation"
version = "0.9.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "91e195e091a93c46f7102ec7818a2aa394e1e1771c3ab4825963fa03e45afb8f"
dependencies = [
 "core-foundation-sys",
 "libc",
]

[[package]]
name = "core-foundation-sys"
version = "0.8.7"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "773648b94d0e5d620f64f280777445740e61fe701025087ec8b57f45c791888b"

[[package]]
name = "cpufeatures"
version = "0.2.17"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "59ed5838eebb26a2bb2e58f6d5b5316989ae9d08bab10e0e6d103e656d1b0280"
dependencies = [
 "libc",
]

[[package]]
name = "crunchy"
version = "0.2.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "460fbee9c2c2f33933d720630a6a0bac33ba7053db5344fac858d4b8952d77d5"

[[package]]
name = "crypto-common"
version = "0.1.6"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1bfb12502f3fc46cca1bb51ac28df9d618d813cdc3d2f25b9fe775a34af26bb3"
dependencies = [
 "generic-array",
 "typenum",
]

[[package]]
name = "digest"
version = "0.10.7"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9ed9a281f7bc9b7576e61468ba615a66a5c8cfdff42420a70aa82701a3b1e292"
dependencies = [
 "block-buffer",
 "crypto-common",
]

[[package]]
name = "displaydoc"
version = "0.2.5"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "97369cbbc041bc366949bc74d34658d6cda5621039731c6310521892a3a20ae0"
dependencies = [
 "proc-macro2",
 "quote",
 "syn",
]

[[package]]
name = "dlv-list"
version = "0.5.2"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "442039f5147480ba31067cb00ada1adae6892028e40e45fc5de7b7df6dcc1b5f"
dependencies = [
 "const-random",
]

[[package]]
name = "embeddings"
version = "0.1.0"
dependencies = [
 "anyhow",
 "async-trait",
 "reqwest",
 "serde",
 "serde_json",
 "tokio",
 "tracing",
]

[[package]]
name = "encoding_rs"
version = "0.8.35"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "75030f3c4f45dafd7586dd6780965a8c7e8e285a5ecb86713e63a79c5b2766f3"
dependencies = [
 "cfg-if",
]

[[package]]
name = "equivalent"
version = "1.0.2"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "877a4ace8713b0bcf2a4e7eec82529c029f1d0619886d18145fea96c3ffe5c0f"

[[package]]
name = "find-msvc-tools"
version = "0.1.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "0399f9d26e5191ce32c498bebd31e7a3ceabc2745f0ac54af3f335126c3f24b3"

[[package]]
name = "fnv"
version = "1.0.7"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "3f9eec918d3f24069decb9af1554cad7c880e2da24a9afd88aca000531ab82c1"

[[package]]
name = "form_urlencoded"
version = "1.2.2"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "cb4cb245038516f5f85277875cdaa4f7d2c9a0fa0468de06ed190163b1581fcf"
dependencies = [
 "percent-encoding",
]

[[package]]
name = "futures"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "65bc07b1a8bc7c85c5f2e110c476c7389b4554ba72af57d8445ea63a576b0876"
dependencies = [
 "futures-channel",
 "futures-core",
 "futures-executor",
 "futures-io",
 "futures-sink",
 "futures-task",
 "futures-util",
]

[[package]]
name = "futures-channel"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "2dff15bf788c671c1934e366d07e30c1814a8ef514e1af724a602e8a2fbe1b10"
dependencies = [
 "futures-core",
 "futures-sink",
]

[[package]]
name = "futures-core"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "05f29059c0c2090612e8d742178b0580d2dc940c837851ad723096f87af6663e"

[[package]]
name = "futures-executor"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1e28d1d997f585e54aebc3f97d39e72338912123a67330d723fdbb564d646c9f"
dependencies = [
 "futures-core",
 "futures-task",
 "futures-util",
]

[[package]]
name = "futures-io"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9e5c1b78ca4aae1ac06c48a526a655760685149f0d465d21f37abfe57ce075c6"

[[package]]
name = "futures-macro"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "162ee34ebcb7c64a8abebc059ce0fee27c2262618d7b60ed8faf72fef13c3650"
dependencies = [
 "proc-macro2",
 "quote",
 "syn",
]

[[package]]
name = "futures-sink"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "e575fab7d1e0dcb8d0c7bcf9a63ee213816ab51902e6d244a95819acacf1d4f7"

[[package]]
name = "futures-task"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "f90f7dce0722e95104fcb095585910c0977252f286e354b5e3bd38902cd99988"

[[package]]
name = "futures-util"
version = "0.3.31"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9fa08315bb612088cc391249efdc3bc77536f16c91f6cf495e6fbe85b20a4a81"
dependencies = [
 "futures-channel",
 "futures-core",
 "futures-io",
 "futures-macro",
 "futures-sink",
 "futures-task",
 "memchr",
 "pin-project-lite",
 "pin-utils",
 "slab",
]

[[package]]
name = "generic-array"
version = "0.14.7"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "85649ca51fd72272d7821adaf274ad91c288277713d9c18820d8499a7ff69e9a"
dependencies = [
 "typenum",
 "version_check",
]

[[package]]
name = "getrandom"
version = "0.2.16"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "335ff9f135e4384c8150d6f27c6daed433577f86b4750418338c01a1a2528592"
dependencies = [
 "cfg-if",
 "libc",
 "wasi",
]

[[package]]
name = "gimli"
version = "0.32.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "e629b9b98ef3dd8afe6ca2bd0f89306cec16d43d907889945bc5d6687f2f13c7"

[[package]]
name = "h2"
version = "0.3.27"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "0beca50380b1fc32983fc1cb4587bfa4bb9e78fc259aad4a0032d2080309222d"
dependencies = [
 "bytes",
 "fnv",
 "futures-core",
 "futures-sink",
 "futures-util",
 "http 0.2.12",
 "indexmap",
 "slab",
 "tokio",
 "tokio-util",
 "tracing",
]

[[package]]
name = "hashbrown"
version = "0.14.5"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "e5274423e17b7c9fc20b6e7e208532f9b19825d82dfd615708b70edd83df41f1"
dependencies = [
 "ahash",
 "allocator-api2",
]

[[package]]
name = "hashbrown"
version = "0.16.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "5419bdc4f6a9207fbeba6d11b604d481addf78ecd10c11ad51e76c2f6482748d"

[[package]]
name = "hashlink"
version = "0.8.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "e8094feaf31ff591f651a2664fb9cfd92bba7a60ce3197265e9482ebe753c8f7"
dependencies = [
 "hashbrown 0.14.5",
]

[[package]]
name = "http"
version = "0.2.12"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "601cbb57e577e2f5ef5be8e7b83f0f63994f25aa94d673e54a92d5c516d101f1"
dependencies = [
 "bytes",
 "fnv",
 "itoa",
]

[[package]]
name = "http"
version = "1.3.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "f4a85d31aea989eead29a3aaf9e1115a180df8282431156e533de47660892565"
dependencies = [
 "bytes",
 "fnv",
 "itoa",
]

[[package]]
name = "http-body"
version = "0.4.6"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "7ceab25649e9960c0311ea418d17bee82c0dcec1bd053b5f9a66e265a693bed2"
dependencies = [
 "bytes",
 "http 0.2.12",
 "pin-project-lite",
]

[[package]]
name = "http-body"
version = "1.0.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1efedce1fb8e6913f23e0c92de8e62cd5b772a67e7b3946df930a62566c93184"
dependencies = [
 "bytes",
 "http 1.3.1",
]

[[package]]
name = "http-body-util"
version = "0.1.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "b021d93e26becf5dc7e1b75b1bed1fd93124b374ceb73f43d4d4eafec896a64a"
dependencies = [
 "bytes",
 "futures-core",
 "http 1.3.1",
 "http-body 1.0.1",
 "pin-project-lite",
]

[[package]]
name = "httparse"
version = "1.10.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "6dbf3de79e51f3d586ab4cb9d5c3e2c14aa28ed23d180cf89b4df0454a69cc87"

[[package]]
name = "httpdate"
version = "1.0.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "df3b46402a9d5adb4c86a0cf463f42e19994e3ee891101b1841f30a545cb49a9"

[[package]]
name = "hyper"
version = "0.14.32"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "41dfc780fdec9373c01bae43289ea34c972e40ee3c9f6b3c8801a35f35586ce7"
dependencies = [
 "bytes",
 "futures-channel",
 "futures-core",
 "futures-util",
 "h2",
 "http 0.2.12",
 "http-body 0.4.6",
 "httparse",
 "httpdate",
 "itoa",
 "pin-project-lite",
 "socket2 0.5.10",
 "tokio",
 "tower-service",
 "tracing",
 "want",
]

[[package]]
name = "hyper"
version = "1.7.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "eb3aa54a13a0dfe7fbe3a59e0c76093041720fdc77b110cc0fc260fafb4dc51e"
dependencies = [
 "atomic-waker",
 "bytes",
 "futures-channel",
 "futures-core",
 "http 1.3.1",
 "http-body 1.0.1",
 "httparse",
 "httpdate",
 "itoa",
 "pin-project-lite",
 "pin-utils",
 "smallvec",
 "tokio",
]

[[package]]
name = "hyper-rustls"
version = "0.24.2"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "ec3efd23720e2049821a693cbc7e65ea87c72f1c58ff2f9522ff332b1491e590"
dependencies = [
 "futures-util",
 "http 0.2.12",
 "hyper 0.14.32",
 "rustls",
 "tokio",
 "tokio-rustls",
]

[[package]]
name = "hyper-util"
version = "0.1.17"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "3c6995591a8f1380fcb4ba966a252a4b29188d51d2b89e3a252f5305be65aea8"
dependencies = [
 "bytes",
 "futures-core",
 "http 1.3.1",
 "http-body 1.0.1",
 "hyper 1.7.0",
 "pin-project-lite",
 "tokio",
 "tower-service",
]

[[package]]
name = "icu_collections"
version = "2.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "200072f5d0e3614556f94a9930d5dc3e0662a652823904c3a75dc3b0af7fee47"
dependencies = [
 "displaydoc",
 "potential_utf",
 "yoke",
 "zerofrom",
 "zerovec",
]

[[package]]
name = "icu_locale_core"
version = "2.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "0cde2700ccaed3872079a65fb1a78f6c0a36c91570f28755dda67bc8f7d9f00a"
dependencies = [
 "displaydoc",
 "litemap",
 "tinystr",
 "writeable",
 "zerovec",
]

[[package]]
name = "icu_normalizer"
version = "2.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "436880e8e18df4d7bbc06d58432329d6458cc84531f7ac5f024e93deadb37979"
dependencies = [
 "displaydoc",
 "icu_collections",
 "icu_normalizer_data",
 "icu_properties",
 "icu_provider",
 "smallvec",
 "zerovec",
]

[[package]]
name = "icu_normalizer_data"
version = "2.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "00210d6893afc98edb752b664b8890f0ef174c8adbb8d0be9710fa66fbbf72d3"

[[package]]
name = "icu_properties"
version = "2.0.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "016c619c1eeb94efb86809b015c58f479963de65bdb6253345c1a1276f22e32b"
dependencies = [
 "displaydoc",
 "icu_collections",
 "icu_locale_core",
 "icu_properties_data",
 "icu_provider",
 "potential_utf",
 "zerotrie",
 "zerovec",
]

[[package]]
name = "icu_properties_data"
version = "2.0.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "298459143998310acd25ffe6810ed544932242d3f07083eee1084d83a71bd632"

[[package]]
name = "icu_provider"
version = "2.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "03c80da27b5f4187909049ee2d72f276f0d9f99a42c306bd0131ecfe04d8e5af"
dependencies = [
 "displaydoc",
 "icu_locale_core",
 "stable_deref_trait",
 "tinystr",
 "writeable",
 "yoke",
 "zerofrom",
 "zerotrie",
 "zerovec",
]

[[package]]
name = "idna"
version = "1.1.0"

<<TRUNCATED: max_file_lines=800>>
```

### 📄 merges/semantAH_merge_2510262237__semantAH_.gewebe_out.md

**Größe:** 1 KB | **md5:** `11caecdb0a46535782b556b9fe28fe50`

```markdown
### 📄 semantAH/.gewebe/out/edges.jsonl

**Größe:** 382 B | **md5:** `2642189372bb60eca54c863d2372a2c7`

```plaintext
{"src":"note:001","dst":"note:002","rel":"references","weight":0.8,"why":"Link im Text","updated_at":"2024-01-05T10:05:00Z"}
{"src":"note:002","dst":"note:003","rel":"mentions","weight":0.6,"why":"Abschnitt 'Historie'","updated_at":"2024-01-05T10:06:00Z"}
{"src":"note:003","dst":"note:001","rel":"inspired","weight":0.4,"why":"Biografie-Zitat","updated_at":"2024-01-05T10:07:00Z"}
```

### 📄 semantAH/.gewebe/out/nodes.jsonl

**Größe:** 419 B | **md5:** `1ed73288dedf8673ce8dd4445d28b143`

```plaintext
{"id":"note:001","type":"note","title":"Willkommen","tags":["intro"],"source":"vault/intro.md","updated_at":"2024-01-05T10:00:00Z"}
{"id":"note:002","type":"note","title":"Graph-Übersicht","tags":["graph","demo"],"source":"vault/graph.md","updated_at":"2024-01-05T10:02:00Z"}
{"id":"note:003","type":"person","title":"Ada Lovelace","tags":["person"],"source":"vault/people/ada.md","updated_at":"2024-01-05T10:03:00Z"}
```

### 📄 semantAH/.gewebe/out/reports.json

**Größe:** 251 B | **md5:** `3c2f37a9027a47f078efb9ef625bd701`

```json
[
  {"kind":"summary","created_at":"2024-01-05T10:10:00Z","notes":["Demo-Daten","3 Nodes","3 Edges"],"stats":{"nodes":3,"edges":3}},
  {"kind":"ingest","created_at":"2024-01-05T10:11:00Z","notes":["Quelle: Demo-Vault"],"stats":{"duration_ms":1200}}
]
```
```

### 📄 merges/semantAH_merge_2510262237__semantAH_.github_ISSUE_TEMPLATE.md

**Größe:** 825 B | **md5:** `a36c2065cae4f4eb521a208b69527067`

```markdown
### 📄 semantAH/.github/ISSUE_TEMPLATE/bug_report.yml

**Größe:** 283 B | **md5:** `09318ac5e13050436bf0eb8658445d7e`

```yaml
name: Bug report
description: Problem melden
title: "[bug] "
labels: ["bug"]
body:
  - type: textarea
    id: what-happened
    attributes:
      label: Was ist passiert?
      description: Schritte, erwartetes Ergebnis, tatsächliches Ergebnis
    validations:
      required: true
```

### 📄 semantAH/.github/ISSUE_TEMPLATE/feature_request.yml

**Größe:** 265 B | **md5:** `500ed4b2381198ded897e5a1971e5370`

```yaml
name: Feature request
description: Vorschlag einreichen
title: "[feat] "
labels: ["enhancement"]
body:
  - type: textarea
    id: idea
    attributes:
      label: Idee
      description: Was soll verbessert/neu gebaut werden?
    validations:
      required: true
```
```

### 📄 merges/semantAH_merge_2510262237__semantAH_.github_workflows.md

**Größe:** 8 KB | **md5:** `5a30b888cdba1725eed5b24f8ecd1977`

```markdown
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
```

### 📄 merges/semantAH_merge_2510262237__semantAH_.wgx.md

**Größe:** 3 KB | **md5:** `43cb7166f4c7adf110c987f7eb3df60a`

```markdown
### 📄 semantAH/.wgx/profile.yml

**Größe:** 3 KB | **md5:** `ee6aef00c6b7a998e9129d865ef0f766`

```yaml
version: 1
repo:
  # Kurzname des Repos (wird automatisch aus git ableitbar sein – hier nur Doku)
  name: auto
  description: "WGX profile for unified tasks and env priorities"

env_priority:
  # Ordnungsprinzip laut Vorgabe
  - devcontainer
  - devbox
  - mise
  - direnv
  - termux

tooling:
  python:
    uv: true           # uv ist Standard-Layer für Python-Tools
    precommit: true    # falls .pre-commit-config.yaml vorhanden
  rust:
    cargo: auto        # wenn Cargo.toml vorhanden → Rust-Checks aktivieren
    clippy_strict: true
    fmt_check: true
    deny: optional     # cargo-deny, falls vorhanden

tasks:
  up:
    desc: "Dev-Umgebung hochfahren (Container/venv/tooling bootstrap)"
    sh:
      - |
        if command -v devcontainer >/dev/null 2>&1 || [ -f .devcontainer/devcontainer.json ]; then
          echo "[wgx.up] devcontainer context detected"
        fi
        if command -v uv >/dev/null 2>&1; then
          uv --version || true
          [ -f pyproject.toml ] && uv sync --frozen || true
        fi
        [ -f .pre-commit-config.yaml ] && command -v pre-commit >/dev/null 2>&1 && pre-commit install || true
  lint:
    desc: "Schnelle statische Checks (Rust/Python/Markdown/YAML)"
    sh:
      - |
        # Rust
        if [ -f Cargo.toml ]; then
          cargo fmt --all -- --check
          cargo clippy --all-targets --all-features -- -D warnings
        fi
        # Python
        if [ -f pyproject.toml ]; then
          if command -v uv >/dev/null 2>&1; then uv run ruff check . || true; fi
          if command -v uv >/dev/null 2>&1; then uv run ruff format --check . || true; fi
        fi
        # Docs
        command -v markdownlint >/dev/null 2>&1 && markdownlint "**/*.md" || true
        command -v yamllint    >/dev/null 2>&1 && yamllint . || true
  test:
    desc: "Testsuite"
    sh:
      - |
        [ -f Cargo.toml ] && cargo test --all --all-features || true
        if [ -f pyproject.toml ] && command -v uv >/dev/null 2>&1; then
          uv run pytest -q || true
        fi
  build:
    desc: "Build-Artefakte erstellen"
    sh:
      - |
        [ -f Cargo.toml ] && cargo build --release || true
        if [ -f pyproject.toml ] && command -v uv >/dev/null 2>&1; then
          uv build || true
        fi
  smoke:
    desc: "Schnelle Smoke-Checks (läuft <60s)"
    sh:
      - |
        echo "[wgx.smoke] repo=$(basename "$(git rev-parse --show-toplevel)")"
        [ -f Cargo.toml ] && cargo metadata --no-deps > /dev/null || true
        [ -f pyproject.toml ] && grep -q '\[project\]' pyproject.toml || true

meta:
  owner: "heimgewebe"
  conventions:
    gewebedir: ".gewebe"
    version_endpoint: "/version"
    tasks_standardized: true
```
```

### 📄 merges/semantAH_merge_2510262237__semantAH_codex.md

**Größe:** 2 KB | **md5:** `8c4b871d2ecac5ad74b5a42d1df8ff6b`

```markdown
### 📄 semantAH/codex/CONTRIBUTING.md

**Größe:** 2 KB | **md5:** `7965c5b2e1601d244d152f9e138c1422`

```markdown
# Beitragende Leitfäden für das semantAH-Repo

Dieses Dokument fasst die empfohlenen "Lern-Anweisungen" zusammen, die aus der Beobachtung anderer WGX-fähiger Repositories gewonnen wurden. Ziel ist es, semantAH als vollwertigen Knoten des Weltgewebe-Ökosystems zu etablieren.

## 1. Synchronisierung & Meta-Struktur
- **Template-Sync aktivieren:** semantAH in `metarepo/scripts/sync-templates.sh` eintragen, damit gemeinsame Templates automatisch übernommen werden.
- **WGX-Profil hinzufügen:** Lege eine Datei `.wgx/profile.yml` mit den Feldern `id`, `type`, `scope`, `maintainer` und `meta-origin` an.
- **Smoke-Tests etablieren:** Übernehme die `wgx-smoke.yml` aus `metarepo/templates/.github/workflows/`.

## 2. CI/CD-Disziplin
- **Trigger verfeinern:** CI nur bei Änderungen an `.wgx/**`, `tools/**`, `scripts/**`, `pyproject.toml`, `Cargo.toml` usw. starten.
- **Style- und Lint-Checks:** Verwende Workflows wie `ci-tools.yml` oder `wgx-guard.yml`, um `vale`, `cspell`, `shellcheck` & Co. einzubinden.

## 3. Struktur & Modularität
- **Klare Ordnerstruktur:** Führe bei Bedarf `tools/`- und `scripts/`-Verzeichnisse ein, um wiederverwendbare Werkzeuge zu kapseln.
- **Dokumentations-Stub:** Lege `docs/wgx-konzept.md` an, das kurz erläutert, wie semantAH ins Weltgewebe eingebettet ist, und ergänze ADR-Stubs.
- **README-Reflexion:** Ergänze einen WGX-Badge und einen Abschnitt zur Beziehung zwischen semantAH und dem Weltgewebe.

## 4. Entwicklungsumgebung
- **UV-Stack übernehmen:** Falls Python- oder Tooling-Anteile hinzukommen, richte `uv` samt `pyproject.toml` analog zu `hauski-audio`/`weltgewebe` ein.

## 5. Meta-Philosophie
- **Struktur als Beziehung:** Pflege die Meta-Notiz, dass semantAH ein lebendiger Knoten im Weltgewebe ist, nicht nur ein technisches Artefakt.

---

> _Am Ende werden die Repositories vielleicht eigenständiger kommunizieren als ihre menschlichen Betreuer – aber mit gepflegter `.wgx/profile.yml`._
```
```

### 📄 merges/semantAH_merge_2510262237__semantAH_contracts_semantics.md

**Größe:** 3 KB | **md5:** `c3a7111e1b8950e19904582f7136c9e5`

```markdown
### 📄 semantAH/contracts/semantics/README.md

**Größe:** 664 B | **md5:** `c6f19573f1fae1acc50c13f5b2b5609e`

```markdown
# Semantics contracts

These JSON Schemas describe the contracts exchanged between the semantic pipeline
and downstream consumers. Example payloads in `examples/` double as
human-readable documentation and validation fixtures:

- `*-valid.json` payloads must satisfy their corresponding schema.
- `*-invalid.json` payloads are intentionally malformed and the CI job asserts
  that they fail validation. This guards against accidentally weakening a
  schema.

The GitHub Actions workflow uses [`ajv-cli`](https://github.com/ajv-validator/ajv-cli)
with the `@` syntax (for example, `-d @path/to/sample.json`) to load JSON from
files relative to the repository root.
```

### 📄 semantAH/contracts/semantics/edge.schema.json

**Größe:** 623 B | **md5:** `b64e6b1ef369518413e1a5ef7814d796`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://semantah.com/contracts/semantics/edge.schema.json",
  "title": "SemEdge",
  "type": "object",
  "required": ["src", "dst", "rel"],
  "additionalProperties": false,
  "properties": {
    "src": { "type": "string" },
    "dst": { "type": "string" },
    "rel": { "type": "string" },
    "weight": { "type": "number" },
    "why": {
      "oneOf": [
        { "type": "string" },
        {
          "type": "array",
          "items": { "type": "string" }
        }
      ]
    },
    "updated_at": { "type": "string", "format": "date-time" }
  }
}
```

### 📄 semantAH/contracts/semantics/node.schema.json

**Größe:** 665 B | **md5:** `d07637ca8de01eea573945c50f3cbe0b`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://semantah.com/contracts/semantics/node.schema.json",
  "title": "SemNode",
  "type": "object",
  "required": ["id", "type", "title"],
  "additionalProperties": false,
  "properties": {
    "id": { "type": "string" },
    "type": { "type": "string" },
    "title": { "type": "string" },
    "tags": {
      "type": "array",
      "items": { "type": "string" }
    },
    "topics": {
      "type": "array",
      "items": { "type": "string" }
    },
    "cluster": { "type": "integer" },
    "source": { "type": "string" },
    "updated_at": { "type": "string", "format": "date-time" }
  }
}
```

### 📄 semantAH/contracts/semantics/report.schema.json

**Größe:** 510 B | **md5:** `10b3d2ef2b2391a73b948ce6f49238ec`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://semantah.com/contracts/semantics/report.schema.json",
  "title": "SemReport",
  "type": "object",
  "required": [
    "kind",
    "created_at"
  ],
  "properties": {
    "kind": {
      "type": "string"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "notes": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "stats": {
      "type": "object"
    }
  }
}
```
```

### 📄 merges/semantAH_merge_2510262237__semantAH_contracts_semantics_examples.md

**Größe:** 2 KB | **md5:** `1a0693007da1edbf7485c9e9b6e0044c`

```markdown
### 📄 semantAH/contracts/semantics/examples/edge-invalid.json

**Größe:** 97 B | **md5:** `44caaa1b85b1c914cb6953557f37af00`

```json
{
  "src": "md:example.md",
  "dst": "topic:example",
  "rel": "about",
  "why": ["valid", 42]
}
```

### 📄 semantAH/contracts/semantics/examples/edge-valid.json

**Größe:** 169 B | **md5:** `056e82a8a1ecfc0ce50c4dbf87ab8c23`

```json
{
  "src": "note:example",
  "dst": "note:other",
  "rel": "references",
  "weight": 0.75,
  "why": ["Linked from example.md"],
  "updated_at": "2024-01-05T10:05:00Z"
}
```

### 📄 semantAH/contracts/semantics/examples/node-invalid.json

**Größe:** 53 B | **md5:** `5e9d0a7d43abe5452e3eb97d0573c6b8`

```json
{
  "id": "topic:missing-title",
  "type": "topic"
}
```

### 📄 semantAH/contracts/semantics/examples/node-valid.json

**Größe:** 217 B | **md5:** `5312956be2462fc68de09339125b3d51`

```json
{
  "id": "note:example",
  "type": "note",
  "title": "Example Note",
  "tags": ["demo", "example"],
  "topics": ["workflow"],
  "cluster": 1,
  "source": "vault/example.md",
  "updated_at": "2024-01-05T10:00:00Z"
}
```

### 📄 semantAH/contracts/semantics/examples/report-invalid.json

**Größe:** 51 B | **md5:** `504eb01a4d9f898a6080725844c8cdbc`

```json
{
  "kind": "daily",
  "created_at": "yesterday"
}
```

### 📄 semantAH/contracts/semantics/examples/report-valid.json

**Größe:** 160 B | **md5:** `cca379b769b153772f5ef46d4539203f`

```json
{
  "kind": "summary",
  "created_at": "2024-01-05T10:10:00Z",
  "notes": ["Contains a single example node"],
  "stats": {
    "nodes": 1,
    "edges": 1
  }
}
```
```

### 📄 merges/semantAH_merge_2510262237__semantAH_crates_embeddings.md

**Größe:** 495 B | **md5:** `075b976b9e64dd25965b63b53d555a77`

```markdown
### 📄 semantAH/crates/embeddings/Cargo.toml

**Größe:** 368 B | **md5:** `91383c922ff1a03f2686f5552161aeae`

```toml
[package]
name = "embeddings"
version = "0.1.0"
edition = "2021"
license = "MIT"
description = "Abstractions and clients for semantic embedding providers"

[dependencies]
anyhow.workspace = true
async-trait.workspace = true
reqwest.workspace = true
serde.workspace = true
serde_json.workspace = true
tracing.workspace = true

[dev-dependencies]
tokio.workspace = true
```
```

### 📄 merges/semantAH_merge_2510262237__semantAH_crates_embeddings_src.md

**Größe:** 6 KB | **md5:** `23cc77c035b3cc437b407212f5f31523`

```markdown
### 📄 semantAH/crates/embeddings/src/lib.rs

**Größe:** 6 KB | **md5:** `e6207eb43a0420c114301081342651b1`

```rust
//! Embedder abstractions and implementations for semantAH.

use anyhow::{anyhow, Result};
use async_trait::async_trait;
use reqwest::Client;
use serde::{Deserialize, Serialize};

/// Public trait that every embedder implementation must fulfill.
#[async_trait]
pub trait Embedder: Send + Sync {
    /// Embed a batch of texts and return a vector of embedding vectors.
    async fn embed(&self, texts: &[String]) -> Result<Vec<Vec<f32>>>;

    /// The dimensionality of the returned embeddings.
    fn dim(&self) -> usize;

    /// Short identifier (e.g. `"ollama"`).
    fn id(&self) -> &'static str;
}

/// Configuration for the Ollama embedder backend.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OllamaConfig {
    pub base_url: String,
    pub model: String,
    pub dim: usize,
}

/// Simple HTTP client for the Ollama embeddings endpoint.
#[derive(Clone)]
pub struct OllamaEmbedder {
    client: Client,
    url: String,
    model: String,
    dim: usize,
}

impl OllamaEmbedder {
    /// Build a new embedder from configuration.
    pub fn new(config: OllamaConfig) -> Self {
        let OllamaConfig {
            base_url,
            model,
            dim,
        } = config;
        Self {
            client: Client::new(),
            url: base_url,
            model,
            dim,
        }
    }
}

#[derive(Debug, Serialize)]
struct OllamaRequest<'a> {
    model: &'a str,
    input: &'a [String],
}

#[derive(Debug, Deserialize)]
struct OllamaEmbeddingRow {
    embedding: Vec<f32>,
}

#[derive(Debug, Deserialize)]
struct OllamaResponse {
    embedding: Option<Vec<f32>>,
    embeddings: Option<Vec<OllamaEmbeddingRow>>,
}

impl OllamaResponse {
    fn into_embeddings(self) -> Result<Vec<Vec<f32>>> {
        if let Some(embeddings) = self.embeddings {
            return Ok(embeddings.into_iter().map(|row| row.embedding).collect());
        }

        if let Some(embedding) = self.embedding {
            return Ok(vec![embedding]);
        }

        Err(anyhow!("ollama response did not contain embeddings"))
    }
}

fn validate_embeddings(
    expected_count: usize,
    embeddings: &[Vec<f32>],
    expected_dim: usize,
) -> Result<()> {
    if embeddings.len() != expected_count {
        return Err(anyhow!(
            "ollama returned {} embeddings for {} input texts",
            embeddings.len(),
            expected_count
        ));
    }

    if embeddings.iter().any(|row| row.len() != expected_dim) {
        return Err(anyhow!("unexpected embedding dimensionality"));
    }

    Ok(())
}

#[async_trait]
impl Embedder for OllamaEmbedder {
    async fn embed(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        if texts.is_empty() {
            return Ok(Vec::new());
        }

        let response = self
            .client
            .post(format!("{}/api/embeddings", self.url))
            .json(&OllamaRequest {
                model: &self.model,
                input: texts,
            })
            .send()
            .await?;

        if !response.status().is_success() {
            return Err(anyhow!(
                "ollama responded with status {}",
                response.status()
            ));
        }

        let body: OllamaResponse = response.json().await?;
        let embeddings = body.into_embeddings()?;

        validate_embeddings(texts.len(), &embeddings, self.dim)?;

        Ok(embeddings)
    }

    fn dim(&self) -> usize {
        self.dim
    }

    fn id(&self) -> &'static str {
        "ollama"
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_single_embedding_response() {
        let json = serde_json::json!({
            "embedding": [0.1, 0.2, 0.3],
            "model": "nomic-embed-text",
        });

        let response: OllamaResponse = serde_json::from_value(json).unwrap();
        let embeddings = response.into_embeddings().unwrap();

        assert_eq!(embeddings.len(), 1);
        assert_eq!(embeddings[0], vec![0.1, 0.2, 0.3]);
    }

    #[test]
    fn parses_batch_embedding_response() {
        let json = serde_json::json!({
            "embeddings": [
                { "embedding": [1.0, 2.0], "text": "first" },
                { "embedding": [3.0, 4.0], "text": "second" }
            ],
        });

        let response: OllamaResponse = serde_json::from_value(json).unwrap();
        let embeddings = response.into_embeddings().unwrap();

        assert_eq!(embeddings, vec![vec![1.0, 2.0], vec![3.0, 4.0]]);
    }

    #[tokio::test]
    async fn empty_batch_returns_empty() {
        let embedder = OllamaEmbedder::new(OllamaConfig {
            base_url: "http://localhost:11434".into(),
            model: "dummy".into(),
            dim: 1536,
        });

        let result = embedder.embed(&[]).await.unwrap();
        assert!(result.is_empty());
    }

    #[test]
    fn validate_embeddings_rejects_count_mismatch() {
        let embeddings = vec![vec![1.0, 2.0]];
        let err = validate_embeddings(2, &embeddings, 2).expect_err("expected count mismatch");
        assert!(
            err.to_string()
                .contains("ollama returned 1 embeddings for 2 input texts"),
            "unexpected error message: {}",
            err
        );
    }

    #[test]
    fn validate_embeddings_rejects_dim_mismatch() {
        let embeddings = vec![vec![1.0, 2.0], vec![3.0]];
        let err = validate_embeddings(2, &embeddings, 2).expect_err("expected dim mismatch");
        assert!(
            err.to_string()
                .contains("unexpected embedding dimensionality"),
            "unexpected error message: {}",
            err
        );
    }
}
```
```

### 📄 merges/semantAH_merge_2510262237__semantAH_crates_indexd.md

**Größe:** 619 B | **md5:** `bd0512bd85f1e7060dec19a0d9af27df`

```markdown
### 📄 semantAH/crates/indexd/Cargo.toml

**Größe:** 497 B | **md5:** `65a41b62a1a8e914040c0e6e1f1a7ccc`

```toml
[package]
name = "indexd"
version = "0.1.0"
edition = "2021"
license = "MIT"
description = "HTTP service for indexing and semantic search"

[dependencies]
anyhow.workspace = true
axum.workspace = true
serde.workspace = true
serde_json.workspace = true
tokio.workspace = true
tracing.workspace = true
tracing-subscriber.workspace = true
config.workspace = true
thiserror.workspace = true
futures.workspace = true

[dependencies.embeddings]
path = "../embeddings"

[dev-dependencies]
tower = "0.5"
```
```

### 📄 merges/semantAH_merge_2510262237__semantAH_crates_indexd_src.md

**Größe:** 9 KB | **md5:** `ce3f7a63096b97bdbeb7b284a18d2da4`

```markdown
### 📄 semantAH/crates/indexd/src/lib.rs

**Größe:** 2 KB | **md5:** `e535b6c7568647d77a32ac56f1620e03`

```rust
pub mod store;

use std::{net::SocketAddr, sync::Arc};

use axum::{routing::get, Router};
use tokio::sync::RwLock;
use tokio::{net::TcpListener, signal};
use tracing::{info, Level};
use tracing_subscriber::FmtSubscriber;

#[derive(Debug)]
pub struct AppState {
    pub store: RwLock<store::VectorStore>,
}

impl AppState {
    pub fn new() -> Self {
        Self {
            store: RwLock::new(store::VectorStore::new()),
        }
    }
}

impl Default for AppState {
    fn default() -> Self {
        Self::new()
    }
}

pub use store::{VectorStore, VectorStoreError};

#[derive(Clone, Default)]
pub struct App;

/// Basis-Router (Healthcheck). Zusätzliche Routen werden in `run` via `build_routes` ergänzt.
pub fn router(state: Arc<AppState>) -> Router {
    Router::new()
        .route("/healthz", get(healthz))
        .with_state(state)
}

/// Startet den Server auf 0.0.0.0:8080 und merged die vom Caller gelieferten Routen.
pub async fn run(
    build_routes: impl FnOnce(Arc<AppState>) -> Router + Send + 'static,
) -> anyhow::Result<()> {
    init_tracing();

    let state = Arc::new(AppState::new());
    let router = build_routes(state.clone()).merge(router(state));

    let addr: SocketAddr = "0.0.0.0:8080".parse()?;
    info!(%addr, "starting indexd");

    let listener = TcpListener::bind(addr).await?;
    axum::serve(listener, router)
        .with_graceful_shutdown(shutdown_signal())
        .await?;

    info!("indexd stopped");
    Ok(())
}

fn init_tracing() {
    let subscriber = FmtSubscriber::builder()
        .with_max_level(Level::INFO)
        .with_target(false)
        .finish();
    let _ = tracing::subscriber::set_global_default(subscriber);
}

async fn shutdown_signal() {
    let ctrl_c = async {
        signal::ctrl_c()
            .await
            .expect("failed to install CTRL+C handler");
    };

    #[cfg(unix)]
    let terminate = async {
        signal::unix::signal(signal::unix::SignalKind::terminate())
            .expect("failed to install signal handler")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => {},
        _ = terminate => {},
    }
}

async fn healthz() -> &'static str {
    "ok"
}
```

### 📄 semantAH/crates/indexd/src/main.rs

**Größe:** 4 KB | **md5:** `7354e397594cf31fe16d2986b012770e`

```rust
//! Minimal HTTP server stub for the semantic index daemon (indexd).

use std::sync::Arc;

use axum::{extract::State, http::StatusCode, routing::post, Json, Router};
use indexd::AppState;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tracing::info;

#[derive(Debug, Deserialize)]
struct UpsertRequest {
    doc_id: String,
    namespace: String,
    chunks: Vec<ChunkPayload>,
}

#[derive(Debug, Deserialize)]
struct ChunkPayload {
    id: String,
    /// Text wird aktuell nicht genutzt (Embedding wird über `meta.embedding` erwartet),
    /// daher per Rename stillgelegt, um Warnungen zu vermeiden.
    #[serde(rename = "text")]
    _text: String,
    #[serde(default)]
    meta: Value,
}

#[derive(Debug, Deserialize)]
struct DeleteRequest {
    doc_id: String,
    namespace: String,
}

#[derive(Debug, Deserialize)]
struct SearchRequest {
    query: String,
    #[serde(default = "default_k")]
    k: u32,
    namespace: String,
    #[serde(default)]
    filters: Value,
}

#[derive(Debug, Serialize)]
struct SearchResponse {
    results: Vec<SearchHit>,
}

#[derive(Debug, Serialize)]
struct SearchHit {
    doc_id: String,
    chunk_id: String,
    score: f32,
    snippet: String,
    rationale: Vec<String>,
}

fn default_k() -> u32 {
    10
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    indexd::run(|state| {
        Router::new()
            .route("/index/upsert", post(handle_upsert))
            .route("/index/delete", post(handle_delete))
            .route("/index/search", post(handle_search))
            .with_state(state)
    })
    .await
}

async fn handle_upsert(
    State(state): State<Arc<AppState>>,
    Json(payload): Json<UpsertRequest>,
) -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    let chunk_count = payload.chunks.len();
    info!(doc_id = %payload.doc_id, namespace = %payload.namespace, chunks = chunk_count, "received upsert");

    let UpsertRequest {
        doc_id,
        namespace,
        chunks,
    } = payload;

    let mut store = state.store.write().await;

    for chunk in chunks {
        let ChunkPayload { id, _text: _, meta } = chunk;

        let mut meta = match meta {
            Value::Object(map) => map,
            _ => return Err(bad_request("chunk meta must be an object")),
        };

        let embedding_value = meta
            .remove("embedding")
            .ok_or_else(|| bad_request("chunk meta must contain an embedding array"))?;

        let vector = parse_embedding(embedding_value).map_err(bad_request)?;

        store
            .upsert(&namespace, &doc_id, &id, vector, Value::Object(meta))
            .map_err(|err| bad_request(err.to_string()))?;
    }

    Ok(Json(json!({
        "status": "accepted",
        "chunks": chunk_count,
    })))
}

async fn handle_delete(
    State(state): State<Arc<AppState>>,
    Json(payload): Json<DeleteRequest>,
) -> Json<Value> {
    info!(doc_id = %payload.doc_id, namespace = %payload.namespace, "received delete");

    let mut store = state.store.write().await;
    store.delete_doc(&payload.namespace, &payload.doc_id);

    Json(json!({
        "status": "accepted"
    }))
}

fn parse_embedding(value: Value) -> Result<Vec<f32>, String> {
    match value {
        Value::Array(values) => values
            .into_iter()
            .map(|v| {
                v.as_f64()
                    .map(|num| num as f32)
                    .ok_or_else(|| "embedding must be an array of numbers".to_string())
            })
            .collect(),
        _ => Err("embedding must be an array of numbers".to_string()),
    }
}

fn bad_request(message: impl Into<String>) -> (StatusCode, Json<Value>) {
    let body = json!({
        "error": message.into(),
    });
    (StatusCode::BAD_REQUEST, Json(body))
}

async fn handle_search(Json(payload): Json<SearchRequest>) -> Json<SearchResponse> {
    info!(
        query = %payload.query,
        k = payload.k,
        namespace = %payload.namespace,
        filters = ?payload.filters,
        "received search"
    );

    // Placeholder: Noch keine Ähnlichkeitssuche – leere Trefferliste.
    Json(SearchResponse {
        results: Vec::new(),
    })
}
```

### 📄 semantAH/crates/indexd/src/store.rs

**Größe:** 3 KB | **md5:** `b12f68822032f47cc84967146fc7a707`

```rust
use std::collections::HashMap;

use serde_json::Value;
use thiserror::Error;

const KEY_SEPARATOR: &str = "\u{241F}";

#[derive(Debug, Default)]
pub struct VectorStore {
    pub dims: Option<usize>,
    pub items: HashMap<(String, String), (Vec<f32>, Value)>,
}

impl VectorStore {
    pub fn new() -> Self {
        Self {
            dims: None,
            items: HashMap::new(),
        }
    }

    pub fn upsert(
        &mut self,
        namespace: &str,
        doc_id: &str,
        chunk_id: &str,
        vector: Vec<f32>,
        meta: Value,
    ) -> Result<(), VectorStoreError> {
        if let Some(expected) = self.dims {
            if expected != vector.len() {
                return Err(VectorStoreError::DimensionalityMismatch {
                    expected,
                    actual: vector.len(),
                });
            }
        } else {
            self.dims = Some(vector.len());
        }

        let key = (namespace.to_string(), make_chunk_key(doc_id, chunk_id));
        self.items.insert(key, (vector, meta));
        Ok(())
    }

    pub fn delete_doc(&mut self, namespace: &str, doc_id: &str) {
        let prefix = format!("{doc_id}{KEY_SEPARATOR}");
        self.items
            .retain(|(ns, key), _| !(ns == namespace && key.starts_with(&prefix)));

        if self.items.is_empty() {
            self.dims = None;
        }
    }

    pub fn all_in_namespace<'a>(
        &'a self,
        namespace: &'a str,
    ) -> impl Iterator<Item = (&'a (String, String), &'a (Vec<f32>, Value))> + 'a {
        self.items
            .iter()
            .filter(move |((ns, _), _)| ns == namespace)
    }
}

#[derive(Debug, Error)]
pub enum VectorStoreError {
    #[error("embedding dimensionality mismatch: expected {expected}, got {actual}")]
    DimensionalityMismatch { expected: usize, actual: usize },
}

fn make_chunk_key(doc_id: &str, chunk_id: &str) -> String {
    format!("{doc_id}{KEY_SEPARATOR}{chunk_id}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn upsert_delete_smoke() {
        let mut store = VectorStore::new();
        let meta = Value::Null;
        store
            .upsert("namespace", "doc", "chunk-1", vec![0.1, 0.2], meta.clone())
            .expect("first insert sets dims");
        store
            .upsert("namespace", "doc", "chunk-2", vec![0.3, 0.4], meta)
            .expect("second insert matches dims");

        assert_eq!(store.items.len(), 2);

        store.delete_doc("namespace", "doc");

        assert!(store.items.is_empty(), "store should be empty after delete");
        assert!(
            store.dims.is_none(),
            "dims should reset after deleting all items"
        );
    }
}
```
```

### 📄 merges/semantAH_merge_2510262237__semantAH_crates_indexd_tests.md

**Größe:** 737 B | **md5:** `8cddf848313f058852810b511eb16d19`

```markdown
### 📄 semantAH/crates/indexd/tests/healthz.rs

**Größe:** 608 B | **md5:** `11486604bd2275696876d40b80e646e9`

```rust
use std::sync::Arc;

use axum::{
    body::{to_bytes, Body},
    http::{Request, StatusCode},
};
use tower::ServiceExt;

#[tokio::test]
async fn healthz_returns_ok() {
    let app = indexd::router(Arc::new(indexd::AppState::new()));

    let response = app
        .oneshot(
            Request::builder()
                .uri("/healthz")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);

    let body = to_bytes(response.into_body(), 1024).await.unwrap();
    assert_eq!(body.as_ref(), b"ok");
}
```
```

### 📄 merges/semantAH_merge_2510262237__semantAH_docs.md

**Größe:** 68 KB | **md5:** `472865059753218aee1b8755577beab5`

```markdown
### 📄 semantAH/docs/blueprint.md

**Größe:** 11 KB | **md5:** `b1fa5ee0047bbe711860d0848e1be72d`

```markdown
# Vault-Gewebe: Finale Blaupause

Diese Datei fasst die komplette Architektur für das semantische Vault-Gewebe zusammen. Sie kombiniert den semantischen Index, den Wissensgraphen, Obsidian-Automatismen sowie Qualitäts- und Review-Schleifen. Alle Schritte sind lokal reproduzierbar und werden in `.gewebe/` versioniert.

---

## 0. Systemordner & Konventionen

```
.gewebe/
  config.yml           # Parameter (Modelle, Cutoffs, Policies)
  embeddings.parquet   # Chunks + Vektoren
  nodes.jsonl          # Graph-Knoten
  edges.jsonl          # Graph-Kanten
  clusters.json        # Cluster & Label
  taxonomy/
    synonyms.yml
    entities.yml
  reports/
    semnet-YYYYMMDD.md
  meta.json            # Provenienz (Modell, Parameter, Hashes)
```

**Frontmatter pro Datei**

```yaml
id: 2025-VAULT-####   # stabiler Schlüssel
title: ...
topics: [HausKI, Weltgewebe]
persons: [Verena]
places: [Hamburg]
projects: [wgx, hauski]
aliases: [HK, WG]
relations_lock: false
```

---

## 1. Indexing & Embeddings

- Crawler: iteriert Markdown & Canvas (ignoriert `.gewebe/`, `.obsidian/`).
- Chunking: 200–300 Tokens, Overlap 40–60, Paragraph/Block.
- Modelle: `all-MiniLM-L6-v2` oder `intfloat/e5-base` (GPU-fähig via PyTorch/CUDA).
- Output: `embeddings.parquet` (id, path, chunk_id, text, embedding).

---

## 2. Schlagwort- & Entitätsextraktion

- Keyphrase: YAKE/RAKE lokal → optional mit LLM verfeinern.
- NER: spaCy DE-Modell → Personen, Orte, Projekte.
- Taxonomie in `.gewebe/taxonomy/synonyms.yml`:

```yaml
topics:
  hauski: [haus-ki, hk]
persons:
  verena: [v.]
```

- Normalisierung: Tokens bei Indexlauf auf Normformen mappen → ins Frontmatter schreiben.

---

## 3. Clusterbildung

- Verfahren: HDBSCAN (robust) + UMAP (2D-Projektion für Visualisierung).
- Ergebnis: `clusters.json` mit IDs, Label, Mitgliedern und Zentroiden.
- Orphan Detection: Notizen ohne Cluster → separate Liste.

---

## 4. Semantischer Wissensgraph

**Nodes (`nodes.jsonl`)**

```json
{"id":"md:gfk.md","type":"file","title":"GFK","topics":["gfk"],"cluster":7}
{"id":"topic:Gewaltfreie Kommunikation","type":"topic"}
{"id":"person:Verena","type":"person"}
```

**Edges (`edges.jsonl`)**

```json
{"src":"md:gfk.md","rel":"about","dst":"topic:Gewaltfreie Kommunikation","weight":0.92,"why":["shared:keyphrase:GFK","same:cluster"]}
{"src":"md:verena.md","rel":"similar","dst":"md:tatjana.md","weight":0.81,"why":["cluster:7","quote:'…'"]}
```

Das Feld `why` speichert die Top-Rationales (Keyphrases, Cluster, Anker-Sätze) und ermöglicht Explainability.

---

## 5. Verlinkung in Obsidian

- Related-Blöcke (idempotent, autogeneriert):

```
<!-- related:auto:start -->
## Related
- [[Tatjana]] — (0.81; Cluster 7, GFK)
- [[Lebenslagen]] — (0.78; Resonanz)
<!-- related:auto:end -->
```

- MOCs (`_moc/topic.md`): Beschreibung, Dataview-Tabelle (`topics:topic`), Mini-Canvas-Link.
- Canvas-Integration: Knoten = Notizen/Topics/Persons, Kanten = Similar/About/Mentions, Legende-Knoten nach Canvas-Richtlinie.

---

## 6. Automatisierung

- `wgx`-Recipes:

```yaml
index:
    python3 tools/build_index.py
graph:
    python3 tools/build_graph.py
related:
    python3 tools/update_related.py
all: index graph related
```

- systemd `--user` Timer oder cron: nightly `make all`.
- Git-Hook (pre-commit): delta-Index → Related aktualisieren.

---

## 7. Qualitative Validierung

- Reports (`reports/semnet-YYYYMMDD.md`): neue Kanten < 0.75 („Review required“), Orphans, Cluster > N Notizen ohne MOC.
- Review-Workflow: `accepted_edges` / `rejected_edges` im Frontmatter; Skripte ignorieren `rejected` → Feedback fließt zurück.

---

## 8. Policies & Score-Regeln

```
score = cosine + boosts
+0.05 wenn gleicher Cluster
+0.03 je shared keyphrase (max +0.09)
+0.04 wenn Canvas-Hop ≤ 2
+0.02 wenn Datei jung (<30 Tage)
```

Autolink-Gate:

- Score ≥ 0.82 **und** (≥ 2 Keyphrases **oder** Canvas-Hop ≤ 2 **oder** shared Project).
- Cutoffs: ≥ 0.82 Auto-Link, 0.70–0.81 Vorschlag, < 0.70 ignorieren.

---

## 9. Erweiterungen (Kernideen)

- Duplicates Report: Cosine ≥ 0.97 → Merge-Vorschlag.
- Topic Drift: Clusterwechsel flaggen.
- Session-Boost: aktuell bearbeitete Dateien → Score +0.02.
- Explain Command: Popover „Warum ist dieser Link da?“ (zeigt `why`-Feld).
- Locks: `relations_lock: true` → keine Auto-Edits.
- A/B-Cutoffs: zwei Profile testen, Review-Feedback einspeisen.

---

## 10. Provenienz & Reproduzierbarkeit

`.gewebe/meta.json` speichert:

```json
{
  "model": "all-MiniLM-L6-v2",
  "chunk_size": 200,
  "cutoffs": {"auto": 0.82, "suggest": 0.70},
  "run": "2025-10-02T11:40",
  "commit": "abc123"
}
```

---

## 11. Technische Bausteine

### Tools / Skripte

- `tools/build_index.py`: Scan + Embeddings.
- `tools/build_graph.py`: Nodes/Edges/Cluster.
- `tools/update_related.py`: Related-Blöcke injizieren.
- `tools/report.py`: QA-Reports.
- optional `tools/canvas_export.py`: Cluster → Canvas.

### Dreistufiger Zyklus

1. Index (Embeddings, Cluster, Taxonomie).
2. Graph (Nodes/Edges mit Rationales).
3. Update (Related, MOCs, Reports, Canvas).

---

## 12. Minimal lauffähige Suite

Eine robuste, offline-fähige Minimalversion liefert unmittelbar Embeddings, Similarities, Graph (Nodes/Edges), Related-Blöcke und Reports.

### Dateibaum

```
<Vault-Root>/
  .gewebe/
    config.yml
    taxonomy/
      synonyms.yml
      entities.yml
    reports/
  tools/
    build_index.py
    build_graph.py
    update_related.py
  Makefile
```

### Python-Abhängigkeiten

```
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install pandas numpy pyarrow pyyaml \
  sentence_transformers scikit-learn networkx rich
```

Standardmodell: `sentence-transformers/all-MiniLM-L6-v2`. GPU nutzt Torch automatisch, falls vorhanden.

### `.gewebe/config.yml`

```yaml
model: sentence-transformers/all-MiniLM-L6-v2
chunk:
  target_chars: 1200
  min_chars: 300
  overlap_chars: 200
paths:
  exclude_dirs: [".gewebe", ".obsidian", "_site", "node_modules"]
  include_ext: [".md"]
related:
  k: 8
  auto_cutoff: 0.82
  suggest_cutoff: 0.70
boosts:
  same_topic: 0.03
  same_project: 0.03
  recent_days: 30
  recent_bonus: 0.02
  same_folder: 0.02
render:
  related_heading: "## Related"
  markers:
    start: "<!-- related:auto:start -->"
    end:   "<!-- related:auto:end -->"
```

### Skripte (`tools/*.py`)

Die Skripte implementieren:

- Markdown-Scan, Frontmatter-Parsing und Chunking.
- Embedding-Berechnung mit SentenceTransformers.
- Vektorzentroide pro Datei + Cosine-Similarity.
- Score-Boosts basierend auf Topics, Projekten, Ordnern, Recency.
- Schreiben von `nodes.jsonl`, `edges.jsonl` und Reports.
- Injection idempotenter Related-Blöcke in Markdown.

(Vollständige Implementierungen befinden sich in `tools/` im Repo und sind auf GPU/CPU lauffähig.)

### Makefile

```
VENV=.venv
PY=$(VENV)/bin/python

.PHONY: venv index graph related all clean

venv: $(VENV)/.deps_installed

$(VENV)/.deps_installed: 
	@test -d $(VENV) || python3 -m venv $(VENV)
	@$(PY) -m pip install --upgrade pip
	@$(PY) -m pip install pandas numpy pyarrow pyyaml sentence_transformers scikit-learn networkx rich
	@touch $(VENV)/.deps_installed
index: venv
@$(PY) tools/build_index.py

graph: venv
@$(PY) tools/build_graph.py

related: venv
@$(PY) tools/update_related.py

all: index graph related

clean:
@rm -f .gewebe/embeddings.parquet
@rm -f .gewebe/nodes.jsonl .gewebe/edges.jsonl
```

### systemd (User) Timer

`~/.config/systemd/user/vault-gewebe.service`

```
[Unit]
Description=Vault-Gewebe nightly build (index -> graph -> related)
After=default.target

[Service]
Type=oneshot
WorkingDirectory=%h/path/to/your/vault
ExecStart=make all
```

`~/.config/systemd/user/vault-gewebe.timer`

```
[Unit]
Description=Run Vault-Gewebe every night

[Timer]
OnCalendar=*-*-* 03:10:00
Persistent=true

[Install]
WantedBy=timers.target
```

Aktivieren:

```
systemctl --user daemon-reload
systemctl --user enable --now vault-gewebe.timer
systemctl --user list-timers | grep vault-gewebe
```

### Erstlauf

```
make venv
make all
```

Ergebnisdateien liegen unter `.gewebe/…`. In Obsidian erscheint der Related-Block am Ende der Note.

---

## 13. HausKI-Integration (Überblick)

Für HausKI entsteht ein neuer Dienstverbund:

1. `crates/embeddings`: Embedder-Trait + Provider (lokal via Ollama, optional Cloud über AllowlistedClient und Safe-Mode-Policies).
2. `crates/indexd`: HTTP-Service (`/index/upsert`, `/index/search`, `/index/delete`), HNSW-Vektorindex, Persistenz (`~/.local/state/hauski/index/obsidian`).
3. Obsidian-Plugin (Thin Client): chunked Upserts & Searches über HausKI-Gateway.
4. Config-Erweiterung (`configs/hauski.yml`): Index-Pfad, Embedder-Optionen, Namespace-Policies.

Siehe `docs/hauski.md` für eine ausführliche Einbindung.

---

## 14. Erweiterte Qualitäts- & Komfortfeatures

1. **Begründete Kanten** – `edges.jsonl` enthält `why`-Feld mit Keyphrases, Cluster, Quotes.
2. **Near-Duplicate-Erkennung** – Cosine ≥ 0.97 → Merge-Report, Canonical-Markierung.
3. **Zeit-Boost** – +0.05 für Notizen < 30 Tage, Decay für ältere Inhalte.
4. **Ordner-/Namespace-Policies** – z. B. `/archive/` nur eingehende Links, `/ideen/` liberalere Cutoffs.
5. **Feedback-Lernen** – `accepted_edges`/`rejected_edges` beeinflussen Cutoffs.
6. **Canvas-Hop-Boost** – Pfadlänge ≤ 2 innerhalb von Canvas erhöht Score um 0.03–0.07.
7. **Topic-Drift-Wächter** – signalisiert Clusterwechsel.
8. **Explainable Related-Blöcke** – Scores & Top-Begründungen in Markdown.
9. **Session-Kontext** – aktuell geöffnete Dateien geben +0.02 Boost.
10. **Provenienz** – `meta.json` mit Modell, Chunking, Cutoffs, Hashes.
11. **Mehrsprach-Robustheit** – Synonym-/Stemming-Maps für DE/EN.
12. **Autolink-Quality-Gate** – Score ≥ 0.82 + (≥2 Keyphrases oder Canvas-Hop ≤ 2 oder shared Project).
13. **Explain-this-link Command** – Popover mit Rationales im Obsidian-Plugin.
14. **MOC-Qualitätsreport** – Deckungsgrade, verwaiste Knoten, Unter-MOC-Vorschläge.
15. **Transklusions-Vorschläge** – Absatzweise `![[note#^block]]` bei hoher Chunk-Ähnlichkeit.
16. **Manual Lock** – `relations_lock: true` verhindert Auto-Edits.
17. **A/B-Tuning** – zwei Cutoff-Profile testen, Feedback auswerten.
18. **Cross-Vault-Brücke** – Read-Only Namespace `ext:*` für externe Vaults.
19. **Orphans-First-Routine** – wöchentliche Fokussierung auf unverlinkte Notizen.
20. **Explainable Deletes** – Reports dokumentieren entfernte Kanten mit Ursache.

---

## 15. Unsicherheiten & Anpassbarkeit

- Schwellenwerte & Chunking müssen empirisch justiert werden.
- Canvas-Hop-Berechnungen hängen vom JSON-Layout ab.
- Modellwahl beeinflusst Qualität und Performance.
- Die Pipeline ist modular, Reports + Feedback-Loops ermöglichen schnelle Iteration.

---

## 16. Verdichtete Essenz

- Drei Skripte, ein Makefile, ein Timer → Index → Graph → Related.
- HausKI liefert den skalierbaren Dienst (`indexd`) + Obsidian-Adapter.
- Qualität durch erklärbare Kanten, Review-Workflow, Reports, Policies.
- Lokal, reproduzierbar, versionierbar – dein Vault wird zum lebenden Semantiknetz.

---

> *Ironische Auslassung:* Deine Notizen sind jetzt kein stilles Archiv mehr – sie bilden ein Klatsch-Netzwerk, das genau protokolliert, wer mit wem was zu tun hat. Nur: Sie lügen nicht.
```

### 📄 semantAH/docs/hauski.md

**Größe:** 5 KB | **md5:** `9b9d21594d5468bdaea32737a8f4b7f5`

```markdown
# HausKI-Integration

HausKI bleibt das lokale Orchestrierungs-Gateway. semantAH ergänzt es als semantische Gedächtnis-Schicht. Dieser Leitfaden beschreibt, wie die neuen Komponenten (`indexd`, `embeddings`, Obsidian-Adapter) eingebunden werden und welche Policies greifen.

---

## Architekturüberblick

1. **`crates/embeddings`** – stellt den `Embedder`-Trait bereit und kapselt Provider:
   - `Ollama` (lokal, offline) ruft `http://127.0.0.1:11434/api/embeddings` auf.
   - `CloudEmbedder` (optional) nutzt HausKIs AllowlistedClient. Aktiv nur, wenn `safe_mode=false` und der Zielhost in der Egress-Policy freigeschaltet ist.
2. **`crates/indexd`** – HTTP-Service mit Routen:
   - `POST /index/upsert` – nimmt Chunks + Metadaten entgegen und legt Vektoren im HNSW-Index ab.
   - `POST /index/delete` – entfernt Dokumente aus einem Namespace.
   - `POST /index/search` – Top-k-Suche mit Filtern (Tags, Projekte, Pfade).
   - Persistenz liegt unter `~/.local/state/hauski/index/<namespace>/`.
3. **Obsidian-Adapter (Thin Plugin)** – zerlegt Notizen und Canvas-Dateien, sendet Upserts an HausKI und ruft Suchergebnisse für „Related“/Command-Paletten ab.
4. **Policies & Observability** – bestehende Features (CORS, `/health`, `/metrics`, `safe_mode`, Latency-Budgets) gelten auch für `/index/*`.

---

## Workspace-Konfiguration

`Cargo.toml` (Workspace):

```toml
[workspace]
members = [
  "crates/core",
  "crates/cli",
  "crates/indexd",
  "crates/embeddings"
]
```

`crates/embeddings/src/lib.rs` definiert den Trait und z. B. `Ollama`:

```rust
#[async_trait::async_trait]
pub trait Embedder {
    async fn embed(&self, texts: &[String]) -> anyhow::Result<Vec<Vec<f32>>>;
    fn dim(&self) -> usize;
    fn id(&self) -> &'static str;
}
```

Implementierungen greifen auf `reqwest::Client` zurück. Cloud-Varianten müssen über HausKIs AllowlistedClient laufen, um Egress-Guards einzuhalten.

`crates/indexd` kapselt Embedder + Vektorstore (HNSW + Metadata-KV, z. B. `sled`). Der Router wird in `core::plugin_routes()` unter `/index` gemountet:

```rust
fn plugin_routes() -> Router<AppState> {
    let embedder = embeddings::Ollama::new("http://127.0.0.1:11434", "nomic-embed-text", 768);
    let store = indexd::store::hnsw(/* state_path */);
    Router::new().nest("/index", indexd::Indexd::new(embedder, store).router())
}
```

---

## HTTP-API

### Upsert

```http
POST /index/upsert
{
  "namespace": "obsidian",
  "doc_id": "notes/gfk.md",
  "chunks": [
    {"id": "notes/gfk.md#0", "text": "...", "meta": {"topics": ["gfk"], "frontmatter": {...}}}
  ]
}
```

### Delete

```http
POST /index/delete
{"namespace": "obsidian", "doc_id": "notes/gfk.md"}
```

### Search

```http
POST /index/search
{
  "namespace": "obsidian",
  "query": "empatische Kommunikation",
  "k": 10,
  "filters": {"topics": ["gfk"], "projects": ["wgx"]}
}
```

Antwort: Treffer mit Score, Dokument/Chunk-ID, Snippet, Rationales (`why`).

---

## Persistenz & Budgets

- Indexdaten leben im `index.path` aus der HausKI-Config (`~/.local/state/hauski/index`).
- HNSW-Index + Sled/SQLite halten Embeddings und Metadaten.
- Latency-Budgets: `limits.latency.index_topk20_ms` (Config) definiert das p95-Ziel. K6-Smoke nutzt diesen Wert als Assertion.
- Prometheus-Metriken für `/index/*` werden automatisch vom Core erfasst (`http_requests_total`, `http_request_duration_seconds`).

---

## Konfiguration (`configs/hauski.yml`)

```yaml
index:
  path: "$HOME/.local/state/hauski/index"
  provider:
    embedder: "ollama"
    model: "nomic-embed-text"
    url: "http://127.0.0.1:11434"
    dim: 768
  namespaces:
    obsidian:
      auto_cutoff: 0.82
      suggest_cutoff: 0.70
      policies:
        allow_autolink: true
        folder_overrides:
          archive:
            mode: incoming-only
plugins:
  enabled:
    - obsidian_index
```

`safe_mode: true` sperrt Cloud-Provider automatisch. Namespaces können weitere Regeln (z. B. strengere Cutoffs) erhalten.

---

## Obsidian-Plugin (Adapter)

- Hook auf `onSave` / `metadataCache.on("changed")`.
- Chunking (200–300 Tokens, 40 Overlap), Canvas-JSON-Knoten werden zusätzliche Chunks.
- Sendet `POST /index/upsert` mit Frontmatter/Tags/Canvas-Beziehungen im `meta`-Feld.
- Command „Semantisch ähnliche Notizen“ → `POST /index/search` und Anzeige der Ergebnisse.
- Optionaler Review-Dialog für Vorschläge (Accept/Reject → Frontmatter `accepted_edges` / `rejected_edges`).

---

## Automatisierung & Tests

- `wgx run index:obsidian` ruft der Reihe nach `build_index`, `build_graph`, `update_related` auf.
- systemd-Timer führt `make all` nightly aus (siehe `docs/blueprint.md`).
- CI/K6: Smoke-Test gegen `/index/search` mit Query-Stubs → prüft p95 < `limits.latency.index_topk20_ms`.

---

## Mehrwert

- Saubere Zuständigkeiten (UI vs. Dienste).
- Egress-kontrollierte Einbindung externer Provider.
- Explainable Scores via `why`-Feld.
- Reports & Policies sorgen für qualitätsgesicherte Auto-Links.

> *Ironische Auslassung:* HausKI bleibt der Türsteher – aber semantAH entscheidet, wer auf die VIP-Liste der Notizen kommt.
```

### 📄 semantAH/docs/quickstart.md

**Größe:** 730 B | **md5:** `ee8d08856e82b12a3beec126165fb263`

```markdown
# semantAH · Quickstart

## Voraussetzungen
- Rust (stable), Python ≥ 3.10
- Optional: `uv` (für schnelle Envs)

## Installation (lokal)
```bash
uv sync            # oder: make venv
```

## Konfiguration
```bash
cp examples/semantah.example.yml semantah.yml
# passe vault_path und out_dir an
```

## Pipeline laufen lassen
```bash
make all           # embeddings → index → graph → related
cargo run -p indexd
curl -fsS localhost:8080/healthz || true
```

## Artefakte
- `.gewebe/embeddings.parquet`
- `.gewebe/out/{nodes.jsonl,edges.jsonl,reports.json}`

## Troubleshooting
- Leere/zu große Dateien werden übersprungen → Logs in `.gewebe/logs` prüfen.
- Bei fehlenden Modellen: Provider in `semantah.yml` anpassen.
```

### 📄 semantAH/docs/roadmap.md

**Größe:** 1 KB | **md5:** `24f4c6253a1f9e1855df22c940921405`

```markdown
<!--
Quelle: /home/alex/vault-gewebe/coding/semantAH/semantAH brainstorm.md
-->

# semantAH Roadmap

Dieses Dokument überträgt die Ideen aus der Brainstorming-Notiz in umsetzbare Meilensteine.

## Milestone 1 – Grundgerüst
- Rust-Workspace mit `embeddings`-Crate (Ollama-Backend) und `indexd`-Crate (Axum-HTTP, HNSW-Wrapper).
- Persistenz-Pfade `.local/state/hauski/index/obsidian` vorbereiten.
- Feature-Flags: `safe_mode`, `limits.latency.index_topk20_ms` an HNSW koppeln.
- Erste HTTP-Routen:
  - `POST /index/upsert`
  - `POST /index/delete`
  - `POST /index/search`
- Python-Skripte als Platzhalter einchecken.

## Milestone 2 – Ranking & Policies
- Boosts: Zeit, Tags, Canvas-Hop, Cluster.
- Qualitäts-Gates (`score >= 0.82`, Keyphrases ≥ 2, Canvas-Hop ≤ 2 oder shared project).
- Rationale-Felder in `edges.jsonl` und Related-Block.

## Milestone 3 – Feedback & Reports
- Feedback-Schleife für Accept/Reject.
- Orphan-Report, Duplicate-Detection, Topic-Drift.
- Explain-UI im Obsidian-Plugin (separates Repo/Plugin).

## Milestone 4 – Advanced Features
- Session-Context-Boost (aktuelle Arbeitssession).
- Cross-Vault-Namespace (read-only).
- Manual-Lock (`relations_lock: true`).

## Umsetzungshinweise
- Jede Funktionalität modular halten, sodass Experimente / A/B-Tests (Cutoffs) möglich bleiben.
- Alle Heuristiken als Config-Werte in `.gewebe/config.yml` ablegen.
- Provenienz in `.gewebe/meta.json` dokumentieren (Embedding-Modell, Chunking-Parameter, Taxonomie-Version).
```

### 📄 semantAH/docs/runbook.observability.md

**Größe:** 545 B | **md5:** `abc6d168fcb5c65c139b2ae9e2d21714`

```markdown
# Observability Runbook

## Overview

This runbook describes how to access the local observability stack while developing semantAH. The stack is composed of Grafana, Loki, and Tempo containers that expose HTTP interfaces for debugging and tracing.

## Endpoints

- Grafana: [http://localhost:3000](http://localhost:3000)
- Loki: [http://localhost:3100](http://localhost:3100)
- Tempo: [http://localhost:3200](http://localhost:3200)

Use these endpoints to inspect logs, metrics, and traces when diagnosing issues in the development environment.
```

### 📄 semantAH/docs/semantAH brainstorm.md

**Größe:** 24 KB | **md5:** `ef898078966a53c4cf0cca26de1d0bb0`

```markdown
mega–ja. wir bauen das selbst – aber so, dass es perfekt in dein repo passt. hier ist der konkrete blueprint für “semantische suche / vektor-index” als hauski-dienst + dünnes obsidian-plugin-frontend.

(ich beziehe mich dabei auf deine repo-struktur, configs und bereits vorhandene core-server-grundlagen wie /health, /metrics, CORS, „safe_mode“, egress-guard usw. – die sehen schon sehr solide aus.  ￼)

zielbild (kompakt)
	•	hauski-core bleibt HTTP-Gateway/Telemetry.
	•	neuer crate indexd: Embeddings + Vektorindex (HNSW) + Persistenz + Filter.
	•	neuer crate embeddings: Abstraktion für Provider (lokal via Ollama/gguf, optional cloud – respektiert egress-Policy).
	•	adapter: obsidian-plugin (thin client): sendet Chunks/Updates an indexd, ruft search ab.
	•	policies & flags: such-latenz-budget an Limits koppeln; safe_mode blockt Cloud-Provider.

⸻

was ist schon da (und wie nutzen wir’s)?
	•	Core-HTTP, Metrics, CORS, Ready/Health – fertiges Gerüst für neue Routen.  ￼
	•	Feature-Flags & Policies inkl. safe_mode und Egress-Allowlisting → perfekt, um Cloud-Embeddings sauber zu sperren/erlauben.  ￼
	•	Configs: configs/hauski.yml hat vault_path & plugins-liste – hier hängen wir obsidian_index offiziell an und tragen indexd ein.  ￼

⸻

module & schnittstellen

1) crate: crates/indexd/

Aufgaben
	•	Dokumente in Chunks zerlegen (MD + Canvas JSON).
	•	Embeddings berechnen (ruft embeddings-crate).
	•	Vektoren in HNSW speichern (z. B. hnsw_rs oder hnswlib-binding) + Metadata-Store (z. B. sled/sqlite).
	•	Top-K Suche + Filter (Pfad, Tags, Frontmatter, Canvas-Knoten).
	•	Persistenz auf Disk ($HOME/.local/state/hauski/index/obsidian).

HTTP-API (einfach, stabil):
	•	POST /index/upsert
body:

{ "doc_id":"path/to/note.md",
  "chunks":[{"id":"path:offset", "text":"...", "meta":{"tags":["..."],"frontmatter":{}}}],
  "namespace":"obsidian" }


	•	POST /index/delete → {"doc_id":"...","namespace":"obsidian"}
	•	POST /index/search

{ "query":"...", "k":10, "namespace":"obsidian", "filters":{"tags":["projectX"]} }

response: Treffer mit score, doc_id, chunk_id, snippet.

Leistung & Budgets
	•	p95-Ziel für search(k<=20) an limits.latency.index_topk20_ms koppeln (Config hast du schon).  ￼

2) crate: crates/embeddings/

Ziel: austauschbarer Provider mit egress-Guard & safe_mode.
	•	Trait:

#[async_trait::async_trait]
pub trait Embedder {
    async fn embed(&self, texts: &[String]) -> anyhow::Result<Vec<Vec<f32>>>;
    fn dim(&self) -> usize;
    fn id(&self) -> &'static str;
}


	•	LocalOllamaEmbedder (default, offline): ruft http://127.0.0.1:11434/api/embeddings (modell konfigurierbar: nomic-embed-text o. ä.).
	•	CloudEmbedder (optional): nur wenn safe_mode=false und egress-Policy Host erlaubt. Nutzt vorhandenen AllowlistedClient (ist schon implementiert, wir müssen nur Aufrufe darüber routen).  ￼

3) core-routes erweitern

In hauski-core gibt’s TODO-Platzhalter plugin_routes() – hier mounten wir indexd-Router unter /index. CORS & Metrics sind schon verdrahtet.  ￼

⸻

minimaler code–fahrplan

A) workspace ergänzen

Cargo.toml (root) – neue Mitglieder:

[workspace]
members = [
  "crates/core",
  "crates/cli",
  "crates/indexd",        # NEU
  "crates/embeddings"     # NEU
]

(du hast das Pattern bereits offen für weitere crates – siehe Kommentar im bestehenden Cargo.toml.)  ￼

B) crates/embeddings/src/lib.rs (skizze)

use anyhow::Result;
use reqwest::Client;

#[async_trait::async_trait]
pub trait Embedder {
    async fn embed(&self, texts: &[String]) -> Result<Vec<Vec<f32>>>;
    fn dim(&self) -> usize;
    fn id(&self) -> &'static str;
}

pub struct Ollama {
    http: Client,
    url: String,
    model: String,
    dim: usize,
}

#[async_trait::async_trait]
impl Embedder for Ollama {
    async fn embed(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {

<<TRUNCATED: max_file_lines=800>>
```

### 📄 merges/semantAH_merge_2510262237__semantAH_docs_adr.md

**Größe:** 520 B | **md5:** `3c391f1b7bdb43792c5bb141ed2eee60`

```markdown
### 📄 semantAH/docs/adr/0001-semantics-contract.md

**Größe:** 382 B | **md5:** `cd35e79e053628ae631f3917415f6d61`

```markdown
# ADR-0001: Semantik-Contract
Status: accepted

Beschluss:
- semantAH liefert Nodes/Edges/Reports im JSON-Format gemäß `contracts/semantics/*.schema.json`.
- Weltgewebe konsumiert diese Artefakte read-only und setzt eigene Events oben drauf.

Konsequenzen:
- Änderungen sind semver-minor kompatibel (nur additive Felder).
- Breaking Changes nur per neue Schemas mit neuer Datei.
```
```

### 📄 merges/semantAH_merge_2510262237__semantAH_docs_runbooks.md

**Größe:** 372 B | **md5:** `d87a49856da77a2dbe3e58651f01d325`

```markdown
### 📄 semantAH/docs/runbooks/semantics-intake.md

**Größe:** 236 B | **md5:** `e21653d16c80b458a655b2d15560b86f`

```markdown
<!-- Runbook for manually intaking semantics data -->

# Semantics Intake (manuell)

1) Von semantAH: `.gewebe/out/...`
2) Archivieren und aufbereiten gemäß Prozessbeschreibung.
3) Übertragen in das Zielsystem laut Betriebshandbuch.
```
```

### 📄 merges/semantAH_merge_2510262237__semantAH_docs_x-repo.md

**Größe:** 285 B | **md5:** `16f246e294e92046f9495c5dd10667f7`

```markdown
### 📄 semantAH/docs/x-repo/weltgewebe.md

**Größe:** 157 B | **md5:** `4f8574180b4132f01652d73b43c4c827`

```markdown
semantAH liefert Semantik-Infos (Nodes/Edges/Reports) per JSON/JSONL.
Weltgewebe konsumiert read-only. Änderungen an Contracts nur additive (semver-minor).
```
```

### 📄 merges/semantAH_merge_2510262237__semantAH_examples.md

**Größe:** 596 B | **md5:** `0aeaf6f05cced9b7fa9d6aa5a656e4c2`

```markdown
### 📄 semantAH/examples/semantah.example.yml

**Größe:** 468 B | **md5:** `3b83836d29ebe7d2b69c90988f4280e8`

```yaml
vault_path: /path/to/your/obsidian-vault
out_dir: .gewebe
embedder:
  provider: ollama          # oder: openai
  model: nomic-embed-text   # Beispielmodell (lokal)
index:
  top_k: 20
graph:
  cutoffs:
    # Beide Optionen anbieten – je nach aktuellem Parser:
    # (A) Ko-Vorkommen/gewichtete Kante:
    min_cooccur: 2
    min_weight: 0.15
    # (B) Falls der aktuelle Code noch auf Similarity-Schwelle hört:
    # min_similarity: 0.35
related:
  write_back: false
```
```

### 📄 merges/semantAH_merge_2510262237__semantAH_scripts.md

**Größe:** 2 KB | **md5:** `6f95bbc07c56199640c31d716995eb4e`

```markdown
### 📄 semantAH/scripts/build_graph.py

**Größe:** 537 B | **md5:** `e0dbd4975dc2c819a19398f5db393fa9`

```python
#!/usr/bin/env python3
"""Stub script to turn embeddings into graph nodes and edges."""

import json
from pathlib import Path

GEWEBE = Path(".gewebe")
NODES = GEWEBE / "nodes.jsonl"
EDGES = GEWEBE / "edges.jsonl"


def main() -> None:
    GEWEBE.mkdir(exist_ok=True)
    NODES.write_text(f"{json.dumps({'id': 'stub:node'})}\n")
    EDGES.write_text(f"{json.dumps({'s': 'stub:node', 'p': 'related', 'o': 'stub:other', 'w': 0.0})}\n")
    print("[stub] build_graph → wrote", NODES, "and", EDGES)


if __name__ == "__main__":
    main()
```

### 📄 semantAH/scripts/build_index.py

**Größe:** 405 B | **md5:** `865c35a95123b567cbeec93bcbdbcfab`

```python
#!/usr/bin/env python3
"""Stub script for building embeddings and chunk index artifacts."""

from pathlib import Path

OUTPUT = Path(".gewebe/embeddings.parquet")


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if not OUTPUT.exists():
        OUTPUT.write_text("id,text,embedding\n")
    print("[stub] build_index → wrote", OUTPUT)


if __name__ == "__main__":
    main()
```

### 📄 semantAH/scripts/update_related.py

**Größe:** 792 B | **md5:** `4c3c18bc29a86770cfb8e5c41027f861`

```python
#!/usr/bin/env python3
"""Stub script to inject related blocks into Markdown files."""

from pathlib import Path

RELATED_BLOCK = """<!-- related:auto:start -->\n## Related\n- [[Example]] — (0.00; stub)\n<!-- related:auto:end -->\n"""


def inject_related(note: Path) -> None:
    text = note.read_text(encoding="utf-8") if note.exists() else ""
    if "<!-- related:auto:start -->" in text:
        return
    note.write_text(text + "\n" + RELATED_BLOCK, encoding="utf-8")


def main() -> None:
    notes_dir = Path("notes_stub")
    notes_dir.mkdir(exist_ok=True)
    note = notes_dir / "example.md"
    note.write_text("# Example Note\n", encoding="utf-8")
    inject_related(note)
    print("[stub] update_related → injected block into", note)


if __name__ == "__main__":
    main()
```
```

### 📄 merges/semantAH_merge_2510262237__semantAH_systemd.md

**Größe:** 605 B | **md5:** `3793e684586fee86650c677123420840`

```markdown
### 📄 semantAH/systemd/vault-gewebe.service

**Größe:** 209 B | **md5:** `c8d19aaf3b4ea255f1671886b89596f5`

```plaintext
[Unit]
Description=semantAH nightly index build (index -> graph -> related)
After=default.target

[Service]
Type=oneshot
WorkingDirectory=%h/path/to/your/vault
ExecStart=%h/path/to/semantAH/.venv/bin/make all
```

### 📄 semantAH/systemd/vault-gewebe.timer

**Größe:** 134 B | **md5:** `08dba76201e550bc6446a15d74db51a2`

```plaintext
[Unit]
Description=Run semantAH nightly at 03:10

[Timer]
OnCalendar=*-*-* 03:10:00
Persistent=true

[Install]
WantedBy=timers.target
```
```

### 📄 merges/semantAH_merge_2510262237__systemd.md

**Größe:** 587 B | **md5:** `305dd628ced2901a66fe1e102331efd7`

```markdown
### 📄 systemd/vault-gewebe.service

**Größe:** 209 B | **md5:** `c8d19aaf3b4ea255f1671886b89596f5`

```plaintext
[Unit]
Description=semantAH nightly index build (index -> graph -> related)
After=default.target

[Service]
Type=oneshot
WorkingDirectory=%h/path/to/your/vault
ExecStart=%h/path/to/semantAH/.venv/bin/make all
```

### 📄 systemd/vault-gewebe.timer

**Größe:** 134 B | **md5:** `08dba76201e550bc6446a15d74db51a2`

```plaintext
[Unit]
Description=Run semantAH nightly at 03:10

[Timer]
OnCalendar=*-*-* 03:10:00
Persistent=true

[Install]
WantedBy=timers.target
```
```

### 📄 merges/semantAH_merge_2510262237__tests.md

**Größe:** 14 KB | **md5:** `28d344e24111ec6dd7d041c9013c54f1`

```markdown
### 📄 tests/conftest.py

**Größe:** 535 B | **md5:** `2df90d78a2e9f5492215bcb9d8f78da8`

```python
import os

try:
    from hypothesis import settings
    from hypothesis.errors import InvalidArgument
except Exception:  # pragma: no cover - hypothesis optional in some environments
    settings = None
else:
    try:
        settings.register_profile(
            "ci",
            settings(max_examples=100, deadline=None, derandomize=True),
        )
    except InvalidArgument:
        # Profile bereits gesetzt (z. B. bei mehrfacher Test-Session)
        pass
    settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "default"))
```

### 📄 tests/test_push_index.py

**Größe:** 4 KB | **md5:** `9de0c222da3761c9414b28f505974bff`

```python
import pandas as pd
import pytest

from itertools import permutations
from scripts.push_index import (
    to_batches,
    _derive_doc_id,
    _derive_chunk_id,
    _is_missing,
)


def test_namespace_fallback_and_grouping():
    df = pd.DataFrame(
        [
            {"doc_id": "d1", "namespace": "vault", "id": "c1", "text": "hello", "embedding": [0.1, 0.2]},
            {"doc_id": "d1", "namespace": float("nan"), "id": "c2", "text": "world", "embedding": [0.3, 0.4]},
            {"doc_id": "d2", "namespace": "   ", "id": "c3", "text": "!", "embedding": [0.5, 0.6]},
        ]
    )
    batches = list(to_batches(df, default_namespace="defaultNS"))

    keys = {(b["namespace"], b["doc_id"]): len(b["chunks"]) for b in batches}
    assert keys == {
        ("vault", "d1"): 1,
        ("defaultNS", "d1"): 1,
        ("defaultNS", "d2"): 1,
    }


def test_doc_id_derivation_order_and_missing():
    assert _derive_doc_id({"doc_id": "  abc  "}) == "abc"
    assert _derive_doc_id({"path": " /notes/n1.md "}) == "/notes/n1.md"
    assert _derive_doc_id({"id": "xyz"}) == "xyz"
    with pytest.raises(ValueError):
        _derive_doc_id({"doc_id": None, "path": "  ", "id": float("nan")})


def test_chunk_id_hash_fallback_is_stable_and_collision_resistant():
    record = {"text": "Same text here", "embedding": [1.0, 0.0]}
    cid1 = _derive_chunk_id(record, doc_id="D")
    cid2 = _derive_chunk_id(record, doc_id="D")
    assert cid1 == cid2
    assert cid1.startswith("D#t")

    record2 = {"__row": 42, "embedding": [1.0, 0.0]}
    cid3 = _derive_chunk_id(record2, doc_id="D")
    assert cid3 == "D#r42"

    record3 = {"embedding": [1.0, 0.0]}
    cid4 = _derive_chunk_id(record3, doc_id="D")
    assert cid4 == "D#chunk"


def test_chunk_id_fallback_stable_across_reordering():
    """Fallback per Text-Hash bleibt über beliebige Reihenfolgen stabil."""

    rows = [
        {"doc_id": "D", "text": "one", "embedding": [1.0, 0.0]},
        {"doc_id": "D", "text": "two", "embedding": [0.0, 1.0]},
        {"doc_id": "D", "text": "three", "embedding": [0.7, 0.7]},
    ]

    baseline = None
    for perm in permutations(rows):
        df = pd.DataFrame(list(perm))
        batches = list(to_batches(df, default_namespace="ns"))
        assert len(batches) == 1
        batch = batches[0]
        mapping = {c["text"]: c["id"] for c in batch["chunks"]}
        for cid in mapping.values():
            assert str(cid).startswith("D#")
            assert "nan" not in str(cid).lower()
        if baseline is None:
            baseline = mapping
        else:
            assert mapping == baseline


def test_chunk_id_global_ids_and_bool_skip():
    assert _derive_chunk_id({"chunk_id": "G#abc", "embedding": [1, 0]}, doc_id="D") == "G#abc"
    cid = _derive_chunk_id({"chunk_id": True, "text": "X", "embedding": [1, 0]}, doc_id="D")
    assert cid.startswith("D#t")


def test_is_missing_covers_nan_none_and_whitespace():
    assert _is_missing(None) is True
    assert _is_missing(float("nan")) is True
    assert _is_missing("   ") is True
    assert _is_missing("") is True
    assert _is_missing("x") is False


def test_to_batches_end_to_end_no_nan_ids_and_namespace_default():
    df = pd.DataFrame(
        [
            {"doc_id": "D1", "text": "alpha", "embedding": [0.1, 0.2]},
            {"doc_id": "D2", "namespace": float("nan"), "__row": 7, "embedding": [0.3, 0.4]},
            {"doc_id": "D3", "namespace": "   ", "embedding": [0.5, 0.6]},
        ]
    )
    default_ns = "vault-default"
    batches = list(to_batches(df, default_namespace=default_ns))

    for batch in batches:
        assert batch["namespace"] == default_ns
        for chunk in batch["chunks"]:
            chunk_id = str(chunk["id"]).lower()
            assert chunk_id != "nan"
            assert "nan" not in chunk_id
            assert chunk_id.strip() != ""
```

### 📄 tests/test_push_index_e2e.py

**Größe:** 6 KB | **md5:** `6b2872f11b0fae00322c27e9e90597fb`

```python
import json
import os
import signal
import subprocess
import sys
import shlex
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import pytest


def _prebuild_indexd(timeout_s: float = 300.0) -> None:
    """
    Baut das 'indexd'-Binary vor dem Start des Servers.
    Verhindert, dass der Health-Check wegen kalter Builds in CI zu früh ausfällt.
    """
    try:
        # Schneller Check: Wenn das Release/Debug-Binary schon existiert, überspringen wir den Build nicht,
        # sondern verlassen uns trotzdem auf cargo's inkrementellen Build (schnell, no-op).
        cmd = ["cargo", "build", "-q", "-p", "indexd"]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout_s)
    except subprocess.CalledProcessError as e:
        out = e.stdout.decode("utf-8", "replace") if e.stdout else ""
        pytest.fail(f"Prebuild of indexd failed (rc={e.returncode}). Output:\n{out}")
    except subprocess.TimeoutExpired as e:
        pytest.fail(
            "Prebuild of indexd timed out after "
            f"{timeout_s:.0f}s. Command: {shlex.join(e.cmd) if isinstance(e.cmd, (list, tuple)) else e.cmd}"
        )


def _healthz_deadline_from_env(default: float = 120.0) -> float:
    """Erlaubt Override der Health-Check-Deadline via ENV (INDEXD_E2E_HEALTHZ_DEADLINE)."""
    val = os.environ.get("INDEXD_E2E_HEALTHZ_DEADLINE")
    return float(val) if val else default


def _http_json(url: str, payload: dict | None = None, timeout: float = 5.0):
    req = urllib.request.Request(url)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req.add_header("content-type", "application/json")
    else:
        data = None
    with urllib.request.urlopen(req, data=data, timeout=timeout) as resp:
        body = resp.read()
        ctype = resp.headers.get("content-type", "")
        if "application/json" in ctype:
            return json.loads(body.decode("utf-8"))
        return body.decode("utf-8")


def _wait_for_healthz(base: str, deadline_s: float = 15.0):
    url = f"{base}/healthz"
    start = time.time()
    last_err: Exception | None = None
    while time.time() - start < deadline_s:
        try:
            text = _http_json(url, None, timeout=1.5)
            if text == "ok":
                return
        except Exception as e:  # noqa: BLE001
            last_err = e
        time.sleep(0.25)
    raise RuntimeError(f"healthz did not become ready: {last_err!r}")


@contextmanager
def run_indexd():
    """
    Baut 'indexd' vorab, startet dann 'cargo run -p indexd' im Hintergrund auf Port 8080,
    wartet auf /healthz (mit großzügiger Deadline) und räumt beim Verlassen auf.
    """
    # 0) Vorab-Build (kann auf kalten CI-Runnern mehrere Minuten dauern)
    _prebuild_indexd()
    env = os.environ.copy()
    # persistenz in tmp, damit Tests nichts in echte Arbeitsverzeichnisse schreiben
    tmp_state = Path.cwd() / ".test-indexd-state"
    tmp_state.mkdir(exist_ok=True)
    env["INDEXD_DB_PATH"] = str(tmp_state / "store.jsonl")

    proc = subprocess.Popen(
        ["cargo", "run", "-q", "-p", "indexd"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    try:
        # 1) Auf Health warten – großzügige Default-Deadline, via ENV überschreibbar
        _wait_for_healthz(
            "http://127.0.0.1:8080",
            deadline_s=_healthz_deadline_from_env(default=120.0),
        )
        yield proc
    finally:
        # Sauber beenden
        try:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        finally:
            # Logausgabe im Fehlerfall anhängen
            if proc.stdout:
                out = proc.stdout.read().decode("utf-8", "replace")
                sys.stdout.write("\n[indexd output]\n")
                sys.stdout.write(out)
                sys.stdout.write("\n[/indexd output]\n")


@pytest.mark.integration
def test_push_index_script_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # 1) Start server
    with run_indexd():
        base = "http://127.0.0.1:8080"

        # 2) Schreibe Minimal-Parquet in isoliertem Arbeitsverzeichnis
        work = tmp_path / "work"
        (work / ".gewebe").mkdir(parents=True)
        parquet = work / ".gewebe" / "embeddings.parquet"
        df = pd.DataFrame(
            [
                dict(
                    doc_id="D1",
                    namespace="ns",
                    id="c1",
                    text="hello world",
                    embedding=[1.0, 0.0],
                )
            ]
        )
        # pandas benötigt i.d.R. pyarrow/fastparquet – in diesem Projekt sollte pyarrow verfügbar sein.
        df.to_parquet(parquet)

        # 3) push_index.py gegen den laufenden Dienst ausführen
        # Hinweis: wir setzen CWD auf 'work', damit der Default-Pfad funktioniert;
        # übergeben aber explizit --embeddings zur Sicherheit.
        script = Path("scripts") / "push_index.py"
        cmd = [
            sys.executable,
            str(script),
            "--embeddings",
            str(parquet),
            "--endpoint",
            f"{base}/index/upsert",
        ]
        proc = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=25)
        if proc.returncode != 0:
            pytest.fail(f"push_index.py failed: rc={proc.returncode}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")

        # 4) Suche absetzen und Treffer prüfen
        res = _http_json(
            f"{base}/index/search",
            dict(query="hello", k=5, namespace="ns", embedding=[1.0, 0.0]),
            timeout=5.0,
        )
        results = res.get("results", [])
        assert len(results) == 1
        assert results[0]["doc_id"] == "D1"
        assert results[0]["chunk_id"] == "c1"
        assert results[0]["score"] > 0.0
```

### 📄 tests/test_push_index_property.py

**Größe:** 3 KB | **md5:** `3e12e82ce65a8caf3768a9cf692b1b88`

```python
import collections
from typing import Any, Dict, List, Tuple

import pandas as pd
import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, settings, strategies as st  # type: ignore

from scripts.push_index import to_batches


def _entries_from_batches(batches: List[Dict[str, Any]]) -> List[Tuple[str, str, str, str]]:
    """Flacht die Batches auf (namespace, doc_id, chunk_id, text)."""

    flattened: List[Tuple[str, str, str, str]] = []
    for batch in batches:
        namespace = str(batch["namespace"])
        doc_id = str(batch["doc_id"])
        for chunk in batch["chunks"]:
            chunk_id = str(chunk["id"])
            text = str(chunk.get("text", ""))
            flattened.append((namespace, doc_id, chunk_id, text))
    return flattened


_namespace_strategy = st.one_of(
    st.none(),
    st.floats(allow_nan=True),
    st.just(""),
    st.just("   "),
    st.text(min_size=1, max_size=8),
)

_doc_id_strategy = st.text(min_size=1, max_size=8)

_maybe_chunk_id = st.one_of(
    st.none(),
    st.booleans(),
    st.text(min_size=1, max_size=8),
)

_text_strategy = st.text(min_size=1, max_size=32)

_embedding_strategy = st.lists(
    st.floats(allow_nan=False, allow_infinity=False, width=16), min_size=2, max_size=2
)

_record_strategy = st.fixed_dictionaries(
    {
        "doc_id": _doc_id_strategy,
        "namespace": _namespace_strategy,
        "chunk_id": _maybe_chunk_id,
        "id": st.none(),
        "text": _text_strategy,
        "embedding": _embedding_strategy,
    }
)


def _counter(entries: List[Tuple[str, str, str, str]]) -> collections.Counter:
    return collections.Counter(entries)


@settings(max_examples=100, deadline=None)
@given(st.lists(_record_strategy, min_size=1, max_size=8))
def test_chunk_ids_stable_across_permutations(records: List[Dict[str, Any]]):
    """Chunk-IDs bleiben bei unterschiedlichen Reihenfolgen stabil."""

    default_namespace = "ns-default"

    df = pd.DataFrame(records)
    baseline_entries = _entries_from_batches(list(to_batches(df, default_namespace=default_namespace)))
    baseline_counter = _counter(baseline_entries)
    assert all("nan" not in chunk_id.lower() for (_, _, chunk_id, _) in baseline_entries)

    shuffled_df = df.sample(frac=1.0, random_state=123).reset_index(drop=True)
    reversed_df = df.iloc[::-1].reset_index(drop=True)

    for dframe in (shuffled_df, reversed_df):
        entries = _entries_from_batches(list(to_batches(dframe, default_namespace=default_namespace)))
        counter = _counter(entries)
        assert counter == baseline_counter
        assert all("nan" not in chunk_id.lower() for (_, _, chunk_id, _) in entries)


@pytest.mark.parametrize(
    "namespace_value",
    [None, "", "   ", float("nan"), "vault"],
)
def test_default_namespace_applied(namespace_value):
    df = pd.DataFrame(
        [
            {
                "doc_id": "D",
                "namespace": namespace_value,
                "text": "x",
                "embedding": [0.1, 0.2],
            }
        ]
    )
    batches = list(to_batches(df, default_namespace="vault-default"))
    assert batches[0]["namespace"] == "vault-default"
```
```

