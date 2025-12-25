from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path


def _script_path() -> Path:
    # tests/  -> Repo-Root ist ein Verzeichnis darüber
    here = Path(__file__).resolve()
    return here.parents[1] / "scripts" / "export_daily_insights.py"


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
    (topic_dir / "note.md").write_text("# Test")

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
    topics = dict(data["topics"])
    assert "test_topic" in topics
    assert topics["test_topic"] == 1.0
