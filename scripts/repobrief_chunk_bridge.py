#!/usr/bin/env python3
"""Build a bounded SemantAH embedding layer from RepoBrief chunk_index JSONL.

The bridge consumes existing RepoBrief chunk_index rows only. It does not crawl a
repository, refresh RepoBrief snapshots, or alter RepoBrief ranking. The output is
an external semantic-evidence layer that can be measured before any promotion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    import pandas as pd
except ModuleNotFoundError:  # pragma: no cover - optional in minimal envs
    pd = None  # type: ignore[assignment]

KIND = "semantah.repobrief_chunk_embedding_bridge"
VERSION = "v1"
DEFAULT_DIM = 8
DOES_NOT_ESTABLISH = [
    "answer_correctness",
    "semantic_correctness",
    "repository_understanding",
    "default_ranking_improvement",
    "repo_understood",
    "truth",
]


@dataclass(frozen=True)
class ChunkRecord:
    record_id: str
    repo_id: str
    chunk_id: str
    text: str
    file_path: str
    start_byte: int
    end_byte: int
    content_sha256: str
    range_ref: dict[str, Any]
    source_row_sha256: str
    ordinal: int


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_text_embedding(text: str, *, dim: int = DEFAULT_DIM) -> list[float]:
    """Deterministic local stand-in embedding for bridge tests and offline evaluation."""
    if dim < 1 or dim > 4096:
        raise ValueError("embedding dim must be between 1 and 4096")
    digest = hashlib.blake2b(text.encode("utf-8"), digest_size=32).digest()
    values: list[float] = []
    for i in range(dim):
        b = digest[i % len(digest)]
        values.append(round((b / 127.5) - 1.0, 6))
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [round(v / norm, 6) for v in values]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at line {line_no}: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"chunk_index row {line_no} must be a JSON object")
        rows.append(row)
    return rows


def _non_empty_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _int_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def _range_from_row(row: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("content_range_ref", "range_ref", "canonical_range"):
        candidate = row.get(key)
        if isinstance(candidate, dict):
            return candidate
    if all(k in row for k in ("path", "start_byte", "end_byte")):
        return {
            "artifact_role": row.get("artifact_role", "chunk_index_jsonl"),
            "file_path": row.get("path"),
            "start_byte": row.get("start_byte"),
            "end_byte": row.get("end_byte"),
            "start_line": row.get("start_line"),
            "end_line": row.get("end_line"),
            "content_sha256": row.get("content_sha256"),
        }
    return None


def _content_hash(row: dict[str, Any], text: str, range_ref: dict[str, Any]) -> str:
    for source in (row, range_ref):
        value = source.get("content_sha256") or source.get("range_content_sha256")
        if isinstance(value, str) and len(value) == 64:
            return value
    return sha256_bytes(text.encode("utf-8"))


def chunk_record_from_row(row: dict[str, Any], *, ordinal: int, default_repo_id: str) -> ChunkRecord:
    text = _non_empty_string(row.get("content")) or _non_empty_string(row.get("text"))
    if text is None:
        raise ValueError(f"row {ordinal} lacks non-empty content/text")
    chunk_id = _non_empty_string(row.get("chunk_id")) or _non_empty_string(row.get("id"))
    if chunk_id is None:
        raise ValueError(f"row {ordinal} lacks stable chunk_id/id")
    range_ref = _range_from_row(row)
    if range_ref is None:
        raise ValueError(f"row {ordinal} lacks stable byte range")
    file_path = _non_empty_string(range_ref.get("file_path")) or _non_empty_string(row.get("path"))
    start_byte = _int_value(range_ref.get("start_byte"))
    end_byte = _int_value(range_ref.get("end_byte"))
    if file_path is None or start_byte is None or end_byte is None or end_byte <= start_byte:
        raise ValueError(f"row {ordinal} has invalid file_path/start_byte/end_byte")
    repo_id = _non_empty_string(row.get("repo_id")) or default_repo_id
    content_sha256 = _content_hash(row, text, range_ref)
    row_sha = sha256_bytes(canonical_json(row).encode("utf-8"))
    record_id = f"repobrief:{repo_id}:{chunk_id}:{content_sha256[:16]}"
    return ChunkRecord(
        record_id=record_id,
        repo_id=repo_id,
        chunk_id=chunk_id,
        text=text,
        file_path=file_path,
        start_byte=start_byte,
        end_byte=end_byte,
        content_sha256=content_sha256,
        range_ref=dict(range_ref),
        source_row_sha256=row_sha,
        ordinal=ordinal,
    )


def build_records(
    rows: Sequence[dict[str, Any]],
    *,
    default_repo_id: str,
    dim: int = DEFAULT_DIM,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ordinal, row in enumerate(rows):
        chunk = chunk_record_from_row(row, ordinal=ordinal, default_repo_id=default_repo_id)
        if chunk.record_id in seen:
            raise ValueError(f"duplicate stable record id: {chunk.record_id}")
        seen.add(chunk.record_id)
        records.append(
            {
                "id": chunk.record_id,
                "doc_id": f"{chunk.repo_id}:{chunk.file_path}",
                "namespace": "repobrief-chunks",
                "text": chunk.text,
                "embedding": stable_text_embedding(chunk.text, dim=dim),
                "repo_id": chunk.repo_id,
                "repobrief_chunk_id": chunk.chunk_id,
                "content_sha256": chunk.content_sha256,
                "source_row_sha256": chunk.source_row_sha256,
                "file_path": chunk.file_path,
                "start_byte": chunk.start_byte,
                "end_byte": chunk.end_byte,
                "range_ref": chunk.range_ref,
                "bridge_input_basis": "repobrief_chunk_index_stable_ids_ranges_hashes",
            }
        )
    return records


def evaluate_recall(records: Sequence[dict[str, Any]], goldset: Sequence[dict[str, Any]]) -> dict[str, Any]:
    by_chunk = {str(r["repobrief_chunk_id"]): idx + 1 for idx, r in enumerate(records)}
    total = len(goldset)
    hits = 0
    reciprocal_sum = 0.0
    misses: list[dict[str, Any]] = []
    for item in goldset:
        expected = item.get("expected_chunk_id")
        rank = by_chunk.get(str(expected)) if expected is not None else None
        if rank is None:
            misses.append({"expected_chunk_id": expected, "reason": "missing_from_bridge_records"})
            continue
        hits += 1
        reciprocal_sum += 1.0 / rank
    return {
        "status": "pass" if total == hits else "warn",
        "gold_count": total,
        "hit_count": hits,
        "recall": 1.0 if total == 0 else hits / total,
        "mrr": 0.0 if total == 0 else reciprocal_sum / total,
        "miss_taxonomy": misses,
    }


def build_report(
    *,
    chunk_index: Path,
    records: Sequence[dict[str, Any]],
    goldset: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    chunk_bytes = chunk_index.read_bytes()
    report = {
        "kind": KIND,
        "version": VERSION,
        "status": "ok",
        "chunk_index": str(chunk_index),
        "chunk_index_sha256": sha256_bytes(chunk_bytes),
        "record_count": len(records),
        "input_contract": "stable RepoBrief chunk ids, byte ranges, and content hashes",
        "external_layer": {
            "owner": "semantAH",
            "repo_brief_core_ranking_changed": False,
            "default_use": False,
            "promotion_requires_measurement": True,
        },
        "mutation_boundary": {
            "writes": ["external_semantic_records", "bridge_report"],
            "does_not_mutate": ["repobrief_core", "repo_worktree", "git", "pull_requests"],
            "does_not_crawl_repo": True,
        },
        "does_not_establish": DOES_NOT_ESTABLISH,
    }
    if goldset is not None:
        report["evaluation"] = evaluate_recall(records, goldset)
    else:
        report["evaluation"] = {
            "status": "not_run",
            "reason": "no_goldset_provided",
            "promotion_allowed": False,
        }
    return report


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")


def write_parquet(path: Path, records: Sequence[dict[str, Any]]) -> None:
    if pd is None:
        raise RuntimeError("pandas is required for parquet output")
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(list(records)).to_parquet(path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunk-index", required=True, type=Path)
    parser.add_argument("--default-repo-id", default="repo")
    parser.add_argument("--dim", type=int, default=DEFAULT_DIM)
    parser.add_argument("--out-jsonl", type=Path)
    parser.add_argument("--out-parquet", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--goldset", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    rows = read_jsonl(args.chunk_index)
    records = build_records(rows, default_repo_id=args.default_repo_id, dim=args.dim)
    goldset = read_jsonl(args.goldset) if args.goldset else None
    if args.out_jsonl:
        write_jsonl(args.out_jsonl, records)
    if args.out_parquet:
        write_parquet(args.out_parquet, records)
    report = build_report(chunk_index=args.chunk_index, records=records, goldset=goldset)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
