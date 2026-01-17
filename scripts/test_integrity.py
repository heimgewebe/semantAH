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
