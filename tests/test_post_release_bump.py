# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

from __future__ import annotations

import runpy
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
_VALIDATE = runpy.run_path(str(ROOT / "tools/check_post_release_bump.py"))["validate"]
_FILES = (
    "pyproject.toml",
    "src/b123d_recognisers/__init__.py",
    "src/b123d_recognisers/capabilities.json",
    "uv.lock",
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, stdout=subprocess.PIPE)


@pytest.fixture
def mechanical_bump(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    for relative in _FILES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"identity = 0.3.0.dev0 in {relative}\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "release source")
    _git(tmp_path, "tag", "v0.3.0")
    for relative in _FILES:
        path = tmp_path / relative
        path.write_text(f"identity = 0.3.1.dev0 in {relative}\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "release.md").write_text("workflow explanation\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "post-release bump")
    return tmp_path


def test_generated_bump_accepts_only_the_next_patch_identity(mechanical_bump: Path) -> None:
    assert _VALIDATE(
        mechanical_bump, "v0.3.0", "automation/post-release-v0.3.0-123"
    ) == ("0.3.0.dev0", "0.3.1.dev0")


def test_generated_bump_rejects_an_extra_runtime_change(mechanical_bump: Path) -> None:
    runtime = mechanical_bump / "src/b123d_recognisers/runtime.py"
    runtime.write_text("changed = True\n", encoding="utf-8")
    _git(mechanical_bump, "add", ".")
    _git(mechanical_bump, "commit", "-qm", "runtime change")

    with pytest.raises(ValueError, match="wheel-facing change set"):
        _VALIDATE(mechanical_bump, "v0.3.0", "automation/post-release-v0.3.0-123")


def test_generated_bump_rejects_more_than_a_version_substitution(
    mechanical_bump: Path,
) -> None:
    project = mechanical_bump / "pyproject.toml"
    project.write_text(project.read_text(encoding="utf-8") + "other = change\n", encoding="utf-8")
    _git(mechanical_bump, "add", ".")
    _git(mechanical_bump, "commit", "-qm", "extra build change")

    with pytest.raises(ValueError, match="pyproject.toml changes more"):
        _VALIDATE(mechanical_bump, "v0.3.0", "automation/post-release-v0.3.0-123")


def test_generated_bump_rejects_a_branch_without_the_tag_identity(
    mechanical_bump: Path,
) -> None:
    with pytest.raises(ValueError, match="branch does not match"):
        _VALIDATE(mechanical_bump, "v0.3.0", "feature/not-a-release-bump")
