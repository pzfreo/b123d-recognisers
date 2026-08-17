# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

from b123d_recognisers import __version__ as _PACKAGE_VERSION

ROOT = Path(__file__).parents[1]
README = ROOT / "README.md"
WORKFLOW = ROOT / ".github" / "workflows" / "publish.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
VERIFY = ROOT / "tools" / "verify_release_assets.py"


def _parsed(path: Path) -> dict:
    """A workflow as structure, not as text.

    Every workflow assertion here used to be a substring search, and five review rounds each
    found one that could be satisfied by something other than the thing it meant to check --
    a `uv build` in a different job, a `RELEASE_TAG#v` two steps away, and at the low point an
    assertion that `verify_release_assets.py` appears in `build-release` satisfied by a
    *comment about* `verify_release_assets.py`, so deleting the step that runs it stayed green.
    Substring matching cannot express "this job needs that job" or "this step runs that
    command", which is what the assertions were always about.

    PyYAML resolves the `on:` key to the boolean True (YAML 1.1), so callers wanting triggers
    should use `_triggers` rather than indexing `"on"`.
    """

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _steps(job: dict) -> list[str]:
    """Every `run:` body in a job, so a command can be located in the step that runs it."""

    return [step["run"] for step in job["steps"] if "run" in step]


def _triggers(workflow: dict) -> set[str]:
    """The event names a workflow runs on, however `on:` is spelled."""

    on = workflow.get("on", workflow.get(True))
    if isinstance(on, str):
        return {on}
    return set(on)


def _run_guard(script: str, **env: str) -> subprocess.CompletedProcess:
    """Execute one workflow `run:` body, so a guard is tested by what it does.

    Asserting a guard's *name* appears is not a test of it: `if [[ ... ]]` replaced by
    `if false`, and the release-notes gate inverted from `if ! grep` to `if grep`, both left
    the suite green.
    """

    return subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={"PATH": os.environ["PATH"], **env},
    )


def _job(workflow: str, name: str) -> str:
    """The body of one job, so an assertion cannot be satisfied by a different job.

    Several checks here were whole-file substring searches, and the snapshot job happens to
    contain `uv build` and the TestPyPI `repository-url` too. So deleting `uv build` from
    `build-release` passed, and redirecting the release's first leg at production PyPI --
    bypassing the `pypi` environment's approval -- passed as well.
    """

    start = workflow.index(f"\n  {name}:\n")
    rest = workflow[start + 1 :]
    following = re.search(r"^  [a-z][\w-]*:$", rest[len(f"  {name}:") :], re.M)
    return rest if following is None else rest[: len(f"  {name}:") + following.start()]


def test_publish_workflow_uses_oidc_environments_and_one_promoted_artifact() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "push:" in workflow and "release:" in workflow
    assert "\npermissions: {}\n" in workflow, "publishing must default the token to no permissions"
    assert "environment:\n      name: testpypi" in workflow
    assert "environment:\n      name: pypi" in workflow
    assert "repository-url: https://test.pypi.org/legacy/" in workflow
    assert "password:" not in workflow and "API_TOKEN" not in workflow
    assert "enable-cache: false" in workflow, "release workflows must not consume mutable caches"

    # The artifact is built here, from the tagged commit, and never uploaded from a
    # maintainer's machine. The previous shape asserted the opposite -- `"uv build" not in
    # workflow` -- because it promoted a hand-built asset attached to the GitHub release.
    # That could only check the asset's version against the tag, which a wheel built from a
    # dirty tree also satisfies.
    assert "gh release download" not in workflow, "nothing hand-attached may be promoted"

    # One build feeds TestPyPI and PyPI, so the bytes installed from the first are the bytes
    # promoted to the second: upload once, download in each publishing job. Pinned by digest,
    # not by tag -- this is the workflow holding `id-token: write` against PyPI. An earlier
    # version of this test replaced the digests with these bare counts, which would have let
    # `actions/upload-artifact@v6` through; both belong here.
    assert workflow.count("actions/upload-artifact@") == 1
    assert workflow.count("actions/download-artifact@") == 1
    assert workflow.count(
        "actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f"
    ) == 1
    assert workflow.count(
        "actions/download-artifact@37930b1c2abaa49bbe596cd826c3c89aef350131"
    ) == 1

    # Every workflow that runs on `pull_request` must be dispatched by name for the
    # post-release bump PR, because a branch pushed with GITHUB_TOKEN raises no events and
    # would otherwise arrive with no checks at all. Asserting the *set* rather than one name:
    # dispatching only ci.yml is how this was wrong the first time it was fixed.
    on_pull_request = {
        path.name
        for path in (ROOT / ".github" / "workflows").iterdir()
        if path.suffix in {".yml", ".yaml"}
        and re.search(
            r"""(?mx) ^["']?on["']?:\s*
                ( \n(?:.*\n)*?\ \ -?\ ?pull_request:?\s*$   # block map or sequence
                | \[[^]]*\bpull_request\b                      # flow list
                | \ *pull_request\s*$ )                         # bare scalar""",
            path.read_text(encoding="utf-8"),
        )
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
    # The bump derives its next version from `main`, as the ported workflow does, so there is
    # no RELEASE_TAG-in-the-wrong-scope bug to have. An earlier attempt derived it from the tag
    # and read that variable in a step where it was not defined, which would have failed every
    # release after PyPI had accepted the artifact.
    assert "actions: write" in _job(workflow, "bump-version")
    for name in on_pull_request:
        target = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        assert "workflow_dispatch:" in target, f"{name} is dispatched but declares no trigger"
    # Three publish steps: the main-push snapshot, and the release's TestPyPI and PyPI legs.
    assert workflow.count("pypa/gh-action-pypi-publish@") == 2
    assert workflow.count(
        "pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33"
    ) == 2, "the action holding id-token against PyPI must be pinned by digest"
    assert workflow.count("id-token: write") == 2


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


def test_the_release_pipeline_is_the_ported_shape() -> None:
    """Four jobs and one chain, matching the workflow this was ported from.

    Asserted because the previous attempt drifted into six jobs with three extra guards, and
    every one of five review rounds found its defects in that added machinery rather than in
    the ported part. A `needs:` graph is also invisible to substring matching, which is what
    the assertions here used to be: pointing `publish-pypi` at the wrong job was green.
    """

    jobs = _parsed(WORKFLOW)["jobs"]

    assert list(jobs) == ["publish-testpypi", "build-release", "publish-pypi", "bump-version"]
    assert jobs["publish-pypi"]["needs"] == "build-release"
    assert jobs["bump-version"]["needs"] == "publish-pypi"
    # One build feeds the release; the snapshot builds and publishes on a single runner.
    uploads = [name for name, spec in jobs.items()
               if any("upload-artifact" in str(step) for step in spec["steps"])]
    assert uploads == ["build-release"]


def test_the_release_artifact_is_built_here_and_published_unmodified() -> None:
    """The point of the port: the wheel is a function of the tagged commit.

    Located in the step that runs it. `assert "uv build" in job_text` was satisfied by the
    snapshot job, and at the low point `assert "verify_release_assets.py" in job_text` was
    satisfied by a *comment about* it, so deleting the step that ran it stayed green.
    """

    jobs = _parsed(WORKFLOW)["jobs"]
    build = [line.strip() for run in _steps(jobs["build-release"]) for line in run.splitlines()
             if line.strip() and not line.strip().startswith("#")]

    assert "uv build" in build
    assert any("scripts/update-recogniser-version" in line for line in build)
    assert "gh release download" not in WORKFLOW.read_text(encoding="utf-8")

    publish = jobs["publish-pypi"]["steps"]
    assert not any("run" in step for step in publish), "the release must not be rebuilt here"
    action = next(s for s in publish if "gh-action-pypi-publish" in s.get("uses", ""))
    assert "with" not in action, "PyPI is the default index; a repository-url would redirect it"


def test_the_bump_opens_a_pr_and_dispatches_every_pull_request_workflow() -> None:
    """`git push origin HEAD:main` was green; the job holds `contents: write`."""

    jobs = _parsed(WORKFLOW)["jobs"]
    joined = "\n".join(_steps(jobs["bump-version"]))

    assert 'git push origin HEAD:"$branch"' in joined
    assert "HEAD:main" not in joined and "origin main" not in joined

    dispatched = re.search(r"^\s*for workflow in (.+?); do$", joined, re.M)
    assert dispatched, "the dispatch loop is missing or has been reshaped"
    on_pull_request = {
        path.name
        for path in (ROOT / ".github" / "workflows").iterdir()
        if path.suffix in {".yml", ".yaml"} and "pull_request" in _triggers(_parsed(path))
    }
    # Parsed from the loop, not searched for in the file: the comment beside it names ci.yml,
    # so a substring check passed with ci.yml removed from the loop.
    assert set(dispatched.group(1).split()) == on_pull_request
    for name in on_pull_request:
        assert "workflow_dispatch" in _triggers(_parsed(ROOT / ".github" / "workflows" / name))
