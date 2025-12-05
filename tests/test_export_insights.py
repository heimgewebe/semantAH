from __future__ import annotations

import json
import os
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
    assert isinstance(first_topic, list) and len(first_topic) == 2
    assert isinstance(first_topic[0], str)
    assert isinstance(first_topic[1], (int, float))

    # Fragen und Deltas sind aktuell leer, was laut Schema zulässig ist
    assert "questions" in data
    assert isinstance(data["questions"], list)
    assert data["questions"] == []

    assert "deltas" in data
    assert isinstance(data["deltas"], list)
    assert data["deltas"] == []
