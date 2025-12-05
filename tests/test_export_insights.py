from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _script_path() -> Path:
    # tests/  -> Repo-Root ist ein Verzeichnis darüber
    here = Path(__file__).resolve()
    return here.parents[1] / "scripts" / "export_insights.py"


def test_export_insights_creates_daily_and_today(tmp_path, monkeypatch):
    vault_root = tmp_path / "vault"
    notes_dir = vault_root / "projektA"
    notes_dir.mkdir(parents=True)

    # Eine Dummy-Note, damit es mindestens ein Topic gibt
    (notes_dir / "note1.md").write_text("# Test\n\nInhalt.", encoding="utf-8")

    monkeypatch.setenv("VAULT_ROOT", str(vault_root))

    script = _script_path()
    assert script.is_file(), f"Skript nicht gefunden: {script}"

    # Ausführen wie im echten Betrieb
    result = subprocess.run(
        [sys.executable, str(script)],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(script.parents[1]),
    )

    # Für Debugging bei Fehlschlägen:
    stderr = result.stderr.strip()
    if stderr:
        print(stderr)

    insights_root = vault_root / ".gewebe" / "insights"
    today_path = insights_root / "today.json"

    assert today_path.is_file(), "today.json wurde nicht erzeugt"

    data = json.loads(today_path.read_text(encoding="utf-8"))

    # Minimale Schema-Checks (insights.daily.schema.json-kompatibel)
    assert "ts" in data, "ts fehlt"
    assert isinstance(data["ts"], str)

    assert "topics" in data, "topics fehlt"
    assert isinstance(data["topics"], list)
    assert data["topics"], "topics darf nicht leer sein"

    first_topic = data["topics"][0]
    assert isinstance(first_topic, list)
    assert len(first_topic) == 2
    assert isinstance(first_topic[0], str)
    assert isinstance(first_topic[1], (int, float))

    # Fragen und Deltas sind aktuell leer, was laut Schema zulässig ist
    assert "questions" in data
    assert isinstance(data["questions"], list)
    assert data["questions"] == []

    assert "deltas" in data
    assert isinstance(data["deltas"], list)
    assert data["deltas"] == []


def test_export_insights_creates_daily_file(tmp_path, monkeypatch):
    """Verify that the dated daily/YYYY-MM-DD.json file is created."""
    from datetime import date

    vault_root = tmp_path / "vault"
    notes_dir = vault_root / "notes"
    notes_dir.mkdir(parents=True)
    (notes_dir / "test.md").write_text("# Test Note", encoding="utf-8")

    monkeypatch.setenv("VAULT_ROOT", str(vault_root))

    script = _script_path()
    subprocess.run(
        [sys.executable, str(script)],
        check=True,
        capture_output=True,
        text=True,
    )

    insights_root = vault_root / ".gewebe" / "insights"
    daily_dir = insights_root / "daily"
    today = date.today().isoformat()
    daily_path = daily_dir / f"{today}.json"

    assert daily_path.is_file(), f"daily/{today}.json wurde nicht erzeugt"

    data = json.loads(daily_path.read_text(encoding="utf-8"))
    assert data["ts"] == today


def test_export_insights_missing_vault_root(tmp_path, monkeypatch):
    """Test error handling when VAULT_ROOT is not set."""
    monkeypatch.delenv("VAULT_ROOT", raising=False)

    script = _script_path()
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "VAULT_ROOT ist nicht gesetzt" in result.stderr


def test_export_insights_nonexistent_vault(tmp_path, monkeypatch):
    """Test error handling when VAULT_ROOT points to non-existent path."""
    nonexistent = tmp_path / "does_not_exist"
    monkeypatch.setenv("VAULT_ROOT", str(nonexistent))

    script = _script_path()
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "nicht existierenden Pfad" in result.stderr


def test_export_insights_vault_is_file(tmp_path, monkeypatch):
    """Test error handling when VAULT_ROOT points to a file, not directory."""
    file_path = tmp_path / "not_a_directory.txt"
    file_path.write_text("test")
    monkeypatch.setenv("VAULT_ROOT", str(file_path))

    script = _script_path()
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "muss auf ein Verzeichnis zeigen" in result.stderr


def test_export_insights_empty_vault(tmp_path, monkeypatch):
    """Test edge case where vault has no markdown files."""
    vault_root = tmp_path / "empty_vault"
    vault_root.mkdir(parents=True)

    monkeypatch.setenv("VAULT_ROOT", str(vault_root))

    script = _script_path()
    subprocess.run(
        [sys.executable, str(script)],
        check=True,
        capture_output=True,
        text=True,
    )

    insights_root = vault_root / ".gewebe" / "insights"
    today_path = insights_root / "today.json"

    assert today_path.is_file()

    data = json.loads(today_path.read_text(encoding="utf-8"))
    # Empty vault should fall back to [("vault", 1.0)]
    assert data["topics"] == [["vault", 1.0]]


def test_export_insights_topic_weights(tmp_path, monkeypatch):
    """Test that topic weights are correctly calculated and normalized."""
    vault_root = tmp_path / "vault"

    # Create files in different topics
    (vault_root / "topic1").mkdir(parents=True)
    (vault_root / "topic2").mkdir(parents=True)

    # topic1: 3 files
    (vault_root / "topic1" / "a.md").write_text("# A", encoding="utf-8")
    (vault_root / "topic1" / "b.md").write_text("# B", encoding="utf-8")
    (vault_root / "topic1" / "c.md").write_text("# C", encoding="utf-8")

    # topic2: 1 file
    (vault_root / "topic2" / "d.md").write_text("# D", encoding="utf-8")

    monkeypatch.setenv("VAULT_ROOT", str(vault_root))

    script = _script_path()
    subprocess.run(
        [sys.executable, str(script)],
        check=True,
        capture_output=True,
        text=True,
    )

    insights_root = vault_root / ".gewebe" / "insights"
    today_path = insights_root / "today.json"

    data = json.loads(today_path.read_text(encoding="utf-8"))

    # Convert topics list to dict for easier testing
    topics_dict = {name: weight for name, weight in data["topics"]}

    # topic1 should have weight 0.75 (3/4), topic2 should have 0.25 (1/4)
    assert "topic1" in topics_dict
    assert "topic2" in topics_dict
    assert topics_dict["topic1"] == 0.75
    assert topics_dict["topic2"] == 0.25


def test_export_insights_excludes_hidden_dirs(tmp_path, monkeypatch):
    """Test that hidden directories like .gewebe are excluded from scanning."""
    vault_root = tmp_path / "vault"
    normal_dir = vault_root / "normal"
    hidden_dir = vault_root / ".gewebe" / "data"

    normal_dir.mkdir(parents=True)
    hidden_dir.mkdir(parents=True)

    # Create files in both directories
    (normal_dir / "visible.md").write_text("# Visible", encoding="utf-8")
    (hidden_dir / "hidden.md").write_text("# Hidden", encoding="utf-8")

    monkeypatch.setenv("VAULT_ROOT", str(vault_root))

    script = _script_path()
    subprocess.run(
        [sys.executable, str(script)],
        check=True,
        capture_output=True,
        text=True,
    )

    insights_root = vault_root / ".gewebe" / "insights"
    today_path = insights_root / "today.json"

    data = json.loads(today_path.read_text(encoding="utf-8"))

    # Should only have "normal" topic, not ".gewebe"
    topic_names = [name for name, _ in data["topics"]]
    assert "normal" in topic_names
    assert ".gewebe" not in topic_names
