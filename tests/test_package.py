# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

import subprocess
import sys
import zipfile
from pathlib import Path

from b123d_recognisers import __version__

ROOT = Path(__file__).parents[1]


def test_version_is_available() -> None:
    assert __version__


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
