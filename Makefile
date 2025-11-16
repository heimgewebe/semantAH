.PHONY: 	uv-sync venv sync index graph related push-index all demo clean py-freeze insights-today ingest-intents	test test-integration coverage coverage-clean 	test-rust lint-rust audit-rust cov-rust cov-rust-html cov-rust-clean

UV := $(shell command -v uv 2>/dev/null)
ifeq ($(UV),)
$(error "uv is not installed. Install: https://docs.astral.sh/uv/getting-started/")
endif

CARGO ?= cargo
RUSTFLAGS ?= -D warnings

uv-sync:
	uv sync

venv: uv-sync

sync: uv-sync

index:
	uv run tools/build_index.py

graph:
	uv run tools/build_graph.py

related:
	uv run tools/update_related.py

push-index:
	uv run scripts/push_index.py

all: uv-sync index graph related

# --- Python tests (uv) -------------------------------------------------------
# Erwartung: `uv sync` wurde bereits ausgeführt. Für lokale Nutzung mit Extras:
#   uv sync -E test

test:
	uv run pytest -q -m "not integration"

# Integration-Tests (nur @integration)
test-integration:
	uv run pytest -q -m "integration" -v

# Coverage-Report (Unit-only standardmäßig). Erzeugt:
#   reports/coverage-unit.xml (Cobertura/XML)
#   reports/.coverage         (sqlite)
coverage: | coverage-clean
	mkdir -p reports
	uv run pytest -q -m "not integration" \
	  --junitxml=reports/unit-junit.xml \
	  --cov=. \
	  --cov-report=xml:reports/coverage-unit.xml \
	  --cov-report=term-missing:skip-covered
	@test ! -f .coverage || mv .coverage reports/.coverage

coverage-clean:
	rm -f .coverage
	rm -rf reports

# --- Rust: Tests, Lint, Audit, Coverage -------------------------------------

test-rust:
	$(CARGO) test --workspace --all-features --locked -- --nocapture

lint-rust:
	$(CARGO) clippy --workspace --all-features -- -D warnings

audit-rust:
	@if ! command -v cargo-audit >/dev/null 2>&1; then \
	  echo "cargo-audit nicht gefunden. Installation: 'cargo install cargo-audit'"; \
	  exit 1; \
	fi
	cargo audit

cov-rust: | cov-rust-clean
	@if ! command -v cargo-llvm-cov >/dev/null 2>&1; then \
	  echo "cargo-llvm-cov nicht gefunden. Installation: 'cargo install cargo-llvm-cov'"; \
	  exit 1; \
	fi
	mkdir -p reports
	cargo llvm-cov --workspace --lcov --output-path reports/rust-lcov.info
	@echo "LCOV geschrieben nach reports/rust-lcov.info"

cov-rust-html: | cov-rust-clean
	@if ! command -v cargo-llvm-cov >/dev/null 2>&1; then \
	  echo "cargo-llvm-cov nicht gefunden. Installation: 'cargo install cargo-llvm-cov'"; \
	  exit 1; \
	fi
	mkdir -p reports/llvm-cov
	cargo llvm-cov --workspace --html --output-dir reports/llvm-cov
	@echo "HTML-Report unter reports/llvm-cov/index.html"

cov-rust-clean:
	rm -rf reports/rust-lcov.info reports/llvm-cov

.PHONY: insights-today
insights-today:
	@test -f chronik/data/aussen.jsonl || { echo "fehlend: chronik/data/aussen.jsonl"; exit 1; }
	uv run cli/ingest_chronik.py chronik/data/aussen.jsonl
	@command -v npx >/dev/null 2>&1 || { echo "Node/npx fehlt (für ajv-cli)"; exit 1; }
	npx -y ajv-cli@5 validate --spec=draft2020 --validate-formats=false -s contracts/insights.schema.json -d vault/.gewebe/insights/today.json

.PHONY: ingest-intents
ingest-intents:
	@test -f export/os.intent.jsonl || { echo "fehlend: export/os.intent.jsonl"; exit 1; }
	uv run cli/ingest_intents.py export/os.intent.jsonl

.PHONY: demo
demo:
	@echo ">> Demo-Lauf mit examples/semantah.example.yml"
	@test -f semantah.yml || cp examples/semantah.example.yml semantah.yml
	$(MAKE) all

clean:
	rm -f .gewebe/embeddings.parquet
	rm -f .gewebe/nodes.jsonl .gewebe/edges.jsonl
	# Cache/Build-Artefakte freiwillig:
	# rm -rf .uv .venv

py-freeze:
	mkdir -p .gewebe/reports
	uv export --format=requirements-txt > .gewebe/reports/requirements-frozen.txt
	@echo "Lock-Metadaten → .gewebe/reports/requirements-frozen.txt"
