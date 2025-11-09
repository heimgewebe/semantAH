import json
import tempfile
from pathlib import Path
from cli.ingest_intents import ingest_intents, main
import pytest

@pytest.fixture
def intent_data():
    return [
        {
            "ts": "2024-01-01T12:00:00Z",
            "actor": "user1",
            "goal": "Refactor the authentication module",
            "scope": {"repo": "heimgewebe/semantAH"},
            "context": {"tags": ["refactoring", "security"]},
        }
    ]

def test_ingest_intents(intent_data):
    with tempfile.TemporaryDirectory() as temp_dir:
        source_path = Path(temp_dir) / "intents.jsonl"
        nodes_path = Path(temp_dir) / "nodes.jsonl"
        edges_path = Path(temp_dir) / "edges.jsonl"

        with source_path.open("w", encoding="utf-8") as f:
            for record in intent_data:
                f.write(json.dumps(record) + "\n")

        # Create empty files for nodes and edges
        nodes_path.touch()
        edges_path.touch()

        ingest_intents(source_path, nodes_path, edges_path)

        with nodes_path.open("r", encoding="utf-8") as f:
            nodes = [json.loads(line) for line in f]

        with edges_path.open("r", encoding="utf-8") as f:
            edges = [json.loads(line) for line in f]

        assert len(nodes) == 5
        assert len(edges) == 4

        intent_node = next((n for n in nodes if n["label"] == "Intent"), None)
        assert intent_node is not None
        assert intent_node["ts"] == "2024-01-01T12:00:00Z"

def test_main_with_valid_data(intent_data):
    with tempfile.TemporaryDirectory() as temp_dir:
        source_path = Path(temp_dir) / "intents.jsonl"
        nodes_path = Path(temp_dir) / "nodes.jsonl"
        edges_path = Path(temp_dir) / "edges.jsonl"

        with source_path.open("w", encoding="utf-8") as f:
            for record in intent_data:
                f.write(json.dumps(record) + "\n")

        # Create empty files for nodes and edges
        nodes_path.touch()
        edges_path.touch()

        argv = [str(source_path), "--nodes-file", str(nodes_path), "--edges-file", str(edges_path)]
        assert main(argv) == 0

        with nodes_path.open("r", encoding="utf-8") as f:
            nodes = [json.loads(line) for line in f]

        with edges_path.open("r", encoding="utf-8") as f:
            edges = [json.loads(line) for line in f]

        assert len(nodes) == 5
        assert len(edges) == 4

def test_main_with_invalid_path():
    with tempfile.TemporaryDirectory() as temp_dir:
        source_path = Path(temp_dir) / "non_existent.jsonl"
        argv = [str(source_path)]
        assert main(argv) == 1
