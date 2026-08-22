#!/usr/bin/env python3
"""Validate the generated next-patch ``.dev0`` bump without widening a consumer.

The released tag has already passed the Draftwright candidate canary. Its automatic follow-up
branch changes the package identity to the next patch, which Draftwright must reject until that
transition is reviewed. This check proves that the generated commit changes exactly the four
synchronized version copies relative to its checked-out main parent, so the downstream status
remains meaningful without opening Draftwright's fail-closed version gate.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

_TAG = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_VERSION_FILES = (
    "pyproject.toml",
    "src/b123d_recognisers/__init__.py",
    "src/b123d_recognisers/capabilities.json",
    "uv.lock",
)
_ROOT_WHEEL_INPUTS = {
    ".gitattributes",
    ".gitignore",
    "LICENSE",
    "NOTICE",
    "README.md",
    "THIRD_PARTY_NOTICES.md",
    "pyproject.toml",
    "uv.lock",
}


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, text=True, stdout=subprocess.PIPE
    ).stdout.rstrip("\n")


def _git_bytes(root: Path, *args: str) -> bytes:
    """Read object content without newline decoding or trimming."""

    return subprocess.run(
        ["git", *args], cwd=root, check=True, stdout=subprocess.PIPE
    ).stdout


def validate(root: Path, released_tag: str, branch: str, bump_sha: str) -> tuple[str, str]:
    """Return ``(released, development)`` or raise on a non-mechanical branch."""

    match = _TAG.fullmatch(released_tag)
    if match is None:
        raise ValueError("released tag must be vX.Y.Z")
    released = ".".join(match.groups())
    tagged = f"{released}.dev0"
    major, minor, patch = (int(part) for part in match.groups())
    development = f"{major}.{minor}.{patch + 1}.dev0"
    expected_branch = re.compile(
        rf"^automation/post-release-{re.escape(released_tag)}-[0-9]+$"
    )
    if expected_branch.fullmatch(branch) is None:
        raise ValueError("branch does not match the generated post-release convention")

    tag_commit = _git(root, "rev-parse", "--verify", f"refs/tags/{released_tag}^{{commit}}")
    main_commit = _git(root, "rev-parse", "--verify", "refs/remotes/origin/main^{commit}")
    bump_commit = _git(root, "rev-parse", "--verify", f"{bump_sha}^{{commit}}")
    bump_parent = _git(root, "rev-parse", "--verify", f"{bump_commit}^")
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", tag_commit, bump_parent], cwd=root, check=True
    )
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", bump_parent, main_commit], cwd=root, check=True
    )
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", bump_commit, "HEAD"], cwd=root, check=True
    )
    changed = set(_git(root, "diff", "--name-only", f"{bump_parent}..{bump_commit}").splitlines())
    if changed != set(_VERSION_FILES):
        extra = sorted(changed - set(_VERSION_FILES))
        missing = sorted(set(_VERSION_FILES) - changed)
        raise ValueError(
            "generated commit does not change exactly the four version files; "
            f"extra={extra}, missing={missing}"
        )
    summary = _git(root, "diff", "--summary", f"{bump_parent}..{bump_commit}")
    if summary:
        raise ValueError(f"generated commit changes file metadata: {summary}")
    later_changes = set(
        _git(root, "diff", "--no-renames", "--name-only", f"{bump_commit}..HEAD").splitlines()
    )
    later_wheel_changes = sorted(
        path for path in later_changes if path in _ROOT_WHEEL_INPUTS or path.startswith("src/")
    )
    if later_wheel_changes:
        raise ValueError(
            f"wheel-facing files changed after the generated bump: {later_wheel_changes}"
        )

    for relative in _VERSION_FILES:
        before = _git_bytes(root, "show", f"{bump_parent}:{relative}")
        after = _git_bytes(root, "show", f"{bump_commit}:{relative}")
        tagged_bytes = tagged.encode()
        development_bytes = development.encode()
        if before.count(tagged_bytes) != 1:
            raise ValueError(f"{relative} does not contain exactly one {tagged} identity")
        if before.replace(tagged_bytes, development_bytes) != after:
            raise ValueError(f"{relative} changes more than {tagged} -> {development}")
    return tagged, development


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--released-tag", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--bump-sha", required=True)
    args = parser.parse_args()
    try:
        released, development = validate(
            Path.cwd(), args.released_tag, args.branch, args.bump_sha
        )
    except (ValueError, subprocess.CalledProcessError) as error:
        parser.error(str(error))
    print(f"validated mechanical post-release identity: {released} -> {development}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
