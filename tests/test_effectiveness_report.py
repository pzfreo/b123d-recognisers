# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Contract tests for the Epic 0005 corpus-effectiveness evidence boundary."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from build123d import Box, Cylinder, GeomType, export_step

import tools.run_effectiveness_baseline as baseline_runner
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._dispositions import Outcome
from b123d_recognisers.result import _take_inventory
from tools.effectiveness_report import (
    DatasetTruth,
    EffectivenessDataError,
    canonical_json,
    load_mfcadpp_truth,
    load_mfinstseg_truth,
    load_taxonomy,
    score_inventory,
    summarize_rows,
    summarize_runtime,
    validate_report,
)
from tools.run_effectiveness_baseline import (
    _capture_run_authority,
    _display_path,
    _mfcadpp_selection,
    _mfinstseg_selection,
    _verify_run_authority,
    _write_new_report,
)

ROOT = Path(__file__).parents[1]
TAXONOMY = ROOT / "docs" / "benchmarks" / "effectiveness-taxonomy-v1.json"
TAXONOMY_V2 = ROOT / "docs" / "benchmarks" / "effectiveness-taxonomy-v2.json"
TAXONOMY_V3 = ROOT / "docs" / "benchmarks" / "effectiveness-taxonomy-v3.json"
TAXONOMY_V4 = ROOT / "docs" / "benchmarks" / "effectiveness-taxonomy-v4.json"
TAXONOMY_V5 = ROOT / "docs" / "benchmarks" / "effectiveness-taxonomy-v5.json"
TAXONOMY_V6 = ROOT / "docs" / "benchmarks" / "effectiveness-taxonomy-v6.json"
TAXONOMY_V7 = ROOT / "docs" / "benchmarks" / "effectiveness-taxonomy-v7.json"
TAXONOMY_V8 = ROOT / "docs" / "benchmarks" / "effectiveness-taxonomy-v8.json"
TAXONOMY_V9 = ROOT / "docs" / "benchmarks" / "effectiveness-taxonomy-v9.json"
TAXONOMY_V10 = ROOT / "docs" / "benchmarks" / "effectiveness-taxonomy-v10.json"


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


def test_mfcadpp_face_label_pairing_is_stable_across_processes(tmp_path: Path) -> None:
    step = tmp_path / "asymmetric-box.step"
    export_step(Box(7, 11, 13), step)
    next_label = iter(range(6))
    labelled, count = re.subn(
        r"ADVANCED_FACE\('[^']*'",
        lambda _match: f"ADVANCED_FACE('{next(next_label)}'",
        step.read_text(encoding="utf-8"),
    )
    assert count == 6
    step.write_text(labelled, encoding="utf-8")
    script = """
import json
import sys
from build123d import import_step
from tools.effectiveness_report import load_mfcadpp_truth

truth = load_mfcadpp_truth(__import__('pathlib').Path(sys.argv[1]))
part = import_step(truth.step_path)
signature = []
for label, face in zip(truth.semantic, part.faces(), strict=True):
    center = face.center()
    normal = face.normal_at()
    signature.append([
        label,
        round(face.area, 9),
        [round(value, 9) for value in center],
        [round(value, 9) for value in normal],
    ])
print(json.dumps(signature, sort_keys=True))
"""

    outputs = [
        subprocess.run(
            [sys.executable, "-c", script, str(step)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout
        for _ in range(2)
    ]

    assert outputs[0] == outputs[1]


def test_runner_import_does_not_load_production_recognisers() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import tools.run_effectiveness_baseline; "
            "print(any(name == 'b123d_recognisers' or "
            "name.startswith('b123d_recognisers.') for name in sys.modules))",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.stdout == "False\n"


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


def test_mfinstseg_adapter_accepts_a_face_in_no_instance(tmp_path: Path) -> None:
    """The published data leaves every Stock row zero, so face 2 joins no instance.

    Written against the real MFInstSeg release: across the first 300 test-split models the
    ``inst`` matrix is symmetric, reflexive and disjoint on feature faces, and every all-zero
    row carries semantic class 24 (``Stock``, ``incomparable``, no families). Requiring a
    reflexive diagonal on those rows rejected all 9373 selectable models.
    """

    _mfinstseg(tmp_path, inst=[[1, 1, 0], [1, 1, 0], [0, 0, 0]])

    truth = load_mfinstseg_truth(tmp_path, "part")

    assert truth.semantic == (1, 1, 24)
    assert truth.instances == (frozenset({0, 1}),)


def test_mfinstseg_adapter_drops_a_feature_face_left_out_of_every_instance(
    tmp_path: Path,
) -> None:
    """A feature face with no instance row is dropped, not repaired and not rejected.

    Four models in the published test partition do this, twice while a sibling face of the
    same class does carry an instance. Pinned because the affected feature silently never
    reaches ``truth_instances``: face 1 is class 1 here and joins nothing, so only face 0's
    instance survives.
    """

    _mfinstseg(tmp_path, inst=[[1, 0, 0], [0, 0, 0], [0, 0, 1]])

    truth = load_mfinstseg_truth(tmp_path, "part")

    assert truth.semantic == (1, 1, 24)
    assert truth.instances == (frozenset({0}), frozenset({2}))


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


def test_taxonomy_v4_marks_only_rectangular_through_slot_partially_supported() -> None:
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
        "families": ["slots"],
        "name": "Rectangular through slot",
        "status": "partial",
    }
    assert load_taxonomy(TAXONOMY_V4, "mfinstseg") == current


def test_taxonomy_v5_moves_only_horizontal_round_bottom_slot_to_its_family() -> None:
    historical = load_taxonomy(TAXONOMY_V4, "mfcadpp")
    current = load_taxonomy(TAXONOMY_V5, "mfcadpp")

    assert {key: value for key, value in current.items() if key != 19} == {
        key: value for key, value in historical.items() if key != 19
    }
    assert historical[19]["families"] == ["pockets"]
    assert current[19] == {
        "families": ["round-bottom-blind-slots"],
        "name": "Horizontal circular end blind slot",
        "status": "supported",
    }
    assert load_taxonomy(TAXONOMY_V5, "mfinstseg") == current


def test_taxonomy_v6_moves_only_rectangular_blind_slot_to_its_family() -> None:
    historical = load_taxonomy(TAXONOMY_V5, "mfcadpp")
    current = load_taxonomy(TAXONOMY_V6, "mfcadpp")

    assert {key: value for key, value in current.items() if key != 17} == {
        key: value for key, value in historical.items() if key != 17
    }
    assert historical[17]["families"] == ["pockets"]
    assert current[17] == {
        "families": ["rectangular-blind-slots"],
        "name": "Rectangular blind slot",
        "status": "supported",
    }
    assert load_taxonomy(TAXONOMY_V6, "mfinstseg") == current


def test_taxonomy_v7_adds_only_channel_to_rectangular_through_slot() -> None:
    historical = load_taxonomy(TAXONOMY_V6, "mfcadpp")
    current = load_taxonomy(TAXONOMY_V7, "mfcadpp")

    assert {key: value for key, value in current.items() if key != 6} == {
        key: value for key, value in historical.items() if key != 6
    }
    assert historical[6] == {
        "families": ["slots"],
        "name": "Rectangular through slot",
        "status": "partial",
    }
    assert current[6] == {
        "families": ["channels", "slots"],
        "name": "Rectangular through slot",
        "status": "partial",
    }
    assert load_taxonomy(TAXONOMY_V7, "mfinstseg") == current


def test_taxonomy_v8_adds_only_countersink_to_chamfer() -> None:
    historical = load_taxonomy(TAXONOMY_V7, "mfcadpp")
    current = load_taxonomy(TAXONOMY_V8, "mfcadpp")

    assert {key: value for key, value in current.items() if key != 0} == {
        key: value for key, value in historical.items() if key != 0
    }
    assert historical[0] == {
        "families": ["chamfers"],
        "name": "Chamfer",
        "status": "supported",
    }
    assert current[0] == {
        "families": ["chamfers", "countersinks"],
        "name": "Chamfer",
        "status": "supported",
    }
    assert load_taxonomy(TAXONOMY_V8, "mfinstseg") == current


def test_taxonomy_v9_adds_only_blend_to_round() -> None:
    historical = load_taxonomy(TAXONOMY_V8, "mfcadpp")
    current = load_taxonomy(TAXONOMY_V9, "mfcadpp")

    assert {key: value for key, value in current.items() if key != 23} == {
        key: value for key, value in historical.items() if key != 23
    }
    assert historical[23] == {
        "families": ["fillets"],
        "name": "Round",
        "status": "supported",
    }
    assert current[23] == {
        "families": ["blends", "fillets"],
        "name": "Round",
        "status": "supported",
    }
    assert load_taxonomy(TAXONOMY_V9, "mfinstseg") == current


def test_taxonomy_v10_adds_only_oriented_slot_to_rectangular_passage() -> None:
    historical = load_taxonomy(TAXONOMY_V9, "mfcadpp")
    current = load_taxonomy(TAXONOMY_V10, "mfcadpp")

    assert {key: value for key, value in current.items() if key != 3} == {
        key: value for key, value in historical.items() if key != 3
    }
    assert historical[3]["families"] == ["passages"]
    assert current[3]["families"] == ["oriented-slots", "passages"]
    assert load_taxonomy(TAXONOMY_V10, "mfinstseg") == current


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
        "covered_faces": 1,
        "mapped_defining_faces": 1,
        "truth_instances": 1,
        "recalled_instances": 1,
    }
    assert row["taxonomy_mismatch_defining_faces"] == 0
    assert row["no_physical_records"] is False


def test_face_coverage_counts_constituents_without_changing_defining_semantics() -> None:
    part = Box(1, 1, 1)
    faces = tuple(part.faces())
    candidate = SimpleNamespace(family=FamilyId.STEP_LEVELS)
    product = SimpleNamespace(
        context=SimpleNamespace(graph=SimpleNamespace(face=lambda node: faces[node])),
        reconciliation=SimpleNamespace(
            dispositions=(SimpleNamespace(candidate=candidate, outcome=Outcome.ACCEPTED),)
        ),
        evidence=SimpleNamespace(
            defining_of=lambda _candidate: (0,),
            constituent_of=lambda _candidate: (0, 1),
            observations=lambda *_args: (),
        ),
        diagnostics=(),
    )
    truth = DatasetTruth(
        "coverage",
        Path("coverage.step"),
        (1, 1, 1, *(24 for _face in faces[3:])),
        (),
        None,
        "0" * 64,
    )

    row = score_inventory(
        truth,
        part,
        product,
        load_taxonomy(TAXONOMY, "mfcadpp"),
        0.0,
    )
    row["status"] = "evaluated"
    summary = summarize_rows([row], 1, 0)

    assert row["classes"]["1"] == {
        "status": "supported",
        "labelled_faces": 3,
        "matched_defining_faces": 0,
        "covered_faces": 2,
        "mapped_defining_faces": 0,
        "truth_instances": 0,
        "recalled_instances": 0,
    }
    assert summary["classes"]["1"]["face_coverage"] == {
        "numerator": 2,
        "denominator": 3,
        "value": 2 / 3,
    }
    assert summary["classes"]["0"]["face_coverage"] == {
        "numerator": 0,
        "denominator": 0,
        "value": None,
    }


def test_partial_support_preserves_supported_scorer_semantics() -> None:
    part = Box(30, 30, 10) - Cylinder(3, 10)
    faces = tuple(part.faces())
    cylinder_truth = DatasetTruth(
        "through-hole",
        Path("through-hole.step"),
        tuple(1 if face.geom_type is GeomType.CYLINDER else 24 for face in faces),
        (),
        None,
        "0" * 64,
    )

    def scored(status: str, families: list[str], truth: DatasetTruth) -> dict:
        taxonomy = load_taxonomy(TAXONOMY, "mfcadpp")
        taxonomy[1] = {**taxonomy[1], "families": families, "status": status}
        return score_inventory(truth, part, _take_inventory(part), taxonomy, 1.25)

    supported = scored("supported", ["holes"], cylinder_truth)
    partial = scored("partial", ["holes"], cylinder_truth)
    assert {**partial["classes"]["1"], "status": "supported"} == supported["classes"]["1"]
    assert partial["mapped_dataset_class_records"] == supported["mapped_dataset_class_records"]
    assert partial["taxonomy_mismatch_defining_faces"] == 0

    wrong_family_truth = DatasetTruth(
        "through-hole",
        Path("through-hole.step"),
        (1,) * len(faces),
        (),
        None,
        "0" * 64,
    )
    supported_mismatch = scored("supported", ["slots"], wrong_family_truth)
    partial_mismatch = scored("partial", ["slots"], wrong_family_truth)
    assert partial_mismatch["mapped_dataset_class_records"] == supported_mismatch[
        "mapped_dataset_class_records"
    ]
    assert partial_mismatch["classes"]["1"]["matched_defining_faces"] == 0
    assert partial_mismatch["taxonomy_mismatch_defining_faces"] == supported_mismatch[
        "taxonomy_mismatch_defining_faces"
    ]
    assert partial_mismatch["taxonomy_mismatch_defining_faces"] > 0


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


def _report() -> dict[str, Any]:
    return {
        "format": "b123d-recognisers-effectiveness",
        "format_version": 3,
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


def _evaluated_report() -> dict[str, Any]:
    report = _report()
    classes = {
        str(class_id): {
            "status": "supported",
            "labelled_faces": 0,
            "matched_defining_faces": 0,
            "covered_faces": 0,
            "mapped_defining_faces": 0,
            "truth_instances": 0,
            "recalled_instances": 0,
        }
        for class_id in range(25)
    }
    classes["0"] = {
        **classes["0"],
        "labelled_faces": 1,
        "matched_defining_faces": 1,
        "covered_faces": 1,
        "mapped_defining_faces": 1,
    }
    row = {
        "model_id": "a",
        "source_sha256": "0" * 64,
        "seconds": 0.0,
        "physical_records": {},
        "mapped_dataset_class_records": {},
        "no_physical_records": False,
        "taxonomy_mismatch_defining_faces": 0,
        "reconciliation_drops": {},
        "unsupported_diagnostics": {},
        "predicate_observations": {},
        "classes": classes,
        "status": "evaluated",
    }
    report["models"] = [row]
    report["summary"] = summarize_rows([row], 1, 0)
    report["runtime"] = summarize_runtime([row])
    return report


def test_report_validation_and_json_are_deterministic() -> None:
    report = _report()

    validate_report(report)

    assert canonical_json(report) == canonical_json(json.loads(canonical_json(report)))

    validate_report(_evaluated_report())


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"covered_faces": 2}, "denominators are inconsistent"),
        ({"matched_defining_faces": 2}, "denominators are inconsistent"),
        ({"covered_faces": -1}, "counts must be non-negative integers"),
        ({"unexpected": 0}, "invalid fields"),
    ],
)
def test_report_validation_rejects_invalid_class_evidence(
    mutation: dict[str, int], message: str
) -> None:
    report = _evaluated_report()
    class_row = report["models"][0]["classes"]["0"]
    class_row.update(mutation)
    report["summary"] = summarize_rows(report["models"], 1, 0)

    with pytest.raises(EffectivenessDataError, match=message):
        validate_report(report)


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


def test_corpus_run_authority_captures_mapping_and_refuses_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    taxonomy = tmp_path / "taxonomy.json"
    taxonomy.write_bytes(b"first")
    monkeypatch.setattr(baseline_runner, "_git_commit", lambda: "a" * 40)
    monkeypatch.setattr(baseline_runner, "_git_tree_is_clean", lambda _commit: True)
    monkeypatch.setattr(baseline_runner, "_source_digest", lambda: "source")

    authority = _capture_run_authority(taxonomy)

    assert authority.commit == "a" * 40
    assert authority.taxonomy == b"first"
    assert authority.taxonomy_sha256 == hashlib.sha256(b"first").hexdigest()
    _verify_run_authority(authority, taxonomy)

    taxonomy.write_bytes(b"second")
    with pytest.raises(EffectivenessDataError, match="source authority changed"):
        _verify_run_authority(authority, taxonomy)


def test_taxonomy_loader_scores_from_captured_bytes(tmp_path: Path) -> None:
    taxonomy = tmp_path / "taxonomy.json"
    captured = TAXONOMY_V2.read_bytes()
    taxonomy.write_text("not the captured mapping", encoding="utf-8")

    loaded = load_taxonomy(taxonomy, "mfcadpp", contents=captured)

    assert loaded[7]["status"] == "supported"


@pytest.mark.parametrize(("commit", "clean"), [("b" * 40, True), ("a" * 40, False)])
def test_corpus_run_authority_refuses_source_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    commit: str,
    clean: bool,
) -> None:
    taxonomy = tmp_path / "taxonomy.json"
    taxonomy.write_bytes(b"mapping")
    authority = baseline_runner._RunAuthority(
        commit="a" * 40,
        source_sha256="source",
        taxonomy=b"mapping",
        taxonomy_sha256=hashlib.sha256(b"mapping").hexdigest(),
    )
    monkeypatch.setattr(baseline_runner, "_git_commit", lambda: commit)
    monkeypatch.setattr(baseline_runner, "_git_tree_is_clean", lambda _commit: clean)
    monkeypatch.setattr(baseline_runner, "_source_digest", lambda: "source")

    with pytest.raises(EffectivenessDataError, match="source authority changed"):
        _verify_run_authority(authority, taxonomy)


def test_corpus_run_authority_refuses_a_dirty_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    taxonomy = tmp_path / "taxonomy.json"
    taxonomy.write_bytes(b"mapping")
    monkeypatch.setattr(baseline_runner, "_git_tree_is_clean", lambda _commit: False)

    with pytest.raises(EffectivenessDataError, match="package commit misleading"):
        _capture_run_authority(taxonomy)


def test_corpus_run_authority_refuses_a_commit_transition_during_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    taxonomy = tmp_path / "taxonomy.json"
    taxonomy.write_bytes(b"mapping")
    commits = iter(("a" * 40, "b" * 40))
    monkeypatch.setattr(baseline_runner, "_git_commit", lambda: next(commits))
    monkeypatch.setattr(baseline_runner, "_git_tree_is_clean", lambda _commit: True)
    monkeypatch.setattr(baseline_runner, "_source_digest", lambda: "source")

    with pytest.raises(EffectivenessDataError, match="changed while it was captured"):
        _capture_run_authority(taxonomy)


def test_corpus_run_authority_refuses_a_commit_transition_during_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    taxonomy = tmp_path / "taxonomy.json"
    taxonomy.write_bytes(b"mapping")
    authority = baseline_runner._RunAuthority(
        commit="a" * 40,
        source_sha256="source",
        taxonomy=b"mapping",
        taxonomy_sha256=hashlib.sha256(b"mapping").hexdigest(),
    )
    commits = iter(("a" * 40, "b" * 40))
    monkeypatch.setattr(baseline_runner, "_git_commit", lambda: next(commits))
    monkeypatch.setattr(baseline_runner, "_git_tree_is_clean", lambda _commit: True)
    monkeypatch.setattr(baseline_runner, "_source_digest", lambda: "source")

    with pytest.raises(EffectivenessDataError, match="changed during corpus run"):
        _verify_run_authority(authority, taxonomy)


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
