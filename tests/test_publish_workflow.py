# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "publish.yml"
VERIFY = ROOT / "tools" / "verify_release_assets.py"


def test_publish_workflow_uses_oidc_environments_and_one_promoted_artifact() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow and "release:" in workflow
    assert "permissions:\n      id-token: write" in workflow
    assert "environment:\n      name: testpypi" in workflow
    assert "environment:\n      name: pypi" in workflow
    assert "repository-url: https://test.pypi.org/legacy/" in workflow
    assert workflow.count("actions/download-artifact@") == 2
    assert workflow.count("pypa/gh-action-pypi-publish@") == 2
    assert "password:" not in workflow and "API_TOKEN" not in workflow
    assert "uv build" not in workflow, "publish must promote reviewed GitHub release assets"


def test_release_asset_verifier_accepts_the_built_version_and_rejects_a_wrong_tag(
    tmp_path: Path,
) -> None:
    dist = tmp_path / "dist"
    subprocess.run(
        ["uv", "build", "--out-dir", str(dist)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )

    valid = subprocess.run(
        [sys.executable, str(VERIFY), "--dist", str(dist), "--tag", "v0.1.0a1"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert valid.returncode == 0, valid.stderr

    wrong = subprocess.run(
        [sys.executable, str(VERIFY), "--dist", str(dist), "--tag", "v9.9.9"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert wrong.returncode != 0
    assert "tag version 9.9.9 does not match artifact version 0.1.0a1" in wrong.stderr
