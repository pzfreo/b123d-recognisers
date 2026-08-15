# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from shutil import copytree, ignore_patterns

from b123d_recognisers import __version__

ROOT = Path(__file__).parents[1]


def test_version_is_available() -> None:
    assert __version__ == "0.1.0"


def test_stable_release_notes_record_the_proven_downstream_cutover() -> None:
    notes = (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")

    assert notes.startswith("# Release notes\n\n## 0.1.0\n")
    assert "Draftwright PR #1168" in notes
    assert "d659e7a6" in notes
    assert "no new recognition behaviour" in notes


def test_wheel_contains_runtime_modules_typing_marker_and_licence_files(tmp_path) -> None:
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    wheels = list(tmp_path.glob("*.whl"))
    assert len(wheels) == 1

    with zipfile.ZipFile(wheels[0]) as archive:
        names = set(archive.namelist())

    package_files = {
        path.relative_to(ROOT / "src").as_posix()
        for path in (ROOT / "src" / "b123d_recognisers").glob("*")
        if path.is_file() and (path.suffix == ".py" or path.name == "py.typed")
    }
    assert package_files <= names
    assert any(name.endswith(".dist-info/licenses/LICENSE") for name in names)
    assert any(name.endswith(".dist-info/licenses/NOTICE") for name in names)
    assert any(name.endswith(".dist-info/licenses/THIRD_PARTY_NOTICES.md") for name in names)


def test_sdist_excludes_untracked_workspace_files(tmp_path) -> None:
    checkout = tmp_path / "checkout"
    copytree(
        ROOT,
        checkout,
        ignore=ignore_patterns(".git", ".venv", ".pytest_cache", "__pycache__", "dist"),
    )
    sentinel = checkout / "PRIVATE_BUILD_INPUT.txt"
    sentinel.write_text("must not ship\n", encoding="utf-8")
    output = tmp_path / "dist"

    subprocess.run(
        ["uv", "build", "--sdist", "--out-dir", str(output)],
        cwd=checkout,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    sdist = next(output.glob("*.tar.gz"))
    with tarfile.open(sdist, "r:gz") as archive:
        names = set(archive.getnames())

    assert not any(name.endswith("/PRIVATE_BUILD_INPUT.txt") for name in names)
    assert any(name.endswith("/src/b123d_recognisers/__init__.py") for name in names)
    assert any(name.endswith("/RELEASE_NOTES.md") for name in names)


def test_installed_wheel_imports_without_the_repository_on_sys_path(tmp_path) -> None:
    wheel_dir = tmp_path / "wheel"
    target = tmp_path / "installed"
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(wheel_dir)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    wheel = next(wheel_dir.glob("*.whl"))
    subprocess.run(
        ["uv", "pip", "install", "--no-deps", "--target", str(target), str(wheel)],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            (
                "import sys; "
                f"sys.path.insert(0, {str(target)!r}); "
                "import b123d_recognisers as r; "
                "assert r.__version__; assert r.recognise_holes"
            ),
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.stderr == ""

    consumer = ROOT / "tests" / "typing" / "public_consumer.py"
    environment = os.environ.copy()
    environment["MYPYPATH"] = str(target)
    checked = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--config-file",
            str(ROOT / "tests" / "typing" / "mypy.ini"),
            "--no-incremental",
            str(consumer),
        ],
        cwd=tmp_path,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert "Success: no issues found" in checked.stdout
