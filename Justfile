# uv-powered Python shortcuts

py-init:
	uv sync

py-all:
	just py-init
	make all

py-index:
	uv run scripts/build_index.py

py-graph:
	uv run scripts/build_graph.py

py-related:
	uv run scripts/update_related.py
