import unittest
from unittest.mock import MagicMock, patch, mock_open
import sys
import os
import json
from datetime import datetime
from io import BytesIO

# Import the module to test.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts")))

import chronik_tail_reader


class TestChronikTailReader(unittest.TestCase):
    def test_parse_ts(self):
        """Test robust timestamp parsing."""
        # Valid ISO with Z
        ts = "2023-10-27T10:00:00Z"
        dt = chronik_tail_reader.parse_ts(ts)
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2023)

        # Valid ISO with offset
        ts = "2023-10-27T10:00:00+00:00"
        dt = chronik_tail_reader.parse_ts(ts)
        self.assertIsNotNone(dt)

        # Invalid
        ts = "invalid-date"
        dt = chronik_tail_reader.parse_ts(ts)
        self.assertIsNone(dt)

        # None
        dt = chronik_tail_reader.parse_ts(None)
        self.assertIsNone(dt)

    @patch.dict(os.environ, {}, clear=True)
    def test_auth_missing(self):
        """Test exit code 2 when auth is missing."""
        with self.assertRaises(SystemExit) as cm:
            chronik_tail_reader.main()
        self.assertEqual(cm.exception.code, 2)

    @patch.dict(os.environ, {"CHRONIK_AUTH": "secret-token"}, clear=True)
    @patch("urllib.request.urlopen")
    @patch("sys.argv", ["script_name", "--output", "test_out.json"])
    @patch("builtins.open", new_callable=mock_open)
    def test_process_data_counts_and_honest_metrics(self, mock_file, mock_urlopen):
        """Test counting logic, sorting, and honest metrics."""
        # Mock response data
        mock_data = [
            {"event": "login", "status": "success", "ts": "2023-01-01T10:00:00Z"},
            {"event": "login", "status": "failure", "ts": "2023-01-02T10:00:00Z"},
            {
                "event": "logout",
                "status": "success",
                "timestamp": "2023-01-03T10:00:00Z",
            },  # Use timestamp fallback
            {"other_field": "val"},  # Missing event, status, and ts
        ]

        # Mock response object
        mock_resp = MagicMock()
        mock_resp.read = BytesIO(json.dumps(mock_data).encode("utf-8")).read
        mock_resp.getheader.return_value = "0"
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        mock_urlopen.return_value = mock_resp

        # Run
        chronik_tail_reader.main()

        # Verify output
        handle = mock_file()
        written_content = "".join(call[0][0] for call in handle.write.call_args_list)
        output_json = json.loads(written_content)

        # Assertions
        # Honest counts:
        self.assertEqual(output_json["counts_by_event"]["login"], 2)
        self.assertEqual(output_json["counts_by_event"]["logout"], 1)
        self.assertNotIn(
            "unknown", output_json["counts_by_event"]
        )  # Should not have unknown

        self.assertEqual(output_json["counts_by_status"]["success"], 2)
        self.assertEqual(output_json["counts_by_status"]["failure"], 1)
        self.assertNotIn("unknown", output_json["counts_by_status"])

        self.assertEqual(output_json["total_count"], 4)

        # Metrics
        self.assertEqual(output_json["meta"]["missing_event_field"], 1)
        self.assertEqual(output_json["meta"]["missing_status_field"], 1)
        self.assertEqual(output_json["meta"]["missing_ts_field"], 1)
        self.assertEqual(output_json["meta"]["invalid_ts_field"], 0)

        # Sort verification: newest first (2023-01-03 from timestamp fallback)
        self.assertEqual(len(output_json["sample"]), 3)
        self.assertEqual(
            output_json["sample"][0].get("timestamp"), "2023-01-03T10:00:00Z"
        )
        self.assertEqual(output_json["sample"][1]["ts"], "2023-01-02T10:00:00Z")
        self.assertEqual(output_json["sample"][2]["ts"], "2023-01-01T10:00:00Z")

    @patch.dict(os.environ, {"CHRONIK_AUTH": "secret-token"}, clear=True)
    @patch("urllib.request.urlopen")
    @patch("builtins.open", new_callable=mock_open)
    @patch(
        "sys.argv",
        [
            "script_name",
            "--output",
            "test_out.json",
            "--domain",
            "my domain",
            "--limit",
            "10",
        ],
    )
    def test_full_flow_int_limit(self, mock_file, mock_urlopen):
        """Test full flow including integer limit validation."""

        # Data
        response_data = [{"event": "A", "status": "ok", "ts": "2023-01-01T00:00:00Z"}]
        json_bytes = json.dumps(response_data).encode("utf-8")

        # Mock response
        mock_resp = MagicMock()
        mock_resp.read = BytesIO(json_bytes).read
        mock_resp.getheader.side_effect = (
            lambda k: "100" if k == "X-Chronik-Lines-Returned" else "0"
        )
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        mock_urlopen.return_value = mock_resp

        # Run
        chronik_tail_reader.main()

        # Verify Headers and URL
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        self.assertEqual(req.get_header("X-auth"), "secret-token")
        self.assertIn("domain=my%20domain", req.full_url)
        self.assertIn("limit=10", req.full_url)  # Check limit is in URL as 10

        # Verify Output
        handle = mock_file()
        written_content = "".join(call[0][0] for call in handle.write.call_args_list)
        output_json = json.loads(written_content)

        self.assertEqual(output_json["source"], "chronik:my domain.tail")

        # generated_at should be recent
        generated_at = output_json["generated_at"]
        dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        self.assertIsNotNone(dt.tzinfo)
        self.assertEqual(dt.utcoffset().total_seconds(), 0)  # UTC check


if __name__ == "__main__":
    unittest.main()
