from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RETIRED = {"hausKI", "heimgeist", "heimlern"}


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
        consumers = set(contract["x-consumers"])
        retired = set(contract.get("x-retired-consumers", []))

        assert consumers == expected_consumers
        assert consumers.isdisjoint(RETIRED)
        assert retired <= RETIRED
        assert retired


def test_feedback_loop_has_no_retired_escalation_target() -> None:
    policy = yaml.safe_load(
        (ROOT / "policy/feedback-loop.v1.yml").read_text(encoding="utf-8")
    )

    assert policy["actions"]["escalate"] == []
