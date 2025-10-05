#!/usr/bin/env python3
"""Stub script to turn embeddings into graph nodes and edges."""

import json
from pathlib import Path

GEWEBE = Path(".gewebe")
NODES = GEWEBE / "nodes.jsonl"
EDGES = GEWEBE / "edges.jsonl"


def main() -> None:
    GEWEBE.mkdir(exist_ok=True)
    NODES.write_text("{}\n".format(json.dumps({"id": "stub:node"})))
    EDGES.write_text("{}\n".format(json.dumps({"s": "stub:node", "p": "related", "o": "stub:other", "w": 0.0})))
    print("[stub] build_graph → wrote", NODES, "and", EDGES)


if __name__ == "__main__":
    main()
