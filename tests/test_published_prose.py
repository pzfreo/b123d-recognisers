"""Published runtime prose must make sense outside Draftwright's private history."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
RUNTIME = ROOT / "src" / "b123d_recognisers"
README = ROOT / "README.md"


def _runtime_sources() -> list[Path]:
    return sorted(RUNTIME.glob("*.py"))


def test_runtime_prose_has_no_bare_issue_references() -> None:
    unresolved = {
        path.relative_to(ROOT).as_posix(): sorted(set(re.findall(r"#\d+[a-z]?", text)))
        for path in _runtime_sources()
        if (text := path.read_text(encoding="utf-8")) and re.search(r"#\d+[a-z]?", text)
    }
    assert unresolved == {}


def test_runtime_prose_only_uses_normative_package_adrs() -> None:
    historical = {
        path.relative_to(ROOT).as_posix(): sorted(
            set(re.findall(r"\bADR(?:s)?\s+00(?:0[3-9]|1\d)\b", text))
        )
        for path in _runtime_sources()
        if (text := path.read_text(encoding="utf-8"))
        and re.search(r"\bADR(?:s)?\s+00(?:0[3-9]|1\d)\b", text)
    }
    assert historical == {}


def test_runtime_prose_has_no_consumer_internal_paths() -> None:
    private_paths = {
        "model/declare",
        "model.declare",
        "model/detect.py",
        "sheet_emit",
        "staircase.step",
        "analysis._",
        "recognition/",
        "build_part_model",
        "_analyse",
        "detect._",
        "declare.",
        "analysis.py",
        "Draftwright",
        "draftwright",
    }
    unresolved = {
        path.relative_to(ROOT).as_posix(): sorted(token for token in private_paths if token in text)
        for path in _runtime_sources()
        if (text := path.read_text(encoding="utf-8"))
        and any(token in text for token in private_paths)
    }
    assert unresolved == {}


def test_readme_introduces_imported_brep_recognition_for_cad_consumers() -> None:
    readme = README.read_text(encoding="utf-8")

    assert "import_step" in readme
    assert "boundary-representation (B-Rep)" in readme
    assert "construction history is not available" in readme
    assert "STEP editor" in readme and "topology-editing operation" in readme
    assert "does not mutate the source model" in readme
    assert "build123d solids and imported STEP models" not in readme
