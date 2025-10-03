.PHONY: sync index graph related all clean

sync:
	uv sync

index:
	uv run scripts/build_index.py

graph:
	uv run scripts/build_graph.py

related:
	uv run scripts/update_related.py

all: index graph related

clean:
	@rm -rf .gewebe
	@rm -rf notes_stub
