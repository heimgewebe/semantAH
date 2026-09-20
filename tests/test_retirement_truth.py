from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RETIRED = {"hauski", "heimgeist", "heimlern", "mitschreiber"}
ACTIVE_DOCS = (
    "docs/contracts/output.md",
    "docs/embeddings.md",
    "docs/semantAH/observatory.md",
)
HISTORICAL_DOCS = (
    "docs/blueprint.md",
    "docs/hauski.md",
    "docs/mitschreiber-index.md",
    "docs/semantAH-feedback-loop.md",
    "docs/semantAH.md",
    "docs/semantAH/comprehensive-optimization-strategy.md",
)


def _json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_readme_does_not_claim_live_hauski_repository_dependency() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "https://github.com/heimgewebe/hausKI" not in readme
    assert "keine aktive HausKI-Abhängigkeit" in readme
    assert "Historischer HausKI-Entwurf" in readme


def test_contract_consumers_do_not_reactivate_retired_repositories() -> None:
    cases = {
        "contracts/insights.schema.json": {"chronik"},
        "contracts/knowledge.observatory.schema.json": {"leitstand"},
        "contracts/os.context.text.embed.schema.json": {"leitstand"},
    }

    for relative, expected_consumers in cases.items():
        contract = _json(relative)
        consumers = {value.casefold() for value in contract.get("x-consumers", [])}

        assert consumers == expected_consumers
        assert consumers.isdisjoint(RETIRED)


def test_active_docs_do_not_claim_retired_consumers() -> None:
    for relative in ACTIVE_DOCS:
        text = (ROOT / relative).read_text(encoding="utf-8").casefold()
        for retired in RETIRED:
            assert retired not in text, f"{relative} still presents retired name {retired}"




def test_readme_current_docs_do_not_use_historical_sources_as_current_truth() -> None:
    readme_lines = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
    marker = next(
        index
        for index, line in enumerate(readme_lines)
        if "Aktuelle Dokumentation:" in line
    )
    current_docs: list[str] = []
    for line in readme_lines[marker + 1 :]:
        if not line.startswith("- "):
            break
        start = line.find("(docs/")
        if start == -1:
            continue
        start += 1
        end = line.find(")", start)
        current_docs.append(line[start:end])

    assert set(current_docs) == {"docs/embeddings.md", "docs/namespaces.md"}

    for relative in current_docs:
        lines = (ROOT / relative).read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            for historical in HISTORICAL_DOCS:
                if historical not in line:
                    continue
                context = " ".join(
                    lines[max(0, index - 2) : min(len(lines), index + 3)]
                ).casefold()
                assert any(
                    marker in context
                    for marker in ("histor", "früher", "entwurf", "legacy")
                ), (
                    f"{relative} uses historical source {historical} "
                    "without marking the reference as historical"
                )


def test_legacy_docs_are_explicitly_historical() -> None:
    for relative in HISTORICAL_DOCS:
        head = "\n".join(
            (ROOT / relative).read_text(encoding="utf-8").splitlines()[:8]
        ).casefold()
        assert "historisch" in head


def test_legacy_hauski_source_value_is_explicitly_non_current() -> None:
    source = _json("contracts/insights.schema.json")["properties"]["source"]

    assert "hauski" in {value.casefold() for value in source["enum"]}
    assert "legacy serialized source value" in source["description"]
    assert "does not establish a current repository or service" in source["description"]


def test_feedback_loop_has_no_retired_escalation_target() -> None:
    policy = yaml.safe_load(
        (ROOT / "policy/feedback-loop.v1.yml").read_text(encoding="utf-8")
    )

    assert policy["actions"]["escalate"] == []
