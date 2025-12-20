import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts/ to path so we can import the script
SCRIPTS_DIR = Path(__file__).parents[1] / "scripts"
sys.path.append(str(SCRIPTS_DIR))

import chronik_tail_reader


@pytest.fixture
def mock_events():
    return [
        {"event": "login", "status": "success", "ts": "2023-12-25T10:00:00Z", "id": 1},
        {"event": "login", "status": "failure", "ts": "2023-12-25T10:01:00Z", "id": 2},
        {"event": "logout", "status": "success", "ts": "2023-12-25T12:00:00Z", "id": 3},
        {"event": "login", "status": "success", "ts": "2023-12-25T09:00:00Z", "id": 0},
    ]


def test_process_data_logic(mock_events):
    """Test that process_data correctly aggregates events and sorts them."""
    result = chronik_tail_reader.process_data(mock_events, "aussen")

    assert result["source"] == "chronik:aussen.tail"
    assert "generated_at" in result

    # Counts
    assert result["counts_by_event"]["login"] == 3
    assert result["counts_by_event"]["logout"] == 1

    assert result["counts_by_status"]["success"] == 3
    assert result["counts_by_status"]["failure"] == 1

    # Last seen TS (max)
    # 12:00 is the latest
    assert result["last_seen_ts"] == "2023-12-25T12:00:00+00:00"

    # Sample (first 3 sorted descending)
    # Order should be: id 3 (12:00), id 2 (10:01), id 1 (10:00)
    assert len(result["sample"]) == 3
    assert result["sample"][0]["id"] == 3
    assert result["sample"][1]["id"] == 2
    assert result["sample"][2]["id"] == 1

    # Total count
    assert result["total_count"] == 4


def test_process_data_dynamic_source():
    """Test that source reflects the domain."""
    result = chronik_tail_reader.process_data([], "test_domain")
    assert result["source"] == "chronik:test_domain.tail"


def test_process_data_invalid_timestamps():
    """Test processing events with missing or invalid timestamps."""
    events = [
        {"event": "a", "ts": "invalid"},
        {"event": "b", "ts": None},
        {"event": "c", "ts": "2023-01-01T00:00:00Z"}
    ]
    result = chronik_tail_reader.process_data(events, "aussen")

    assert result["total_count"] == 3
    # Only one valid ts
    assert result["last_seen_ts"] == "2023-01-01T00:00:00+00:00"
    # Sample should prioritize the one with valid timestamp?
    # Logic: sorts valid ones, puts them first.
    assert result["sample"][0]["event"] == "c"


def test_process_data_empty():
    """Test processing empty list."""
    result = chronik_tail_reader.process_data([], "aussen")

    assert result["counts_by_event"] == {}
    assert result["counts_by_status"] == {}
    assert result["sample"] == []
    assert result["total_count"] == 0
    assert "last_seen_ts" not in result


@patch("urllib.request.urlopen")
def test_fetch_data_success(mock_urlopen):
    """Test fetch_data parses JSON response correctly and encodes URL."""
    # Mock response context manager
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps([
        {"event": "test"}
    ]).encode("utf-8")

    mock_urlopen.return_value.__enter__.return_value = mock_response

    data = chronik_tail_reader.fetch_data("http://test", "bad domain", 10)
    assert len(data) == 1
    assert data[0]["event"] == "test"

    # Check URL construction with encoding
    args, _ = mock_urlopen.call_args
    req = args[0]
    assert req.full_url == "http://test/v1/tail?domain=bad%20domain&limit=10"


@patch("urllib.request.urlopen")
def test_fetch_data_auth_header(mock_urlopen):
    """Test that X-Auth header is added from env var."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b"[]"
    mock_urlopen.return_value.__enter__.return_value = mock_response

    with patch.dict(os.environ, {"CHRONIK_AUTH": "secret-token"}):
        chronik_tail_reader.fetch_data("http://test", "aussen", 10)

        args, _ = mock_urlopen.call_args
        req = args[0]
        assert req.get_header("X-auth") == "secret-token"


@patch("urllib.request.urlopen")
def test_fetch_data_auth_header_fallback(mock_urlopen):
    """Test fallback to X_AUTH."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b"[]"
    mock_urlopen.return_value.__enter__.return_value = mock_response

    with patch.dict(os.environ, {"X_AUTH": "fallback-token"}, clear=True):
        # ensure CHRONIK_AUTH is not set
        if "CHRONIK_AUTH" in os.environ:
            del os.environ["CHRONIK_AUTH"]

        chronik_tail_reader.fetch_data("http://test", "aussen", 10)

        args, _ = mock_urlopen.call_args
        req = args[0]
        assert req.get_header("X-auth") == "fallback-token"


def test_main_integration(tmp_path, mock_events):
    """Integration test of main() using mocks for network and tmp_path for output."""
    output_file = tmp_path / "out" / "insights.daily.json"

    with patch("chronik_tail_reader.fetch_data", return_value=mock_events) as mock_fetch:
        # Simulate CLI args
        test_args = [
            "--url", "http://mock-chronik",
            "--output", str(output_file),
            "--domain", "test_domain"
        ]

        with patch.object(sys, "argv", ["script"] + test_args):
            ret = chronik_tail_reader.main()

            assert ret == 0
            assert output_file.exists()

            content = json.loads(output_file.read_text(encoding="utf-8"))
            assert content["source"] == "chronik:test_domain.tail"
            assert content["total_count"] == 4

            # Check sorting happened
            assert content["last_seen_ts"].startswith("2023-12-25T12:00:00")

            mock_fetch.assert_called_once_with("http://mock-chronik", "test_domain", 200)
