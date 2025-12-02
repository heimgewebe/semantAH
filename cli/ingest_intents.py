#!/usr/bin/env python3
"""Read Intent-Log JSONL and transform events to graph nodes and edges."""

import argparse
import hashlib
import json
import sys
import traceback
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
        print(
            f"Warning: Skipping record with missing fields (actor={actor!r}, "
            f"goal={goal!r}, ts={timestamp!r})",
            file=sys.stderr,
        )
        return []

    intent_id = f"intent:{sha256_hash(f'{timestamp}{actor}{goal}')}"

    intent_node = {
        "id": intent_id,
        "type": "Intent",
        "title": goal,
        "updated_at": timestamp,
    }
    meta = record.get("meta", {})
    if isinstance(meta, dict):
        # Update with meta but preserve updated_at
        for key, value in meta.items():
            if key not in ("id", "type", "title", "updated_at"):
                intent_node[key] = value

    nodes = [intent_node]
    edges = []

    # Create actor node and edge
    actor_id = f"actor:{actor}"
    nodes.append({"id": actor_id, "type": "Actor", "title": actor})
    edges.append({"src": actor_id, "rel": "declares", "dst": intent_id})

    # Create scope nodes and edges
    scope = record.get("scope", {})
    if "repo" in scope:
        repo_id = f"repo:{scope['repo']}"
        nodes.append({"id": repo_id, "type": "Repo", "title": scope["repo"]})
        edges.append({"src": intent_id, "rel": "scopes", "dst": repo_id})
    if "path" in scope:
        path_id = f"path:{scope['path']}"
        nodes.append({"id": path_id, "type": "Path", "title": scope["path"]})
        edges.append({"src": intent_id, "rel": "scopes", "dst": path_id})

    # Create tag nodes and edges
    context = record.get("context", {})
    tags = context.get("tags", [])
    for tag in tags:
        tag_id = f"tag:{tag}"
        nodes.append({"id": tag_id, "type": "Tag", "title": tag})
        edges.append({"src": intent_id, "rel": "mentions", "dst": tag_id})

    return nodes + edges


def ingest_intents(source_path: Path, nodes_path: Path, edges_path: Path):
    """Ingest intents from the source file and append to nodes and edges files."""
    with (
        source_path.open("r", encoding="utf-8") as handle,
        nodes_path.open("a", encoding="utf-8") as nodes_file,
        edges_path.open("a", encoding="utf-8") as edges_file,
    ):
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                elements = process_intent_record(record)
                for element in elements:
                    if "rel" in element:  # It's an edge
                        edges_file.write(json.dumps(element) + "\n")
                    else:  # It's a node
                        nodes_file.write(json.dumps(element) + "\n")
            except json.JSONDecodeError:
                print(f"Warning: Could not decode JSON: {line}", file=sys.stderr)
            except Exception as e:
                print(f"Warning: Failed to process record: {e}", file=sys.stderr)
                # We do not print full traceback here to avoid log spam on bulk ingest,
                # but we continue to the next record.


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
    except (OSError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
