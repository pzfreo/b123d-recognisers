"""Run the bounded two-checkout recogniser compatibility check.

The candidate wheel is installed only into a temporary export of the committed Draftwright branch;
neither checkout nor its lockfile is modified.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from email.parser import Parser
from pathlib import Path

PACKAGE_TESTS = (
    "tests/test_capability_manifest.py",
    "tests/test_delivery_protocol.py",
    "tests/test_recogniser_contract.py",
    "tests/test_golden_parity.py",
)
DRAFTWRIGHT_TESTS = (
    "tests/test_recogniser_capabilities.py",
    "tests/test_import_boundaries.py",
)
_DRAFTWRIGHT_PACKAGE_VERSION = re.compile(
    r'^_PACKAGE_VERSION = "(?P<version>[^"]+)"$', re.MULTILINE
)


def _python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _plan(package: Path, draftwright: Path, temporary: Path) -> list[dict[str, object]]:
    dist = temporary / "dist"
    exported = temporary / "draftwright"
    archive = temporary / "draftwright.tar"
    python = _python(exported / ".venv")
    wheel = dist / "<candidate-wheel>"
    return [
        {
            "name": "package-contract",
            "cwd": str(package),
            "command": [
                "uv",
                "run",
                "pytest",
                "-q",
                "-o",
                "addopts=",
                *PACKAGE_TESTS,
            ],
        },
        {
            "name": "build-candidate-wheel",
            "cwd": str(package),
            "command": ["uv", "build", "--wheel", "--out-dir", str(dist)],
        },
        {
            "name": "prepare-draftwright",
            "cwd": str(draftwright),
            "command": ["git", "archive", "--format=tar", "-o", str(archive), "HEAD"],
            "archive": str(archive),
            "extract_to": str(exported),
        },
        {
            "name": "install-candidate-wheel",
            "cwd": str(exported),
            "command": [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--reinstall",
                "--no-deps",
                str(wheel),
            ],
        },
        {
            "name": "draftwright-contract",
            "cwd": str(exported),
            "command": [
                str(python),
                "-m",
                "pytest",
                "-q",
                *DRAFTWRIGHT_TESTS,
                "-k",
                "not installed_released_package_contract",
            ],
        },
    ]


def _run(command: list[str], cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def _candidate_wheel(dist: Path) -> Path:
    wheels = sorted(dist.glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"expected one candidate wheel, found {len(wheels)}")
    return wheels[0]


def _wheel_version(wheel: Path) -> str:
    with zipfile.ZipFile(wheel) as archive:
        metadata = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise SystemExit(f"expected one wheel METADATA file, found {len(metadata)}")
        message = Parser().parsestr(archive.read(metadata[0]).decode("utf-8"))
    if message.get("Name") != "b123d-recognisers" or not (version := message.get("Version")):
        raise SystemExit("candidate wheel has unexpected or missing project metadata")
    return version


def _adapt_exported_draftwright_version(export: Path, version: str) -> None:
    """Adapt only the disposable consumer export to the exact candidate under test."""
    contract = export / "src" / "draftwright" / "recogniser_contract.py"
    source = contract.read_text(encoding="utf-8")
    updated, count = _DRAFTWRIGHT_PACKAGE_VERSION.subn(
        f'_PACKAGE_VERSION = "{version}"', source
    )
    if count != 1:
        raise SystemExit("expected one Draftwright package-version declaration")
    contract.write_text(updated, encoding="utf-8")


def _validate_checkout(path: Path, project_name: str) -> None:
    pyproject = path / "pyproject.toml"
    if not pyproject.is_file() or f'name = "{project_name}"' not in pyproject.read_text(
        encoding="utf-8"
    ):
        raise SystemExit(f"{path} is not a {project_name} checkout")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draftwright", type=Path, required=True)
    parser.add_argument("--package", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--plan", action="store_true", help="print the command plan as JSON")
    args = parser.parse_args()
    package = args.package.resolve()
    draftwright = args.draftwright.resolve()
    if args.plan:
        print(json.dumps(_plan(package, draftwright, Path("<temporary>")), indent=2))
        return 0
    _validate_checkout(package, "b123d-recognisers")
    _validate_checkout(draftwright, "draftwright")
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=draftwright,
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout:
        raise SystemExit("Draftwright checkout must be committed before it can be exported")

    with tempfile.TemporaryDirectory(prefix="b123d-downstream-") as directory:
        temporary = Path(directory)
        plan = _plan(package, draftwright, temporary)
        for step in plan:
            name = str(step["name"])
            command = [str(value) for value in step["command"]]
            cwd = Path(str(step["cwd"]))
            print(f"==> {name}", flush=True)
            if name == "prepare-draftwright":
                _run(command, cwd)
                export = Path(str(step["extract_to"]))
                export.mkdir()
                shutil.unpack_archive(str(step["archive"]), export, format="tar")
                wheel = _candidate_wheel(temporary / "dist")
                _adapt_exported_draftwright_version(export, _wheel_version(wheel))
                _run(["uv", "sync", "--locked"], export)
            elif name == "install-candidate-wheel":
                command[-1] = str(_candidate_wheel(temporary / "dist"))
                _run(command, cwd)
            else:
                _run(command, cwd)
        print("candidate package and Draftwright contract are compatible")
    return 0


if __name__ == "__main__":
    sys.exit(main())
