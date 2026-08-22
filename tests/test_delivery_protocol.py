"""Executable checks for the cross-repository recogniser delivery protocol."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_recogniser_issue_template_requires_independent_delivery_evidence() -> None:
    template = (ROOT / ".github/ISSUE_TEMPLATE/recogniser.yml").read_text(encoding="utf-8")
    for requirement in (
        "Geometry scope",
        "Record contract",
        "Negative and ambiguous cases",
        "Canonical functional tests",
        "Performance budget",
        "Provenance",
        "Downstream capability decisions",
        "Compatibility and landing plan",
    ):
        assert requirement in template


def test_protocol_defines_every_ownership_and_compatibility_boundary() -> None:
    protocol = (ROOT / "docs/delivery-protocol.md").read_text(encoding="utf-8")
    for owned_evidence in (
        "geometry contract and canonical functional tests",
        "IR adapter",
        "DSL and generated-code round trip",
        "drawing regression",
        "completeness semantics",
    ):
        assert owned_evidence in protocol
    for phase in (
        "1. Propose and freeze evidence",
        "2. Publish an additive package contract",
        "3. Add consumer support",
        "4. Enable behavior",
        "5. Clean up and deprecate",
    ):
        assert phase in protocol
    for compatibility_rule in (
        "prerelease",
        "lockfile",
        "rollback",
        "deprecation",
        "geometry-only",
        "deferred",
    ):
        assert compatibility_rule in protocol.lower()


def test_boss_walkthrough_proves_each_intermediate_state() -> None:
    walkthrough = (ROOT / "docs/delivery-protocol.md").read_text(encoding="utf-8")
    assert "BossRecord walkthrough" in walkthrough
    assert walkthrough.count("Both repositories green:") >= 4


def test_contributor_and_pr_surfaces_link_the_protocol() -> None:
    for path in ("CONTRIBUTING.md", ".github/pull_request_template.md"):
        text = (ROOT / path).read_text(encoding="utf-8")
        assert "docs/delivery-protocol.md" in text


def test_package_branch_runs_one_full_matrix_not_push_and_pr_duplicates() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "push:\n    branches: [main]" in workflow
    assert "pull_request:" in workflow
    assert "github.event.pull_request.number || github.run_id" in workflow
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in workflow
