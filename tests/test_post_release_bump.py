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


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, text=True, stdout=subprocess.PIPE
    ).stdout.strip()


@pytest.fixture
def mechanical_bump(tmp_path: Path) -> tuple[Path, str]:
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
    # Publication is protected and can wait. A normal main commit made during that wait belongs
    # to the bump's parent, not to the mechanical commit the generated PR must prove.
    advanced = tmp_path / "src/b123d_recognisers/post_release.py"
    advanced.write_text("advanced = True\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "release.md").write_text("workflow explanation\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "main advanced after release")
    for relative in _FILES:
        path = tmp_path / relative
        path.write_text(f"identity = 0.3.1.dev0 in {relative}\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "post-release bump")
    bump_sha = _git(tmp_path, "rev-parse", "HEAD")
    return tmp_path, bump_sha


def test_generated_bump_accepts_only_the_next_patch_identity(
    mechanical_bump: tuple[Path, str],
) -> None:
    root, bump_sha = mechanical_bump
    assert _VALIDATE(
        root, "v0.3.0", "automation/post-release-v0.3.0-123", bump_sha
    ) == ("0.3.0.dev0", "0.3.1.dev0")


def test_generated_bump_rejects_an_extra_runtime_change(
    mechanical_bump: tuple[Path, str],
) -> None:
    root, bump_sha = mechanical_bump
    runtime = root / "src/b123d_recognisers/runtime.py"
    runtime.write_text("changed = True\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "runtime change")

    with pytest.raises(ValueError, match="wheel-facing files changed after"):
        _VALIDATE(root, "v0.3.0", "automation/post-release-v0.3.0-123", bump_sha)


def test_generated_bump_rejects_more_than_a_version_substitution(
    mechanical_bump: tuple[Path, str],
) -> None:
    root, bump_sha = mechanical_bump
    project = root / "pyproject.toml"
    project.write_text(project.read_text(encoding="utf-8") + "other = change\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "--amend", "--no-edit", "-q")
    bump_sha = _git(root, "rev-parse", "HEAD")

    with pytest.raises(ValueError, match="pyproject.toml changes more"):
        _VALIDATE(root, "v0.3.0", "automation/post-release-v0.3.0-123", bump_sha)


def test_generated_bump_rejects_root_wheel_metadata_changed_afterward(
    mechanical_bump: tuple[Path, str],
) -> None:
    root, bump_sha = mechanical_bump
    (root / "README.md").write_text("different wheel metadata\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "metadata change")

    with pytest.raises(ValueError, match="README.md"):
        _VALIDATE(root, "v0.3.0", "automation/post-release-v0.3.0-123", bump_sha)


def test_generated_bump_rejects_a_branch_without_the_tag_identity(
    mechanical_bump: tuple[Path, str],
) -> None:
    root, bump_sha = mechanical_bump
    with pytest.raises(ValueError, match="branch does not match"):
        _VALIDATE(root, "v0.3.0", "feature/not-a-release-bump", bump_sha)
