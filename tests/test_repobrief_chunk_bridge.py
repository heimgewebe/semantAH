import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import repobrief_chunk_bridge as bridge


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _row(text="hello semantic bridge", chunk_id="c1", path="README.md"):
    return {
        "repo_id": "demo",
        "chunk_id": chunk_id,
        "path": path,
        "content": text,
        "content_range_ref": {
            "artifact_role": "canonical_md",
            "file_path": path,
            "start_byte": 10,
            "end_byte": 31,
            "start_line": 2,
            "end_line": 2,
            "content_sha256": _sha(text),
        },
    }


def test_build_records_preserves_stable_repobrief_identity():
    records = bridge.build_records([_row()], default_repo_id="fallback", dim=6)

    assert len(records) == 1
    rec = records[0]
    assert rec["id"].startswith("repobrief:demo:c1:")
    assert rec["repo_id"] == "demo"
    assert rec["repobrief_chunk_id"] == "c1"
    assert rec["file_path"] == "README.md"
    assert rec["start_byte"] == 10
    assert rec["end_byte"] == 31
    assert rec["content_sha256"] == _sha("hello semantic bridge")
    assert rec["bridge_input_basis"] == "repobrief_chunk_index_stable_ids_ranges_hashes"
    assert len(rec["embedding"]) == 6


def test_build_records_rejects_unstable_rows_without_range():
    bad = {"repo_id": "demo", "chunk_id": "c1", "content": "hello"}

    with pytest.raises(ValueError, match="lacks stable byte range"):
        bridge.build_records([bad], default_repo_id="fallback")


def test_report_keeps_semantic_layer_external_and_non_promoted(tmp_path: Path):
    chunk_index = tmp_path / "demo.chunk_index.jsonl"
    chunk_index.write_text(json.dumps(_row()) + "\n", encoding="utf-8")
    records = bridge.build_records(
        bridge.read_jsonl(chunk_index), default_repo_id="fallback"
    )

    report = bridge.build_report(chunk_index=chunk_index, records=records)

    assert report["external_layer"]["owner"] == "semantAH"
    assert report["external_layer"]["repo_brief_core_ranking_changed"] is False
    assert report["external_layer"]["default_use"] is False
    assert report["evaluation"]["status"] == "not_run"
    assert report["baseline_comparison"] == {
        "status": "not_run",
        "reason": "no_goldset_provided",
        "promotion_allowed": False,
    }
    assert "default_ranking_improvement" in report["does_not_establish"]


def test_goldset_eval_reports_query_ranked_recall_mrr_and_misses():
    records = bridge.build_records(
        [
            _row("unrelated setup", chunk_id="c1"),
            _row("semantic bridge baseline evidence", chunk_id="c2"),
        ],
        default_repo_id="demo",
    )
    result = bridge.evaluate_recall(
        records,
        [
            {"query": "semantic bridge evidence", "expected_chunk_id": "c2"},
            {"query": "missing target", "expected_chunk_id": "missing"},
        ],
    )

    assert result["status"] == "warn"
    assert result["gold_count"] == 2
    assert result["hit_count"] == 1
    assert result["recall"] == 0.5
    assert result["mrr"] == 0.5
    assert result["cases"][0]["rank"] == 1
    assert result["miss_taxonomy"] == [
        {"expected_chunk_id": "missing", "reason": "missing_from_bridge_records"}
    ]


def test_baseline_comparison_is_required_for_promotion_claims(tmp_path: Path):
    chunk_index = tmp_path / "demo.chunk_index.jsonl"
    chunk_index.write_text(json.dumps(_row()) + "\n", encoding="utf-8")
    records = bridge.build_records(
        bridge.read_jsonl(chunk_index), default_repo_id="fallback"
    )
    goldset = [{"query": "semantic bridge", "expected_chunk_id": "c1"}]
    baseline = {
        "metrics": {"recall@10": 50.0, "mrr": 0.25},
        "miss_taxonomy": {"aggregate": {"total_misses": 1}},
    }

    report = bridge.build_report(
        chunk_index=chunk_index,
        records=records,
        goldset=goldset,
        baseline_report=baseline,
    )

    comparison = report["baseline_comparison"]
    assert comparison["status"] == "pass"
    assert comparison["promotion_allowed"] is False
    assert comparison["baseline_metrics"] == {
        "recall": 0.5,
        "mrr": 0.25,
        "miss_count": 1,
    }
    assert comparison["bridge_metrics"] == {
        "recall": 1.0,
        "mrr": 1.0,
        "miss_count": 0,
    }
    assert comparison["deltas"] == {"recall": 0.5, "mrr": 0.75, "miss_count": -1}


def test_baseline_comparison_warns_on_recall_mrr_or_miss_regression():
    bridge_eval = {"recall": 0.4, "mrr": 0.2, "miss_taxonomy": [{"x": 1}]}
    baseline = {
        "metrics": {"recall@10": 0.5, "mrr": 0.25},
        "miss_taxonomy": {"aggregate": {"total_misses": 0}},
    }

    comparison = bridge.compare_to_baseline(bridge_eval, baseline)

    assert comparison["status"] == "warn"
    assert comparison["blockers"] == [
        "recall_regression",
        "mrr_regression",
        "miss_taxonomy_regression",
    ]
    assert comparison["promotion_allowed"] is False


def test_cli_writes_external_jsonl_report_and_baseline_comparison(tmp_path: Path):
    chunk_index = tmp_path / "demo.chunk_index.jsonl"
    out_jsonl = tmp_path / "semantah.records.jsonl"
    report = tmp_path / "bridge.report.json"
    goldset = tmp_path / "goldset.jsonl"
    baseline = tmp_path / "baseline.json"
    chunk_index.write_text(json.dumps(_row()) + "\n", encoding="utf-8")
    goldset.write_text(
        json.dumps({"query": "semantic bridge", "expected_chunk_id": "c1"}) + "\n",
        encoding="utf-8",
    )
    baseline.write_text(
        json.dumps({"metrics": {"recall@10": 1.0, "mrr": 1.0}, "details": []}),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/repobrief_chunk_bridge.py",
            "--chunk-index",
            str(chunk_index),
            "--out-jsonl",
            str(out_jsonl),
            "--report",
            str(report),
            "--dim",
            "4",
            "--goldset",
            str(goldset),
            "--baseline-report",
            str(baseline),
        ],
        cwd=Path(__file__).parent.parent,
        text=True,
        capture_output=True,
        check=True,
    )

    written = [
        json.loads(line) for line in out_jsonl.read_text(encoding="utf-8").splitlines()
    ]
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert proc.returncode == 0
    assert len(written) == 1
    assert len(written[0]["embedding"]) == 4
    assert payload["kind"] == "semantah.repobrief_chunk_embedding_bridge"
    assert payload["record_count"] == 1
    assert payload["baseline_comparison"]["status"] == "pass"
