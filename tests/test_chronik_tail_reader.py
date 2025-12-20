import json
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
    """Test that process_data correctly aggregates events."""
    result = chronik_tail_reader.process_data(mock_events)

    assert result["source"] == "chronik:aussen.tail"
    assert "generated_at" in result

    # Counts
    assert result["counts_by_event"]["login"] == 3
    assert result["counts_by_event"]["logout"] == 1

    assert result["counts_by_status"]["success"] == 3
    assert result["counts_by_status"]["failure"] == 1

    # Last seen TS (max)
    assert result["last_seen_ts"] == "2023-12-25T12:00:00Z"

    # Sample (first 3)
    assert len(result["sample"]) == 3
    assert result["sample"][0]["id"] == 1
    assert result["sample"][2]["id"] == 3

    # Total count
    assert result["total_count"] == 4


def test_process_data_empty():
    """Test processing empty list."""
    result = chronik_tail_reader.process_data([])

    assert result["counts_by_event"] == {}
    assert result["counts_by_status"] == {}
    assert result["sample"] == []
    assert result["total_count"] == 0
    assert "last_seen_ts" not in result


@patch("urllib.request.urlopen")
def test_fetch_data_success(mock_urlopen):
    """Test fetch_data parses JSON response correctly."""
    # Mock response context manager
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps([
        {"event": "test"}
    ]).encode("utf-8")

    mock_urlopen.return_value.__enter__.return_value = mock_response

    data = chronik_tail_reader.fetch_data("http://test", "aussen", 10)
    assert len(data) == 1
    assert data[0]["event"] == "test"

    # Check URL construction
    args, _ = mock_urlopen.call_args
    req = args[0]
    assert req.full_url == "http://test/v1/tail?domain=aussen&limit=10"


@patch("urllib.request.urlopen")
def test_fetch_data_items_wrapper(mock_urlopen):
    """Test fetch_data handles {'items': [...]} wrapper."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps({
        "items": [{"event": "wrapped"}]
    }).encode("utf-8")

    mock_urlopen.return_value.__enter__.return_value = mock_response

    data = chronik_tail_reader.fetch_data("http://test", "aussen", 10)
    assert len(data) == 1
    assert data[0]["event"] == "wrapped"


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

        # We need to patch sys.argv or use parse_args manually,
        # but main() calls parse_args(). Let's patch sys.argv.
        with patch.object(sys, "argv", ["script"] + test_args):
            ret = chronik_tail_reader.main()

            assert ret == 0
            assert output_file.exists()

            content = json.loads(output_file.read_text(encoding="utf-8"))
            assert content["source"] == "chronik:aussen.tail"
            assert content["total_count"] == 4

            mock_fetch.assert_called_once_with("http://mock-chronik", "test_domain", 200)
