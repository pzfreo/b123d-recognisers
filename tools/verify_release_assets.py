#!/usr/bin/env python3
"""Verify that one wheel and one sdist carry the version named by a release tag."""

from __future__ import annotations

import argparse
import sys
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path

import tomllib


class ReleaseAssetError(ValueError):
    """The release artifacts are incomplete or disagree with their tag."""


def _only(paths: list[Path], kind: str) -> Path:
    if len(paths) != 1:
        raise ReleaseAssetError(f"expected exactly one {kind}, found {len(paths)}")
    return paths[0]


def _wheel_version(path: Path) -> tuple[str, str]:
    with zipfile.ZipFile(path) as archive:
        metadata_names = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise ReleaseAssetError(
                f"{path.name}: expected one wheel METADATA, found {len(metadata_names)}"
            )
        metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
    return metadata["Name"], metadata["Version"]


def _sdist_version(path: Path) -> tuple[str, str]:
    with tarfile.open(path, "r:gz") as archive:
        pyprojects = [
            member
            for member in archive.getmembers()
            if member.name.endswith("/pyproject.toml")
        ]
        if len(pyprojects) != 1:
            raise ReleaseAssetError(
                f"{path.name}: expected one sdist pyproject.toml, found {len(pyprojects)}"
            )
        extracted = archive.extractfile(pyprojects[0])
        if extracted is None:
            raise ReleaseAssetError(f"{path.name}: could not read pyproject.toml")
        project = tomllib.loads(extracted.read().decode("utf-8"))["project"]
    return project["name"], project["version"]


def verify(dist: Path, tag: str) -> str:
    if not tag.startswith("v") or len(tag) == 1:
        raise ReleaseAssetError("release tag must be a non-empty version prefixed with 'v'")
    tag_version = tag[1:]
    wheel = _only(sorted(dist.glob("*.whl")), "wheel")
    sdist = _only(sorted(dist.glob("*.tar.gz")), "sdist")
    wheel_identity = _wheel_version(wheel)
    sdist_identity = _sdist_version(sdist)
    if wheel_identity != sdist_identity:
        raise ReleaseAssetError(
            f"wheel identity {wheel_identity!r} does not match sdist identity {sdist_identity!r}"
        )
    name, artifact_version = wheel_identity
    if name != "b123d-recognisers":
        raise ReleaseAssetError(f"unexpected project name {name!r}")
    if tag_version != artifact_version:
        raise ReleaseAssetError(
            f"tag version {tag_version} does not match artifact version {artifact_version}"
        )
    return artifact_version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args(argv)
    try:
        version = verify(args.dist, args.tag)
    except (OSError, KeyError, ValueError, tarfile.TarError, zipfile.BadZipFile) as error:
        print(f"release asset verification failed: {error}", file=sys.stderr)
        return 1
    print(f"verified b123d-recognisers {version} wheel and sdist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
