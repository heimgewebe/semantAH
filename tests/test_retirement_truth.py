from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RETIRED = {"hauski", "heimgeist", "heimlern", "mitschreiber"}
ACTIVE_DOCS = (
    "docs/contracts/output.md",
    "docs/semantAH/observatory.md",
)
HISTORICAL_DOCS = (
    "docs/mitschreiber-index.md",
    "docs/semantAH.md",
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


def test_legacy_docs_are_explicitly_historical() -> None:
    for relative in HISTORICAL_DOCS:
        head = "\n".join(
            (ROOT / relative).read_text(encoding="utf-8").splitlines()[:8]
        ).casefold()
        assert "historischer entwurf" in head


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
