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
    node_data = {"id": "stub:node", "type": "Note", "title": "Stub Node"}
    NODES.write_text(f"{json.dumps(node_data)}\n")
    edge_data = {"src": "stub:node", "rel": "related", "dst": "stub:other", "weight": 0.0}
    EDGES.write_text(f"{json.dumps(edge_data)}\n")
    print("[stub] build_graph → wrote", NODES, "and", EDGES)


if __name__ == "__main__":
    main()
