# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

import subprocess
import sys
from pathlib import Path

from b123d_recognisers import __version__ as _PACKAGE_VERSION

ROOT = Path(__file__).parents[1]
README = ROOT / "README.md"
WORKFLOW = ROOT / ".github" / "workflows" / "publish.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
VERIFY = ROOT / "tools" / "verify_release_assets.py"


def test_publish_workflow_uses_oidc_environments_and_one_promoted_artifact() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow and "release:" in workflow
    assert "\npermissions: {}\n" in workflow, "publishing must default the token to no permissions"
    assert workflow.count("id-token: write") == 2
    assert "environment:\n      name: testpypi" in workflow
    assert "environment:\n      name: pypi" in workflow
    assert "repository-url: https://test.pypi.org/legacy/" in workflow
    assert workflow.count("actions/download-artifact@") == 2
    assert workflow.count("pypa/gh-action-pypi-publish@") == 2
    assert "password:" not in workflow and "API_TOKEN" not in workflow
    assert "uv build" not in workflow, "publish must promote reviewed GitHub release assets"
    assert "enable-cache: false" in workflow, "release workflows must not consume mutable caches"
    assert workflow.count(
        "actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f"
    ) == 1
    assert workflow.count(
        "actions/download-artifact@37930b1c2abaa49bbe596cd826c3c89aef350131"
    ) == 2
    assert "ignore-empty-workdir: true" in workflow
    assert "--refresh-package b123d-recognisers" in workflow


def test_ci_workflow_pins_node24_actions() -> None:
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert workflow.count("actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803") == 2
    assert workflow.count("astral-sh/setup-uv@37802adc94f370d6bfd71619e3f0bf239e1f3b78") == 2
    assert workflow.count("actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f") == 1
    assert workflow.count("codecov/codecov-action@fb8b3582c8e4def4969c97caa2f19720cb33a72f") == 1
    assert "actions/checkout@v" not in workflow
    assert "astral-sh/setup-uv@v" not in workflow
    assert "actions/upload-artifact@v" not in workflow
    assert "codecov/codecov-action@v" not in workflow
    assert "id-token: write" in workflow
    assert "use_oidc: true" in workflow
    assert "fail_ci_if_error: true" in workflow


def test_readme_links_the_codecov_badge_to_the_public_project() -> None:
    readme = README.read_text(encoding="utf-8")

    badge = "https://codecov.io/gh/pzfreo/b123d-recognisers/graph/badge.svg"
    project = "https://codecov.io/gh/pzfreo/b123d-recognisers"
    assert f"[![codecov]({badge})]({project})" in readme


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
        [sys.executable, str(VERIFY), "--dist", str(dist), "--tag", f"v{_PACKAGE_VERSION}"],
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
    assert (
        f"tag version 9.9.9 does not match artifact version {_PACKAGE_VERSION}" in wrong.stderr
    )
