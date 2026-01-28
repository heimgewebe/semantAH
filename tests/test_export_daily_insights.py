from __future__ import annotations

import json
import pytest
import subprocess
import sys
from datetime import date
from pathlib import Path


def _script_path() -> Path:
    # tests/  -> Repo-Root ist ein Verzeichnis darüber
    here = Path(__file__).resolve()
    return here.parents[1] / "scripts" / "export_daily_insights.py"


def _parse_topics(data: dict) -> dict:
    """Helper to robustly parse topics from the JSON output."""
    if "topics" not in data:
        pytest.fail("Missing 'topics' in output JSON")

    topics_raw = data["topics"]
    if isinstance(topics_raw, dict):
        return topics_raw
    try:
        return dict(topics_raw)
    except Exception as e:
        pytest.fail(f"Unexpected topics format: {type(topics_raw)}; error: {e}")


def test_export_daily_insights_creates_valid_artifact(tmp_path):
    output_path = tmp_path / "artifacts" / "insights.daily.json"

    script = _script_path()
    assert script.is_file(), f"Skript nicht gefunden: {script}"

    # Run without vault (fallback mode)
    subprocess.run(
        [sys.executable, str(script), "--output", str(output_path)],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(script.parents[1]),
    )

    assert output_path.is_file()

    data = json.loads(output_path.read_text(encoding="utf-8"))

    # Check structure
    assert data["ts"] == date.today().isoformat()
    assert data["source"] == "semantAH"
    assert "metadata" in data
    assert "generated_at" in data["metadata"]
    # Check fallback topic
    assert data["topics"] == [["vault", 1.0]]
    assert data["questions"] == []
    assert data["deltas"] == []


def test_export_daily_insights_with_vault(tmp_path):
    vault_root = tmp_path / "vault"
    topic_dir = vault_root / "test_topic"
    topic_dir.mkdir(parents=True)
    (topic_dir / "note.md").write_text("# Test", encoding="utf-8")

    output_path = tmp_path / "out.json"

    script = _script_path()

    subprocess.run(
        [
            sys.executable,
            str(script),
            "--output",
            str(output_path),
            "--vault-root",
            str(vault_root),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(script.parents[1]),
    )

    data = json.loads(output_path.read_text(encoding="utf-8"))

    # Check topic extraction
    topics = _parse_topics(data)
    assert "test_topic" in topics
    assert topics["test_topic"] == 1.0


def test_export_daily_insights_with_observatory(tmp_path):
    # Mock observatory file
    obs_path = tmp_path / "knowledge.observatory.json"
    obs_data = {
        "observatory_id": "test-obs-123",
        "generated_at": "2025-01-01T00:00:00Z",
        "source": {"component": "test", "version": "1"},
        "topics": [
            {"topic": "Alpha", "confidence": 0.9},
            {"topic": "Beta", "confidence": 0.8},
            {"topic": "Gamma", "confidence": 0.1},  # Low confidence
        ],
        "signals": [],
        "blind_spots": [],
        "considered_but_rejected": [],
    }
    obs_path.write_text(json.dumps(obs_data), encoding="utf-8")

    output_path = tmp_path / "out_obs.json"
    script = _script_path()

    subprocess.run(
        [
            sys.executable,
            str(script),
            "--output",
            str(output_path),
            "--observatory",
            str(obs_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(script.parents[1]),
    )

    data = json.loads(output_path.read_text(encoding="utf-8"))

    # Verify observatory data usage
    topics = _parse_topics(data)

    assert "Alpha" in topics
    assert topics["Alpha"] == 0.9
    assert "Beta" in topics
    assert topics["Beta"] == 0.8

    # Check metadata additions
    meta = data["metadata"]
    assert "observatory_ref" in meta
    assert meta["observatory_ref"] == "test-obs-123"

    # Check uncertainty (1 - avg(0.9, 0.8, 0.1) = 1 - 0.6 = 0.4)
    assert "uncertainty" in meta
    assert meta["uncertainty"] == 0.4


def test_export_daily_insights_ignores_hidden_content(tmp_path):
    """
    Ensures that hidden directories and files (starting with .) are excluded
    from the vault scan.
    """
    vault_root = tmp_path / "vault_hidden_test"
    vault_root.mkdir()

    # 1. Visible content
    # Structure: vault_root/visible_topic/note.md
    visible_topic_dir = vault_root / "visible_topic"
    visible_topic_dir.mkdir()
    (visible_topic_dir / "note.md").write_text("# Visible", encoding="utf-8")

    # 2. Hidden Directory
    # Structure: vault_root/.hidden_topic/note.md
    hidden_topic_dir = vault_root / ".hidden_topic"
    hidden_topic_dir.mkdir()
    (hidden_topic_dir / "note.md").write_text("# Hidden", encoding="utf-8")

    # 3. Hidden File in Visible Directory
    # Structure: vault_root/visible_topic/.hidden_note.md
    hidden_file_dir = vault_root / "hidden_file_dir"
    hidden_file_dir.mkdir()
    (hidden_file_dir / ".hidden_note.md").write_text("# Hidden Note", encoding="utf-8")

    output_path = tmp_path / "out_hidden.json"
    script = _script_path()

    subprocess.run(
        [
            sys.executable,
            str(script),
            "--output",
            str(output_path),
            "--vault-root",
            str(vault_root),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(script.parents[1]),
    )

    data = json.loads(output_path.read_text(encoding="utf-8"))
    topics = _parse_topics(data)

    # Assertions
    # 1. Visible topic must be present
    assert "visible_topic" in topics, "Visible topic should be detected"

    # 2. Hidden directory topic must NOT be present
    assert ".hidden_topic" not in topics, "Hidden directory should be skipped"

    # 3. Directory with only hidden file must NOT be present
    assert "hidden_file_dir" not in topics, "Hidden files should be ignored"
