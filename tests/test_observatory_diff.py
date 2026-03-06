from __future__ import annotations

import copy
from pathlib import Path

import pytest

from scripts.observatory_diff import generate_diff, parse_args


@pytest.fixture
def default_snapshot():
    return {"topics": [{"topic": "Alpha"}], "generated_at": "2024-01-02T00:00:00Z"}


def test_parse_args_defaults():
    args = parse_args([])
    assert args.snapshot == Path("artifacts/knowledge.observatory.json")
    assert args.baseline == Path("tests/fixtures/knowledge.observatory.baseline.json")
    assert args.output == Path("artifacts/knowledge.observatory.diff.json")
    assert args.schema == Path("contracts/knowledge.observatory.schema.json")
    assert args.strict is False


def test_parse_args_custom():
    args = parse_args(
        [
            "--snapshot",
            "snap.json",
            "--baseline",
            "base.json",
            "--output",
            "out.json",
            "--schema",
            "sch.json",
            "--strict",
        ]
    )
    assert args.snapshot == Path("snap.json")
    assert args.baseline == Path("base.json")
    assert args.output == Path("out.json")
    assert args.schema == Path("sch.json")
    assert args.strict is True


@pytest.mark.parametrize(
    "snapshot_mods, baseline_val, baseline_status, expected_subset",
    [
        (
            {"topics": []},
            None,
            {"missing": True, "reason": "Baseline not found"},
            {
                "baseline_missing": True,
                "baseline_error": False,
                "reason": "Baseline not found",
                "baseline_generated_at": None,
                "current_generated_at": "2024-01-02T00:00:00Z",
            },
        ),
        (
            {"topics": []},
            None,
            {"error": True, "reason": "Invalid JSON"},
            {
                "baseline_missing": False,
                "baseline_error": True,
                "reason": "Invalid JSON",
            },
        ),
        (
            {"topics": [{"topic": "Alpha"}, {"topic": "Beta"}]},
            {
                "topics": [{"topic": "Beta"}, {"topic": "Gamma"}],
                "generated_at": "2024-01-01T00:00:00Z",
            },
            {"missing": False, "error": False},
            {
                "baseline_missing": False,
                "baseline_error": False,
                "current_generated_at": "2024-01-02T00:00:00Z",
                "baseline_generated_at": "2024-01-01T00:00:00Z",
                "topic_count_diff": 0,
                "topics_changed": True,
                "new_topics": ["Alpha"],
                "removed_topics": ["Gamma"],
                "reason": None,
            },
        ),
        (
            {},  # No changes to default_snapshot
            {
                "topics": [{"topic": "Alpha"}],
                "generated_at": "2024-01-01T00:00:00Z",
            },
            {"missing": False, "error": False},
            {
                "topics_changed": False,
                "new_topics": [],
                "removed_topics": [],
                "topic_count_diff": 0,
            },
        ),
    ],
)
def test_generate_diff(
    default_snapshot, snapshot_mods, baseline_val, baseline_status, expected_subset
):
    snapshot = copy.deepcopy(default_snapshot)
    snapshot.update(snapshot_mods)

    baseline = copy.deepcopy(baseline_val) if baseline_val else None
    diff = generate_diff(snapshot, baseline, baseline_status)

    for k, v in expected_subset.items():
        assert diff[k] == v
