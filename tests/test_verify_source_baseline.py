import json
import subprocess
import sys
from pathlib import Path

import pytest

VERIFY = Path(__file__).parents[1] / "tools" / "verify_source_baseline.py"


def _git(checkout: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(checkout), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    checkout = tmp_path / "draftwright"
    checkout.mkdir()
    _git(checkout, "init")
    _git(checkout, "config", "user.name", "Test Author")
    _git(checkout, "config", "user.email", "test@example.com")
    _git(checkout, "remote", "add", "origin", "git@github.com:pzfreo/draftwright.git")
    source = checkout / "src" / "draftwright" / "recognition"
    source.mkdir(parents=True)
    (source / "holes.py").write_text("baseline\n", encoding="utf-8")
    _git(checkout, "add", ".")
    _git(checkout, "commit", "-m", "baseline")

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "source": {
                    "repository": "https://github.com/pzfreo/draftwright.git",
                    "commit": _git(checkout, "rev-parse", "HEAD"),
                },
                "sources": [
                    {
                        "path": "src/draftwright/recognition/holes.py",
                        "blob": _git(
                            checkout,
                            "rev-parse",
                            "HEAD:src/draftwright/recognition/holes.py",
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return checkout, manifest


def _verify(checkout: Path, manifest: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VERIFY),
            "--draftwright",
            str(checkout),
            "--manifest",
            str(manifest),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_verifier_accepts_exact_clean_checkout_and_ssh_remote(tmp_path):
    checkout, manifest = _fixture(tmp_path)

    result = _verify(checkout, manifest)

    assert result.returncode == 0
    assert "matches the pinned clean source baseline" in result.stdout


@pytest.mark.parametrize("drift", ["wrong_commit", "dirty", "wrong_remote", "wrong_blob"])
def test_verifier_rejects_baseline_drift(tmp_path, drift):
    checkout, manifest_path = _fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if drift == "wrong_commit":
        manifest["source"]["commit"] = "0" * 40
    elif drift == "dirty":
        (checkout / "untracked.txt").write_text("drift\n", encoding="utf-8")
    elif drift == "wrong_remote":
        _git(checkout, "remote", "set-url", "origin", "https://github.com/example/other.git")
    else:
        manifest["sources"][0]["blob"] = "0" * 40
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = _verify(checkout, manifest_path)

    assert result.returncode == 1
    assert "baseline verification failed" in result.stderr
