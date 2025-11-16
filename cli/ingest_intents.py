#!/usr/bin/env python3
"""Read Intent-Log JSONL and transform events to graph nodes and edges."""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def sha256_hash(data: str) -> str:
    """Return the SHA256 hash of the given data."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def process_intent_record(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Process a single intent record and return a list of graph elements."""
    actor = record.get("actor")
    goal = record.get("goal")
    timestamp = record.get("ts")

    if not all([actor, goal, timestamp]):
        return []

    intent_id = f"intent:{sha256_hash(f'{timestamp}{actor}{goal}')}"

    intent_node = {
        "id": intent_id,
        "label": "Intent",
        "ts": timestamp,
    }
    meta = record.get("meta", {})
    if isinstance(meta, dict):
        intent_node.update(meta)

    nodes = [intent_node]
    edges = []

    # Create actor node and edge
    actor_id = f"actor:{actor}"
    nodes.append({"id": actor_id, "label": "Actor"})
    edges.append({"s": actor_id, "p": "declares", "o": intent_id})

    # Create scope nodes and edges
    scope = record.get("scope", {})
    if "repo" in scope:
        repo_id = f"repo:{scope['repo']}"
        nodes.append({"id": repo_id, "label": "Repo"})
        edges.append({"s": intent_id, "p": "scopes", "o": repo_id})
    if "path" in scope:
        path_id = f"path:{scope['path']}"
        nodes.append({"id": path_id, "label": "Path"})
        edges.append({"s": intent_id, "p": "scopes", "o": path_id})

    # Create tag nodes and edges
    context = record.get("context", {})
    tags = context.get("tags", [])
    for tag in tags:
        tag_id = f"tag:{tag}"
        nodes.append({"id": tag_id, "label": "Tag"})
        edges.append({"s": intent_id, "p": "mentions", "o": tag_id})

    return nodes + edges


def ingest_intents(source_path: Path, nodes_path: Path, edges_path: Path):
    """Ingest intents from the source file and append to nodes and edges files."""
    with source_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                elements = process_intent_record(record)
                with (
                    nodes_path.open("a", encoding="utf-8") as nodes_file,
                    edges_path.open("a", encoding="utf-8") as edges_file,
                ):
                    for element in elements:
                        if "p" in element:  # It's an edge
                            edges_file.write(json.dumps(element) + "\n")
                        else:  # It's a node
                            nodes_file.write(json.dumps(element) + "\n")
            except json.JSONDecodeError:
                print(f"Warning: Could not decode JSON: {line}", file=sys.stderr)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Ingest intent events and update the knowledge graph."
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Path to the intent JSONL file (e.g., export/os.intent.jsonl)",
    )
    parser.add_argument(
        "--nodes-file",
        type=Path,
        default=Path(".gewebe/nodes.jsonl"),
        help="Path to the nodes JSONL file",
    )
    parser.add_argument(
        "--edges-file",
        type=Path,
        default=Path(".gewebe/edges.jsonl"),
        help="Path to the edges JSONL file",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Main function."""
    args = parse_args(argv)
    try:
        ingest_intents(args.source, args.nodes_file, args.edges_file)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
