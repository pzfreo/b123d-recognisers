# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

import re
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

    assert "push:" in workflow and "release:" in workflow
    assert "\npermissions: {}\n" in workflow, "publishing must default the token to no permissions"
    assert "environment:\n      name: testpypi" in workflow
    assert "environment:\n      name: pypi" in workflow
    assert "repository-url: https://test.pypi.org/legacy/" in workflow
    assert "password:" not in workflow and "API_TOKEN" not in workflow
    assert "enable-cache: false" in workflow, "release workflows must not consume mutable caches"
    assert "ignore-empty-workdir: true" in workflow
    assert "--refresh-package b123d-recognisers" in workflow

    # The artifact is built here, from the tagged commit, and never uploaded from a
    # maintainer's machine. The previous shape asserted the opposite -- `"uv build" not in
    # workflow` -- because it promoted a hand-built asset attached to the GitHub release.
    # That could only check the asset's version against the tag, which a wheel built from a
    # dirty tree also satisfies.
    assert "uv build" in workflow, "the published artifact must be built from the tag"
    assert "gh release download" not in workflow, "nothing hand-attached may be promoted"

    # One build feeds TestPyPI and PyPI, so the bytes installed from the first are the bytes
    # promoted to the second: upload once, download in each publishing job. Pinned by digest,
    # not by tag -- this is the workflow holding `id-token: write` against PyPI. An earlier
    # version of this test replaced the digests with these bare counts, which would have let
    # `actions/upload-artifact@v6` through; both belong here.
    assert workflow.count("actions/upload-artifact@") == 1
    assert workflow.count("actions/download-artifact@") == 2
    assert workflow.count(
        "actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f"
    ) == 1
    assert workflow.count(
        "actions/download-artifact@37930b1c2abaa49bbe596cd826c3c89aef350131"
    ) == 2

    # Every workflow that runs on `pull_request` must be dispatched by name for the
    # post-release bump PR, because a branch pushed with GITHUB_TOKEN raises no events and
    # would otherwise arrive with no checks at all. Asserting the *set* rather than one name:
    # dispatching only ci.yml is how this was wrong the first time it was fixed.
    on_pull_request = {
        path.name
        for path in (ROOT / ".github" / "workflows").iterdir()
        if path.suffix in {".yml", ".yaml"}
        and re.search(r"(?m)^on:\s*(\n(?:.*\n)*?  pull_request:|\[[^]]*\bpull_request\b)",
                      path.read_text(encoding="utf-8"))
    }
    dispatched = re.search(r"^\s*for workflow in (.+?); do$", workflow, re.M)
    assert dispatched, "the dispatch loop is missing or has been reshaped"
    # Parsed from the loop, not searched for in the file. `assert name in workflow` passed
    # with ci.yml removed from the loop, because the comment above it says the words "ci.yml"
    # -- so the test could not detect the exact defect it was written for.
    assert set(dispatched.group(1).split()) == on_pull_request, (
        f"dispatch loop runs {dispatched.group(1)}, but the workflows triggered by "
        f"pull_request are {sorted(on_pull_request)}"
    )
    assert "actions: write" in workflow, "dispatching CI needs actions: write"
    for name in on_pull_request:
        target = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        assert "workflow_dispatch:" in target, f"{name} is dispatched but declares no trigger"
    # Three publish steps: the main-push snapshot, and the release's TestPyPI and PyPI legs.
    assert workflow.count("pypa/gh-action-pypi-publish@") == 3
    assert workflow.count("id-token: write") == 3


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
