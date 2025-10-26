.PHONY: uv-sync venv sync index graph related push-index all demo clean py-freeze insights-today

UV := $(shell command -v uv 2>/dev/null)
ifeq ($(UV),)
$(error "uv is not installed. Install: https://docs.astral.sh/uv/getting-started/")
endif

uv-sync:
	uv sync

venv: uv-sync

sync: uv-sync

index:
	uv run scripts/build_index.py

graph:
	uv run scripts/build_graph.py

related:
	uv run scripts/update_related.py

push-index:
	uv run scripts/push_index.py

all: uv-sync index graph related

.PHONY: insights-today
insights-today:
	@test -f leitstand/data/aussen.jsonl || { echo "fehlend: leitstand/data/aussen.jsonl"; exit 1; }
	uv run cli/ingest_leitstand.py leitstand/data/aussen.jsonl
	@command -v npx >/dev/null 2>&1 || { echo "Node/npx fehlt (für ajv-cli)"; exit 1; }
	npx -y ajv-cli@5 validate --spec=draft2020 --validate-formats=false -s contracts/insights.schema.json -d vault/.gewebe/insights/today.json

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
