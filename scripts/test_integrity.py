import unittest
import tempfile
import shutil
import os
import json
from pathlib import Path
import sys

# Ensure we can import the script
scripts_path = Path(__file__).parent
if str(scripts_path) not in sys.path:
    sys.path.insert(0, str(scripts_path))

try:
    import generate_integrity_summary
except ImportError:
    # If running from root, scripts might not be importable directly
    sys.path.insert(0, str(Path.cwd() / "scripts"))
    import generate_integrity_summary

class TestIntegrity(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.test_dir)

        self.contracts_dir = Path(self.test_dir) / "contracts"
        self.artifacts_dir = Path(self.test_dir) / "artifacts"
        self.contracts_dir.mkdir()
        self.artifacts_dir.mkdir()

        # Output dir
        self.reports_dir = Path(self.test_dir) / "reports" / "integrity"

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.test_dir)

    def test_empty_contracts_status_ok(self):
        """Test status is OK when contracts dir exists but has no schemas."""
        generate_integrity_summary.main()

        with open(self.reports_dir / "summary.json") as f:
            summary = json.load(f)

        self.assertEqual(summary["status"], "OK")
        self.assertEqual(summary["counts"]["claims"], 0)
        self.assertEqual(summary["counts"]["loop_gaps"], 0)

    def test_dynamic_url_generation(self):
        """Test that report URL respects GITHUB_REPOSITORY env var."""
        os.environ["GITHUB_REPOSITORY"] = "test-org/test-repo"
        try:
            generate_integrity_summary.main()
            with open(self.reports_dir / "event_payload.json") as f:
                payload = json.load(f)
            self.assertEqual(
                payload["url"],
                "https://github.com/test-org/test-repo/releases/download/integrity/summary.json"
            )
            self.assertEqual(payload["repo"], "test-org/test-repo")
        finally:
            if "GITHUB_REPOSITORY" in os.environ:
                del os.environ["GITHUB_REPOSITORY"]

    def test_invalid_repo_name_fail(self):
        """Test status is FAIL when GITHUB_REPOSITORY format is invalid."""
        os.environ["GITHUB_REPOSITORY"] = "invalid-repo-name"
        try:
            generate_integrity_summary.main()
            with open(self.reports_dir / "summary.json") as f:
                summary = json.load(f)

            self.assertEqual(summary["status"], "FAIL")
            self.assertIn("repo_error", summary["details"])
            self.assertIn("Invalid repository name format", summary["details"]["repo_error"])
        finally:
             if "GITHUB_REPOSITORY" in os.environ:
                del os.environ["GITHUB_REPOSITORY"]

    def test_generated_at_format(self):
        """Test that generated_at is ISO-8601 with Z suffix."""
        generate_integrity_summary.main()
        with open(self.reports_dir / "summary.json") as f:
            summary = json.load(f)

        generated_at = summary["generated_at"]
        self.assertTrue(generated_at.endswith("Z"))
        # Validate simple ISO format (approximate)
        # e.g. 2023-10-27T10:00:00.123456Z
        self.assertIn("T", generated_at)

    def test_event_payload_strictness(self):
        """Test that event payload contains only allowed keys."""
        generate_integrity_summary.main()
        with open(self.reports_dir / "event_payload.json") as f:
            payload = json.load(f)

        allowed_keys = {"url", "generated_at", "repo", "status"}
        self.assertEqual(set(payload.keys()), allowed_keys)

    def test_missing_artifact_warn(self):
        """Test status is WARN when a contract exists but artifact is missing."""
        (self.contracts_dir / "test.schema.json").touch()

        generate_integrity_summary.main()

        with open(self.reports_dir / "summary.json") as f:
            summary = json.load(f)

        self.assertEqual(summary["status"], "WARN")
        self.assertEqual(summary["counts"]["claims"], 1)
        self.assertEqual(summary["counts"]["loop_gaps"], 1)
        self.assertIn("test", summary["details"]["loop_gaps"])

    def test_claims_filtering(self):
        """Test that INTEGRITY_CLAIMS filters out unrelated schemas."""
        (self.contracts_dir / "relevant.schema.json").touch()
        (self.contracts_dir / "ignored.schema.json").touch()

        # Only artifacts for 'relevant' exist
        (self.artifacts_dir / "relevant.json").touch()

        os.environ["INTEGRITY_CLAIMS"] = "relevant"
        try:
            generate_integrity_summary.main()
            with open(self.reports_dir / "summary.json") as f:
                summary = json.load(f)

            # Should be OK because 'ignored' is filtered out
            self.assertEqual(summary["status"], "OK")
            self.assertEqual(summary["counts"]["claims"], 1) # Only relevant
            self.assertEqual(summary["counts"]["loop_gaps"], 0)
            self.assertIn("relevant.schema.json", summary["details"]["claims"])
            self.assertNotIn("ignored.schema.json", summary["details"]["claims"])
            self.assertEqual(summary["details"]["claims_filter"], ["relevant"])
        finally:
            del os.environ["INTEGRITY_CLAIMS"]

    def test_matching_artifact_ok(self):
        """Test status is OK when contract matches artifact."""
        (self.contracts_dir / "test.schema.json").touch()
        (self.artifacts_dir / "test.json").touch()

        generate_integrity_summary.main()

        with open(self.reports_dir / "summary.json") as f:
            summary = json.load(f)

        self.assertEqual(summary["status"], "OK")
        self.assertEqual(summary["counts"]["claims"], 1)
        self.assertEqual(summary["counts"]["loop_gaps"], 0)

if __name__ == "__main__":
    unittest.main()
