from __future__ import annotations

import json
from pathlib import Path
import pytest
from scripts.observatory_diff import parse_args, generate_diff

def test_parse_args_defaults():
    args = parse_args([])
    assert args.snapshot == Path("artifacts/knowledge.observatory.json")
    assert args.baseline == Path("tests/fixtures/knowledge.observatory.baseline.json")
    assert args.output == Path("artifacts/knowledge.observatory.diff.json")
    assert args.schema == Path("contracts/knowledge.observatory.schema.json")
    assert args.strict is False

def test_parse_args_custom():
    args = parse_args([
        "--snapshot", "snap.json",
        "--baseline", "base.json",
        "--output", "out.json",
        "--schema", "sch.json",
        "--strict"
    ])
    assert args.snapshot == Path("snap.json")
    assert args.baseline == Path("base.json")
    assert args.output == Path("out.json")
    assert args.schema == Path("sch.json")
    assert args.strict is True

def test_generate_diff_missing_baseline():
    snapshot = {"topics": [], "generated_at": "2024-01-01T00:00:00Z"}
    baseline_status = {"missing": True, "reason": "Baseline not found"}
    diff = generate_diff(snapshot, None, baseline_status)

    assert diff["baseline_missing"] is True
    assert diff["baseline_error"] is False
    assert diff["reason"] == "Baseline not found"
    assert diff["current_generated_at"] == "2024-01-01T00:00:00Z"
    assert diff["baseline_generated_at"] is None

def test_generate_diff_baseline_error():
    snapshot = {"topics": [], "generated_at": "2024-01-01T00:00:00Z"}
    baseline_status = {"error": True, "reason": "Invalid JSON"}
    diff = generate_diff(snapshot, None, baseline_status)

    assert diff["baseline_missing"] is False
    assert diff["baseline_error"] is True
    assert diff["reason"] == "Invalid JSON"

def test_generate_diff_with_baseline():
    snapshot = {
        "topics": [{"topic": "Alpha"}, {"topic": "Beta"}],
        "generated_at": "2024-01-02T00:00:00Z"
    }
    baseline = {
        "topics": [{"topic": "Beta"}, {"topic": "Gamma"}],
        "generated_at": "2024-01-01T00:00:00Z"
    }
    baseline_status = {"missing": False, "error": False}

    diff = generate_diff(snapshot, baseline, baseline_status)

    assert diff["baseline_missing"] is False
    assert diff["baseline_error"] is False
    assert diff["current_generated_at"] == "2024-01-02T00:00:00Z"
    assert diff["baseline_generated_at"] == "2024-01-01T00:00:00Z"
    assert diff["topic_count_diff"] == 0
    assert diff["topics_changed"] is True
    assert diff["new_topics"] == ["Alpha"]
    assert diff["removed_topics"] == ["Gamma"]
    assert diff["reason"] is None

def test_generate_diff_no_changes():
    snapshot = {
        "topics": [{"topic": "Alpha"}],
        "generated_at": "2024-01-02T00:00:00Z"
    }
    baseline = {
        "topics": [{"topic": "Alpha"}],
        "generated_at": "2024-01-01T00:00:00Z"
    }
    baseline_status = {"missing": False, "error": False}

    diff = generate_diff(snapshot, baseline, baseline_status)

    assert diff["topics_changed"] is False
    assert diff["new_topics"] == []
    assert diff["removed_topics"] == []
    assert diff["topic_count_diff"] == 0
