"""Executable checks for the cross-repository recogniser delivery protocol."""

from __future__ import annotations

import json
import runpy
import subprocess
import sys
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

ROOT = Path(__file__).parents[1]
_HARNESS = runpy.run_path(str(ROOT / "tools/check_downstream.py"))
_wheel_version = cast(Callable[[Path], str], _HARNESS["_wheel_version"])
_adapt_exported_draftwright_version = cast(
    Callable[[Path, str], None], _HARNESS["_adapt_exported_draftwright_version"]
)


def test_recogniser_issue_template_requires_independent_delivery_evidence() -> None:
    template = (ROOT / ".github/ISSUE_TEMPLATE/recogniser.yml").read_text(encoding="utf-8")
    for requirement in (
        "Geometry scope",
        "Record contract",
        "Negative and ambiguous cases",
        "Canonical goldens",
        "Performance budget",
        "Provenance",
        "Downstream capability decisions",
        "Compatibility and landing plan",
    ):
        assert requirement in template


def test_protocol_defines_every_ownership_and_compatibility_boundary() -> None:
    protocol = (ROOT / "docs/delivery-protocol.md").read_text(encoding="utf-8")
    for owned_evidence in (
        "geometry contract and canonical goldens",
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


def test_two_checkout_harness_exposes_bounded_candidate_plan() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/check_downstream.py"),
            "--draftwright",
            str(ROOT),
            "--plan",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    plan = json.loads(result.stdout)
    assert [step["name"] for step in plan] == [
        "package-contract",
        "build-candidate-wheel",
        "prepare-draftwright",
        "install-candidate-wheel",
        "draftwright-contract",
    ]
    joined = "\n".join(" ".join(step["command"]) for step in plan)
    assert "test_capability_manifest.py" in joined
    assert "test_recogniser_capabilities.py" in joined
    assert "not installed_released_package_contract" in joined
    assert "--no-deps" in joined


def test_candidate_harness_reads_wheel_version_and_adapts_only_disposable_export(
    tmp_path: Path,
) -> None:
    wheel = tmp_path / "candidate.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            "b123d_recognisers-0.2.1.dist-info/METADATA",
            "Metadata-Version: 2.4\nName: b123d-recognisers\nVersion: 0.2.1\n",
        )
    export = tmp_path / "export"
    contract = export / "src" / "draftwright" / "recogniser_contract.py"
    contract.parent.mkdir(parents=True)
    contract.write_text('_PACKAGE_VERSION = "0.2.0"\nUNCHANGED = True\n', encoding="utf-8")

    version = _wheel_version(wheel)
    _adapt_exported_draftwright_version(export, version)

    assert version == "0.2.1"
    assert contract.read_text(encoding="utf-8") == (
        '_PACKAGE_VERSION = "0.2.1"\nUNCHANGED = True\n'
    )


def test_candidate_harness_fails_closed_on_ambiguous_consumer_declaration(tmp_path: Path) -> None:
    contract = tmp_path / "src" / "draftwright" / "recogniser_contract.py"
    contract.parent.mkdir(parents=True)
    contract.write_text(
        '_PACKAGE_VERSION = "0.2.0"\n_PACKAGE_VERSION = "0.2.0"\n', encoding="utf-8"
    )

    with pytest.raises(SystemExit, match="one Draftwright package-version declaration"):
        _adapt_exported_draftwright_version(tmp_path, "0.2.1")


def test_contributor_and_pr_surfaces_link_the_protocol() -> None:
    for path in ("CONTRIBUTING.md", ".github/pull_request_template.md"):
        text = (ROOT / path).read_text(encoding="utf-8")
        assert "docs/delivery-protocol.md" in text


def test_hosted_downstream_canary_is_narrow_reproducible_and_auditable() -> None:
    workflow = (ROOT / ".github/workflows/downstream-canary.yml").read_text(encoding="utf-8")
    assert "pull_request:" in workflow and "schedule:" in workflow
    assert workflow.count("runs-on:") == 1, "the canary is one job, not another platform matrix"
    assert "repository: pzfreo/draftwright" in workflow
    assert "ref: main" in workflow
    assert "tools/check_downstream.py --draftwright ../draftwright" in workflow
    assert "git -C ../draftwright rev-parse HEAD" in workflow
    assert "capability_manifest(format_version=1)" in workflow
    assert "GITHUB_STEP_SUMMARY" in workflow
    assert "Wall time" in workflow
    assert "matrix:" not in workflow


def test_package_branch_runs_one_full_matrix_not_push_and_pr_duplicates() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "push:\n    branches: [main]" in workflow
    assert "pull_request:" in workflow
    assert "github.event.pull_request.number || github.run_id" in workflow
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in workflow
