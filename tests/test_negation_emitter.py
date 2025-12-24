import json
import os
import sys
import unittest
from pathlib import Path

# Add scripts/ to path
sys.path.append(str(Path(__file__).parent.parent / "scripts"))

from emit_negations import emit_negations
from observatory_lib import validate_payload

SCHEMA_PATH = Path("contracts") / "insights.schema.json"

class TestEmitNegations(unittest.TestCase):
    def test_emit_negations_conflict(self):
        insights = [
            {
                "type": "review.insight",
                "id": "rev-1",
                "repo": "repo1",
                "file": "file1",
                "source": "hausKI",
                "score": 85,
                "verdict": "It is bad",
                "bucket": "fail",
                "ingested_at": "2023-01-01T00:00:00Z"
            },
            {
                "type": "review.insight",
                "id": "rev-2",
                "repo": "repo1",
                "file": "file1",
                "source": "hausKI",
                "score": 90,
                "verdict": "It is good",
                "bucket": "info",
                "ingested_at": "2023-01-01T00:00:00Z"
            }
        ]

        result = emit_negations(insights)
        self.assertEqual(len(result), 1)
        negation = result[0]
        self.assertEqual(negation["type"], "insight.negation")
        self.assertEqual(negation["relation"]["thesis"], "rev-1")
        self.assertEqual(negation["relation"]["antithesis"], "rev-2")

        # Validate against schema
        # Note: validate_payload usually expects a file path, but here we have a dict.
        # observatory_lib.validate_payload takes a dict and a schema path.
        if SCHEMA_PATH.exists():
            validate_payload(negation, SCHEMA_PATH, label="Generated Negation")

    def test_emit_negations_no_conflict_low_score(self):
        insights = [
            {
                "type": "review.insight",
                "id": "rev-1",
                "repo": "repo1",
                "file": "file1",
                "source": "hausKI",
                "score": 50, # Low score
                "bucket": "fail",
                "ingested_at": "2023-01-01T00:00:00Z"
            },
            {
                "type": "review.insight",
                "id": "rev-2",
                "repo": "repo1",
                "file": "file1",
                "source": "hausKI",
                "score": 90,
                "bucket": "info",
                "ingested_at": "2023-01-01T00:00:00Z"
            }
        ]
        result = emit_negations(insights)
        self.assertEqual(len(result), 0)

    def test_emit_negations_dedup(self):
        # Running twice on same input should produce same ID
        insights = [
            {
                "type": "review.insight",
                "id": "rev-1",
                "repo": "repo1",
                "file": "file1",
                "source": "hausKI",
                "score": 85,
                "bucket": "fail",
                "ingested_at": "2023-01-01T00:00:00Z"
            },
            {
                "type": "review.insight",
                "id": "rev-2",
                "repo": "repo1",
                "file": "file1",
                "source": "hausKI",
                "score": 90,
                "bucket": "info",
                "ingested_at": "2023-01-01T00:00:00Z"
            }
        ]
        result1 = emit_negations(insights)
        result2 = emit_negations(insights)
        self.assertEqual(result1[0]["id"], result2[0]["id"])

if __name__ == "__main__":
    unittest.main()
