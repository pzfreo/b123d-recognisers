# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Contract tests for the Epic 0005 corpus-effectiveness evidence boundary."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from build123d import Box, Cylinder, GeomType

from b123d_recognisers.result import _take_inventory
from tools.effectiveness_report import (
    DatasetTruth,
    EffectivenessDataError,
    canonical_json,
    load_mfcadpp_truth,
    load_mfinstseg_truth,
    load_taxonomy,
    score_inventory,
    validate_report,
)
from tools.run_effectiveness_baseline import (
    _display_path,
    _mfcadpp_selection,
    _mfinstseg_selection,
    _write_new_report,
)

ROOT = Path(__file__).parents[1]
TAXONOMY = ROOT / "docs" / "benchmarks" / "effectiveness-taxonomy-v1.json"
TAXONOMY_V2 = ROOT / "docs" / "benchmarks" / "effectiveness-taxonomy-v2.json"
TAXONOMY_V3 = ROOT / "docs" / "benchmarks" / "effectiveness-taxonomy-v3.json"
TAXONOMY_V4 = ROOT / "docs" / "benchmarks" / "effectiveness-taxonomy-v4.json"


def _mfinstseg(root: Path, *, inst: list[list[int]] | None = None) -> None:
    (root / "steps").mkdir(parents=True)
    (root / "labels").mkdir()
    (root / "steps" / "part.step").write_text("ISO-10303-21;", encoding="ascii")
    labels = {
        "seg": {"0": 1, "1": 1, "2": 24},
        "inst": inst or [[1, 1, 0], [1, 1, 0], [0, 0, 1]],
        "bottom": {"0": 0, "1": 1, "2": 0},
    }
    (root / "labels" / "part.json").write_text(
        json.dumps([["part", labels]]), encoding="utf-8"
    )


def test_mfcadpp_adapter_reads_only_advanced_face_names(tmp_path: Path) -> None:
    step = tmp_path / "42.step"
    step.write_bytes(
        b"#1=ADVANCED_FACE('1',(),$,.T.);\n#2=ADVANCED_FACE('24',(),$,.T.);\n"
    )

    truth = load_mfcadpp_truth(step)

    assert truth.model_id == "42"
    assert truth.semantic == (1, 24)
    assert truth.instances == ()
    assert truth.bottom is None
    assert len(truth.source_sha256) == 64


def test_mfcadpp_adapter_rejects_missing_labels(tmp_path: Path) -> None:
    step = tmp_path / "empty.step"
    step.write_text("ISO-10303-21;", encoding="ascii")

    with pytest.raises(EffectivenessDataError, match="no ADVANCED_FACE labels"):
        load_mfcadpp_truth(step)


def test_mfcadpp_selection_rejects_a_missing_corpus(tmp_path: Path) -> None:
    with pytest.raises(EffectivenessDataError, match=r"no MFCAD\+\+ STEP files"):
        _mfcadpp_selection(tmp_path / "missing")


def test_mfinstseg_adapter_reads_semantic_instances_and_bottom(tmp_path: Path) -> None:
    _mfinstseg(tmp_path)

    truth = load_mfinstseg_truth(tmp_path, "part")

    assert truth.semantic == (1, 1, 24)
    assert truth.instances == (frozenset({0, 1}), frozenset({2}))
    assert truth.bottom == (False, True, False)
    assert len(truth.source_sha256) == 64


@pytest.mark.parametrize(
    ("inst", "message"),
    [
        ([[1, 1, 0], [0, 1, 0], [0, 0, 1]], "symmetric"),
        ([[1, 1, 0], [1, 0, 0], [0, 0, 1]], "equivalence classes"),
        ([[1, 0], [0, 1]], "face keys"),
    ],
)
def test_mfinstseg_adapter_rejects_malformed_instance_evidence(
    tmp_path: Path, inst: list[list[int]], message: str
) -> None:
    _mfinstseg(tmp_path, inst=inst)

    with pytest.raises(EffectivenessDataError, match=message):
        load_mfinstseg_truth(tmp_path, "part")


def test_taxonomy_is_closed_and_shared_without_claiming_stock() -> None:
    mfcadpp = load_taxonomy(TAXONOMY, "mfcadpp")
    mfinstseg = load_taxonomy(TAXONOMY, "mfinstseg")

    assert mfinstseg == mfcadpp
    assert mfcadpp[1] == {
        "families": ["holes"],
        "name": "Through hole",
        "status": "supported",
    }
    assert mfcadpp[9] == {
        "families": ["paired-ramp-steps"],
        "name": "2-sided through step",
        "status": "supported",
    }
    assert mfcadpp[24] == {"families": [], "name": "Stock", "status": "incomparable"}
    manifest = json.loads(
        (ROOT / "src" / "b123d_recognisers" / "capabilities.json").read_text()
    )
    public_families = {family["id"] for family in manifest["families"]}
    assert {family for row in mfcadpp.values() for family in row["families"]} <= public_families


def test_taxonomy_v2_moves_only_circular_blind_step_to_its_physical_family() -> None:
    historical = load_taxonomy(TAXONOMY, "mfcadpp")
    current = load_taxonomy(TAXONOMY_V2, "mfcadpp")

    assert {key: value for key, value in current.items() if key != 21} == {
        key: value for key, value in historical.items() if key != 21
    }
    assert historical[21]["families"] == ["fillets"]
    assert current[21]["families"] == ["circular-blind-steps"]
    assert load_taxonomy(TAXONOMY_V2, "mfinstseg") == current


def test_taxonomy_v3_marks_only_circular_through_slot_unsupported() -> None:
    historical = load_taxonomy(TAXONOMY_V2, "mfcadpp")
    current = load_taxonomy(TAXONOMY_V3, "mfcadpp")

    assert {key: value for key, value in current.items() if key != 7} == {
        key: value for key, value in historical.items() if key != 7
    }
    assert historical[7] == {
        "families": ["slots"],
        "name": "Circular through slot",
        "status": "supported",
    }
    assert current[7] == {
        "families": [],
        "name": "Circular through slot",
        "status": "unsupported",
    }
    assert load_taxonomy(TAXONOMY_V3, "mfinstseg") == current


def test_taxonomy_v4_marks_only_rectangular_through_slot_unsupported() -> None:
    historical = load_taxonomy(TAXONOMY_V3, "mfcadpp")
    current = load_taxonomy(TAXONOMY_V4, "mfcadpp")

    assert {key: value for key, value in current.items() if key != 6} == {
        key: value for key, value in historical.items() if key != 6
    }
    assert historical[6] == {
        "families": ["slots"],
        "name": "Rectangular through slot",
        "status": "supported",
    }
    assert current[6] == {
        "families": [],
        "name": "Rectangular through slot",
        "status": "unsupported",
    }
    assert load_taxonomy(TAXONOMY_V4, "mfinstseg") == current


def test_corpus_selections_are_lexical_unique_and_disclose_mfinstseg_leaks(
    tmp_path: Path,
) -> None:
    mfcad = tmp_path / "mfcad"
    mfcad.mkdir()
    for name in ("10.step", "2.step", "1.step"):
        (mfcad / name).write_text("ADVANCED_FACE('24'", encoding="ascii")
    ids, _loader, extra = _mfcadpp_selection(mfcad)
    assert ids == ["1", "10", "2"]
    assert extra == {"excluded": {}}

    corpus = tmp_path / "mfinst"
    partitions = tmp_path / "partitions"
    partitions.mkdir()
    (partitions / "train.txt").write_text("shared\ntrain\n", encoding="utf-8")
    (partitions / "val.txt").write_text("val\n", encoding="utf-8")
    (partitions / "test.txt").write_text("z\nduplicate\na\nduplicate\nshared\n", encoding="utf-8")

    ids, _loader, extra = _mfinstseg_selection(corpus, partitions)

    assert ids == ["a", "z"]
    assert extra["excluded"] == {
        "duplicate_test_ids": ["duplicate"],
        "cross_split_ids": ["shared"],
    }


def test_one_inventory_scores_records_faces_instances_and_reconciliation() -> None:
    part = Box(30, 30, 10) - Cylinder(3, 10)
    faces = tuple(part.faces())
    semantic = tuple(1 if face.geom_type is GeomType.CYLINDER else 24 for face in faces)
    through_hole_faces = frozenset(
        index for index, label in enumerate(semantic) if label == 1
    )
    truth = DatasetTruth(
        "through-hole",
        Path("through-hole.step"),
        semantic,
        (through_hole_faces, frozenset(set(range(len(faces))) - through_hole_faces)),
        tuple(False for _ in faces),
        "0" * 64,
    )

    row = score_inventory(
        truth,
        part,
        _take_inventory(part),
        load_taxonomy(TAXONOMY, "mfcadpp"),
        1.25,
    )

    assert row["physical_records"]["holes"] == 1
    assert row["classes"]["1"] == {
        "status": "supported",
        "labelled_faces": 1,
        "matched_defining_faces": 1,
        "mapped_defining_faces": 1,
        "truth_instances": 1,
        "recalled_instances": 1,
    }
    assert row["taxonomy_mismatch_defining_faces"] == 0
    assert row["no_physical_records"] is False


def test_scorer_rejects_a_class_outside_the_closed_taxonomy() -> None:
    part = Box(1, 1, 1)
    truth = DatasetTruth(
        "unknown-class",
        Path("unknown-class.step"),
        (25,) * len(part.faces()),
        (),
        None,
        "0" * 64,
    )

    with pytest.raises(EffectivenessDataError, match=r"unknown classes \[25\]"):
        score_inventory(
            truth,
            part,
            _take_inventory(part),
            load_taxonomy(TAXONOMY, "mfcadpp"),
            0.0,
        )


def test_taxonomy_provenance_path_supports_external_files(tmp_path: Path) -> None:
    external = tmp_path / "mapping.json"
    assert _display_path(TAXONOMY) == str(
        Path("docs") / "benchmarks" / "effectiveness-taxonomy-v1.json"
    )
    assert _display_path(external) == str(external.resolve())


def _report() -> dict[str, object]:
    return {
        "format": "b123d-recognisers-effectiveness",
        "format_version": 1,
        "dataset": {"name": "fixture", "version": "1"},
        "package": {"name": "b123d-recognisers", "version": "1", "commit": "abc"},
        "environment": {"python": "3", "build123d": "1", "ocp": "1", "os": "test"},
        "selection": {
            "rule": "fixture",
            "limit": None,
            "selected_ids_sha256": hashlib.sha256(b"a\n").hexdigest(),
            "excluded": {},
        },
        "mapping": {"format_version": 1, "sha256": "0" * 64, "path": "mapping.json"},
        "models": [{"model_id": "a", "status": "invalid", "reason": "fixture"}],
        "summary": {
            "selected": 1,
            "loaded": 0,
            "invalid": 1,
            "evaluated": 0,
            "empty": 0,
            "physical_records": {},
            "mapped_dataset_class_records": {},
            "taxonomy_mismatch_defining_faces": 0,
            "reconciliation_drops": {},
            "unsupported_diagnostics": {},
            "predicate_observations": {},
            "classes": {},
        },
        "runtime": {
            "count": 0,
            "total_seconds": 0.0,
            "min_seconds": None,
            "median_seconds": None,
            "p95_seconds": None,
            "max_seconds": None,
        },
    }


def test_report_validation_and_json_are_deterministic() -> None:
    report = _report()

    validate_report(report)

    assert canonical_json(report) == canonical_json(json.loads(canonical_json(report)))


def test_report_validation_rejects_denominator_drift_and_duplicate_models() -> None:
    report = _report()
    report["summary"] = {
        "selected": 2,
        "loaded": 2,
        "invalid": 1,
        "evaluated": 1,
        "empty": 0,
    }
    with pytest.raises(EffectivenessDataError, match=r"loaded \+ invalid"):
        validate_report(report)

    report = _report()
    report["models"] = [
        {"model_id": "a", "status": "invalid", "reason": "one"},
        {"model_id": "a", "status": "invalid", "reason": "two"},
    ]
    with pytest.raises(EffectivenessDataError, match="unique sorted"):
        validate_report(report)


def test_report_validation_recomputes_selection_summary_and_runtime() -> None:
    report = _report()
    report["selection"]["selected_ids_sha256"] = "0" * 64
    with pytest.raises(EffectivenessDataError, match="selection hash"):
        validate_report(report)

    report = _report()
    report["summary"]["physical_records"] = {"holes": 1}
    with pytest.raises(EffectivenessDataError, match="summary does not match"):
        validate_report(report)

    report = _report()
    report["runtime"]["total_seconds"] = 1.0
    with pytest.raises(EffectivenessDataError, match="runtime does not match"):
        validate_report(report)


def test_report_creation_is_exclusive_and_preserves_existing_bytes(tmp_path: Path) -> None:
    output = tmp_path / "frozen.json"
    _write_new_report(output, "first\n")

    with pytest.raises(EffectivenessDataError, match="refusing to overwrite"):
        _write_new_report(output, "second\n")

    assert output.read_bytes() == b"first\n"


def test_command_refuses_to_write_a_partial_report(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "broken.step").write_text("ADVANCED_FACE('1'", encoding="ascii")
    output = tmp_path / "report.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "run_effectiveness_baseline.py"),
            "mfcadpp",
            str(corpus),
            "--dataset-version",
            "fixture",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 2
    assert "refusing partial report" in completed.stderr
    assert not output.exists()
