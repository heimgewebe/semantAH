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

    # Assert: Output files exist (Canonical Path: reports/integrity)
    summary_path = tmp_path / "reports" / "integrity" / "summary.json"
    event_payload_path = tmp_path / "reports" / "integrity" / "event_payload.json"
    event_path = tmp_path / "reports" / "integrity" / "event.json"
    assert summary_path.is_file()
    assert event_payload_path.is_file()
    assert event_path.is_file()

    # Assert: Timestamp is deterministic and status is OK
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["generated_at"] == "2023-11-14T22:13:20Z"
    assert summary["status"] == "OK"

    event_payload = json.loads(event_payload_path.read_text(encoding="utf-8"))
    assert event_payload["generated_at"] == "2023-11-14T22:13:20Z"
    assert event_payload["status"] == "OK"
    # Strict schema check: NO counts in payload
    assert "counts" not in event_payload
    # Strict schema check: Only allowed fields
    assert set(event_payload.keys()) == {"url", "generated_at", "repo", "status"}

    # Assert: Envelope structure
    event = json.loads(event_path.read_text(encoding="utf-8"))
    assert event["type"] == "integrity.summary.published.v1"
    assert event["source"] == "heimgewebe/semantAH"
    assert event["payload"] == event_payload


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

    # Assert: Event payload status reflects WARN
    event_payload_path = tmp_path / "reports" / "integrity" / "event_payload.json"
    event_payload = json.loads(event_payload_path.read_text(encoding="utf-8"))
    assert event_payload["status"] == "WARN"


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
    assert "event.json" not in summary["details"]["artifacts"]

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


def test_dynamic_url_generation(tmp_path, monkeypatch):
    """Test that report URL respects GITHUB_REPOSITORY env var."""
    # Setup
    contracts_dir = tmp_path / "contracts"
    artifacts_dir = tmp_path / "artifacts"
    contracts_dir.mkdir()
    artifacts_dir.mkdir()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_REPOSITORY", "test-org/test-repo")

    # Run
    script = _import_script()
    script.main()

    # Assert
    event_payload_path = tmp_path / "reports" / "integrity" / "event_payload.json"
    payload = json.loads(event_payload_path.read_text(encoding="utf-8"))

    assert (
        payload["url"]
        == "https://github.com/test-org/test-repo/releases/download/integrity/summary.json"
    )
    assert payload["repo"] == "test-org/test-repo"


def test_invalid_repo_name_fail(tmp_path, monkeypatch):
    """Test status is FAIL when GITHUB_REPOSITORY format is invalid."""
    # Setup
    contracts_dir = tmp_path / "contracts"
    artifacts_dir = tmp_path / "artifacts"
    contracts_dir.mkdir()
    artifacts_dir.mkdir()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_REPOSITORY", "invalid-repo-name")

    # Run
    script = _import_script()
    script.main()

    # Assert
    summary_path = tmp_path / "reports" / "integrity" / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert summary["status"] == "FAIL"
    assert "repo_error" in summary["details"]
    assert "Invalid repository name format" in summary["details"]["repo_error"]

    # Test edge case: valid slash but empty parts (e.g. "owner/")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/")
    script.main()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "FAIL"
    assert "repo_error" in summary["details"]


def test_claims_filtering(tmp_path, monkeypatch):
    """Test that INTEGRITY_CLAIMS filters out unrelated schemas."""
    # Setup
    contracts_dir = tmp_path / "contracts"
    artifacts_dir = tmp_path / "artifacts"
    contracts_dir.mkdir()
    artifacts_dir.mkdir()

    (contracts_dir / "relevant.schema.json").write_text(json.dumps({}))
    (contracts_dir / "ignored.schema.json").write_text(json.dumps({}))

    # Only artifacts for 'relevant' exist
    (artifacts_dir / "relevant.json").write_text(json.dumps({}))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("INTEGRITY_CLAIMS", "relevant")

    # Run
    script = _import_script()
    script.main()

    # Assert
    summary_path = tmp_path / "reports" / "integrity" / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    # Should be OK because 'ignored' is filtered out
    assert summary["status"] == "OK"
    assert summary["counts"]["claims"] == 1  # Only relevant
    assert summary["counts"]["loop_gaps"] == 0
    assert "relevant.schema.json" in summary["details"]["claims"]
    assert "ignored.schema.json" not in summary["details"]["claims"]
    assert summary["details"]["claims_filter"] == ["relevant"]
    assert summary["details"]["claims_filter_active"] is True


def test_claims_filtering_active_flag(tmp_path, monkeypatch):
    """Test that claims_filter_active is set only when INTEGRITY_CLAIMS is present."""
    # Setup
    contracts_dir = tmp_path / "contracts"
    artifacts_dir = tmp_path / "artifacts"
    contracts_dir.mkdir()
    artifacts_dir.mkdir()

    # Case 1: No INTEGRITY_CLAIMS
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("INTEGRITY_CLAIMS", raising=False)

    script = _import_script()
    script.main()

    summary_path = tmp_path / "reports" / "integrity" / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert "claims_filter_active" not in summary["details"] or summary["details"]["claims_filter_active"] is False

    # Case 2: INTEGRITY_CLAIMS set
    monkeypatch.setenv("INTEGRITY_CLAIMS", "foo")

    script.main()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["details"]["claims_filter_active"] is True


def test_generated_at_format(tmp_path, monkeypatch):
    """Test that generated_at is ISO-8601 with Z suffix."""
    # Setup
    contracts_dir = tmp_path / "contracts"
    artifacts_dir = tmp_path / "artifacts"
    contracts_dir.mkdir()
    artifacts_dir.mkdir()

    monkeypatch.chdir(tmp_path)

    # Run
    script = _import_script()
    script.main()

    # Assert
    summary_path = tmp_path / "reports" / "integrity" / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    generated_at = summary["generated_at"]
    assert generated_at.endswith("Z")
    assert "T" in generated_at
