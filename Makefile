.PHONY: uv-sync venv sync index graph related all demo clean py-freeze

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

all: uv-sync index graph related

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
	uv export --frozen --format=requirements-txt > .gewebe/reports/requirements-frozen.txt
	@echo "Lock-Metadaten → .gewebe/reports/requirements-frozen.txt"
