#!/usr/bin/env python3
"""Validate the generated next-patch ``.dev0`` bump without widening a consumer.

The released tag has already passed the Draftwright candidate canary. Its automatic follow-up
branch changes the package identity to the next patch, which Draftwright must reject until that
transition is reviewed. This check proves that the branch has not changed any wheel-facing input
except the four synchronized version copies, so the downstream status remains meaningful without
opening Draftwright's fail-closed version gate.
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


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, text=True, stdout=subprocess.PIPE
    ).stdout.rstrip("\n")


def validate(root: Path, released_tag: str, branch: str) -> tuple[str, str]:
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

    _git(root, "rev-parse", "--verify", f"refs/tags/{released_tag}^{{commit}}")
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", released_tag, "HEAD"], cwd=root, check=True
    )
    changed = set(_git(root, "diff", "--name-only", f"{released_tag}..HEAD").splitlines())
    protected = {
        path
        for path in changed
        if path == "pyproject.toml" or path == "uv.lock" or path.startswith("src/")
    }
    if protected != set(_VERSION_FILES):
        extra = sorted(protected - set(_VERSION_FILES))
        missing = sorted(set(_VERSION_FILES) - protected)
        raise ValueError(
            "wheel-facing change set is not the four version files; "
            f"extra={extra}, missing={missing}"
        )

    for relative in _VERSION_FILES:
        before = _git(root, "show", f"{released_tag}:{relative}")
        after = (root / relative).read_text(encoding="utf-8").rstrip("\n")
        if before.replace(tagged, development) != after:
            raise ValueError(f"{relative} changes more than {tagged} -> {development}")
    return tagged, development


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--released-tag", required=True)
    parser.add_argument("--branch", required=True)
    args = parser.parse_args()
    try:
        released, development = validate(Path.cwd(), args.released_tag, args.branch)
    except (ValueError, subprocess.CalledProcessError) as error:
        parser.error(str(error))
    print(f"validated mechanical post-release identity: {released} -> {development}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
