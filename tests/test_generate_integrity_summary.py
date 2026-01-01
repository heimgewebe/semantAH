"""Tests for scripts/generate_integrity_summary.py"""

from __future__ import annotations

import json
from pathlib import Path


def _script_path() -> Path:
    """Get path to generate_integrity_summary.py script."""
    here = Path(__file__).resolve()
    return here.parents[1] / "scripts" / "generate_integrity_summary.py"


def _import_script():
    """Import the script as a module."""
    import importlib.util
    import sys

    script = _script_path()
    spec = importlib.util.spec_from_file_location("generate_integrity_summary", script)
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_integrity_summary"] = module
    spec.loader.exec_module(module)
    return module


def test_deterministic_timestamp_via_source_date_epoch(tmp_path, monkeypatch):
    """Test that SOURCE_DATE_EPOCH produces deterministic timestamps."""
    # Setup: Create minimal directory structure
    contracts_dir = tmp_path / "contracts"
    artifacts_dir = tmp_path / "artifacts"
    contracts_dir.mkdir()
    artifacts_dir.mkdir()

    # Set deterministic timestamp: 2023-11-14T22:13:20Z
    epoch = "1700000000"
    monkeypatch.setenv("SOURCE_DATE_EPOCH", epoch)
    monkeypatch.chdir(tmp_path)

    # Import and run
    script = _import_script()
    script.main()

    # Assert: Output files exist
    summary_path = tmp_path / "reports" / "integrity" / "summary.json"
    event_payload_path = tmp_path / "reports" / "integrity" / "event_payload.json"
    assert summary_path.is_file()
    assert event_payload_path.is_file()

    # Assert: Timestamp is deterministic
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["generated_at"] == "2023-11-14T22:13:20Z"
    assert "status" in summary

    event_payload = json.loads(event_payload_path.read_text(encoding="utf-8"))
    assert event_payload["generated_at"] == "2023-11-14T22:13:20Z"
    assert "status" in event_payload


def test_gap_detection_claim_without_artifact(tmp_path, monkeypatch):
    """Test that gap detection identifies claims without matching artifacts."""
    # Setup: Create contracts/ with a schema but no corresponding artifact
    contracts_dir = tmp_path / "contracts"
    artifacts_dir = tmp_path / "artifacts"
    contracts_dir.mkdir()
    artifacts_dir.mkdir()

    # Create a schema file
    (contracts_dir / "foo.schema.json").write_text(json.dumps({}))

    monkeypatch.chdir(tmp_path)

    # Run
    script = _import_script()
    script.main()

    # Assert: Gap is detected
    summary_path = tmp_path / "reports" / "integrity" / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert summary["counts"]["claims"] == 1
    assert summary["counts"]["loop_gaps"] == 1
    assert "foo.schema.json" in summary["details"]["claims"]
    assert "foo" in summary["details"]["loop_gaps"]
    assert summary["status"] == "WARN"


def test_artifact_listing_only_top_level_no_self_reference(tmp_path, monkeypatch):
    """Test that artifacts list only includes top-level files, not integrity subdirectory."""
    # Setup: Create schema and corresponding artifact
    contracts_dir = tmp_path / "contracts"
    artifacts_dir = tmp_path / "artifacts"
    contracts_dir.mkdir()
    artifacts_dir.mkdir()

    (contracts_dir / "foo.schema.json").write_text(json.dumps({}))
    (artifacts_dir / "foo.json").write_text(json.dumps({"data": "test"}))

    monkeypatch.chdir(tmp_path)

    # Run
    script = _import_script()
    script.main()

    # Assert: foo.json is in artifacts list
    summary_path = tmp_path / "reports" / "integrity" / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert "foo.json" in summary["details"]["artifacts"]
    # Assert: Exactly one artifact counted
    assert summary["counts"]["artifacts"] == 1

    # Assert: summary.json and event_payload.json are NOT in artifacts list
    # (they are in integrity subdirectory)
    assert "summary.json" not in summary["details"]["artifacts"]
    assert "event_payload.json" not in summary["details"]["artifacts"]

    # Assert: No gap since artifact exists
    assert summary["counts"]["loop_gaps"] == 0
    assert "foo" not in summary["details"]["loop_gaps"]
    assert summary["status"] == "OK"


def test_multiple_claims_partial_gaps(tmp_path, monkeypatch):
    """Test with multiple claims where some have artifacts and some don't."""
    # Setup
    contracts_dir = tmp_path / "contracts"
    artifacts_dir = tmp_path / "artifacts"
    contracts_dir.mkdir()
    artifacts_dir.mkdir()

    # Create schemas
    (contracts_dir / "alpha.schema.json").write_text(json.dumps({}))
    (contracts_dir / "beta.schema.json").write_text(json.dumps({}))
    (contracts_dir / "gamma.schema.json").write_text(json.dumps({}))

    # Create artifacts only for alpha and gamma
    (artifacts_dir / "alpha.json").write_text(json.dumps({}))
    (artifacts_dir / "gamma.json").write_text(json.dumps({}))

    monkeypatch.chdir(tmp_path)

    # Run
    script = _import_script()
    script.main()

    # Assert
    summary_path = tmp_path / "reports" / "integrity" / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert summary["counts"]["claims"] == 3
    assert summary["counts"]["artifacts"] == 2
    assert summary["counts"]["loop_gaps"] == 1
    assert "beta" in summary["details"]["loop_gaps"]
    assert "alpha" not in summary["details"]["loop_gaps"]
    assert "gamma" not in summary["details"]["loop_gaps"]
    assert summary["status"] == "WARN"


def test_custom_output_directory(tmp_path, monkeypatch):
    """Test that INTEGRITY_OUT_DIR environment variable works."""
    # Setup
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir()
    (tmp_path / "artifacts").mkdir()

    custom_out = "custom_out"
    monkeypatch.setenv("INTEGRITY_OUT_DIR", custom_out)
    monkeypatch.chdir(tmp_path)

    # Run
    script = _import_script()
    script.main()

    # Assert: Files are in custom directory
    summary_path = tmp_path / custom_out / "summary.json"
    event_payload_path = tmp_path / custom_out / "event_payload.json"
    assert summary_path.is_file()
    assert event_payload_path.is_file()


def test_missing_contracts_directory_raises_error(tmp_path, monkeypatch):
    """Test that missing contracts/ directory produces clear error message."""
    # Setup: tmp_path without contracts/ directory
    monkeypatch.chdir(tmp_path)

    # Run and assert
    script = _import_script()
    try:
        script.main()
        assert False, "Expected SystemExit to be raised"
    except SystemExit as e:
        assert "contracts/ missing: integrity loop cannot evaluate claims" in str(e)
