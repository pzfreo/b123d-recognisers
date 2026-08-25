# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""MFTRCAD stays external; these fixtures pin its ingestion contract, not its outcomes."""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path, PureWindowsPath
from typing import get_args

import pytest
from build123d import Box, export_step

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))

import mftrcad_audit as audit_module  # noqa: E402
from mftrcad_audit import (  # noqa: E402
    DATASET_REF,
    DATASET_VERSION,
    DEVELOPMENT_BUCKETS,
    F5_BOSSES_H1,
    F5_CHANNELS_H1,
    F5_COUNTERSINKS_H1,
    F5_DOUBLE_D_BORES_H1,
    F5_FILLETS_H1,
    F5_FLATS_H1,
    F5_HOLES_H1,
    F5_PADS_H1,
    F5_PLATES_H1,
    F5_POLYGONAL_BOSSES_H1,
    FEATURE_LABELS,
    HOLDOUT_BUCKETS,
    NAMED_ALLOCATIONS,
    PACKAGE_FAMILIES_BY_LABEL,
    SELECTIONS,
    Selection,
    audit,
    check_compact_baseline,
    compact_baseline,
    discover_models,
    selection_bucket,
    selection_of,
)

ROOT = Path(__file__).parents[1]
DEFAULT_MODEL_ID = next(
    f"development-{at}"
    for at in range(10_000)
    if selection_of(f"development-{at}") == "development"
)


def _dataset(tmp_path: Path, *, model_id: str = DEFAULT_MODEL_ID) -> Path:
    root = tmp_path / "mftrcad"
    steps = root / "steps"
    labels = root / "labels"
    steps.mkdir(parents=True, exist_ok=True)
    labels.mkdir(exist_ok=True)

    part = Box(10, 8, 6)
    export_step(part, steps / f"{model_id}_result.step")
    count = len(part.faces())
    cls = {str(at): 24 for at in range(count)}
    cls["0"] = 14
    cls["1"] = 0
    (labels / f"{model_id}_result.json").write_text(
        json.dumps(
            {
                "cls": cls,
                "seg": [[0], [1], []],
                "bottom": {str(at): 0 for at in range(count)},
            }
        ),
        encoding="utf-8",
    )
    (labels / f"{model_id}_result_rel.json").write_text(
        json.dumps({"relation": [["intersecting", [0, 1]]]}),
        encoding="utf-8",
    )
    return root


def test_selection_is_outcome_independent_disjoint_and_stable() -> None:
    assert set(get_args(Selection)) == SELECTIONS
    assert DEVELOPMENT_BUCKETS.isdisjoint(HOLDOUT_BUCKETS)
    assert selection_bucket("20240116_231044_0") == 113
    assert selection_of("20240116_231044_0") == "unselected"

    # This exercises both selected arms without reading a label or STEP file. A selection
    # rule that accidentally hashed annotation content could not have this API.
    selected = {
        model_id: selection_of(model_id)
        for at in range(10_000)
        if selection_of(model_id := f"model-{at}") != "unselected"
    }
    assert {value for value in selected.values()} == {
        "development",
        "holdout",
        "f5_fillets_h1",
        "f5_flats_h1",
        "f5_countersinks_h1",
        "f5_bosses_h1",
        "f5_double_d_bores_h1",
        "f5_polygonal_bosses_h1",
        "f5_pads_h1",
        "f5_holes_h1",
        "f5_channels_h1",
        "f5_plates_h1",
    }
    assert not (
        {name for name, value in selected.items() if value == "development"}
        & {name for name, value in selected.items() if value == "holdout"}
    )


def test_taxonomy_mapping_is_total_and_marks_the_unsupported_group() -> None:
    assert set(PACKAGE_FAMILIES_BY_LABEL) == set(FEATURE_LABELS)
    assert PACKAGE_FAMILIES_BY_LABEL[8] == ()
    assert PACKAGE_FAMILIES_BY_LABEL[9] == ()
    assert PACKAGE_FAMILIES_BY_LABEL[10] == ()
    assert PACKAGE_FAMILIES_BY_LABEL[14] == ("pockets", "prismatic_pockets")
    assert all(PACKAGE_FAMILIES_BY_LABEL[label] == () for label in (24, 25, 26))


def test_checked_in_selection_and_baseline_are_versioned_and_sealed() -> None:
    selection = json.loads(
        (ROOT / "docs/corpora/mftrcad-selection.json").read_text(encoding="utf-8")
    )
    baseline = json.loads(
        (ROOT / "docs/corpora/mftrcad-development-baseline.json").read_text(encoding="utf-8")
    )

    assert selection["dataset"]["ref"] == baseline["dataset_ref"] == DATASET_REF
    assert selection["dataset"]["version"] == baseline["dataset_version"] == DATASET_VERSION
    assert selection["selection"]["development_buckets"] == sorted(DEVELOPMENT_BUCKETS)
    assert selection["selection"]["holdout_buckets"] == sorted(HOLDOUT_BUCKETS)
    assert selection["selection"]["named_allocations"] == {
        F5_FILLETS_H1: {
            "buckets": sorted(NAMED_ALLOCATIONS[F5_FILLETS_H1]),
            "status": "consumed",
        },
        F5_FLATS_H1: {
            "buckets": sorted(NAMED_ALLOCATIONS[F5_FLATS_H1]),
            "status": "consumed",
        },
        F5_COUNTERSINKS_H1: {
            "buckets": sorted(NAMED_ALLOCATIONS[F5_COUNTERSINKS_H1]),
            "status": "consumed",
        },
        F5_BOSSES_H1: {
            "buckets": sorted(NAMED_ALLOCATIONS[F5_BOSSES_H1]),
            "status": "consumed",
        },
        F5_DOUBLE_D_BORES_H1: {
            "buckets": sorted(NAMED_ALLOCATIONS[F5_DOUBLE_D_BORES_H1]),
            "status": "consumed",
        },
        F5_POLYGONAL_BOSSES_H1: {
            "buckets": sorted(NAMED_ALLOCATIONS[F5_POLYGONAL_BOSSES_H1]),
            "status": "consumed",
        },
        F5_PADS_H1: {
            "buckets": sorted(NAMED_ALLOCATIONS[F5_PADS_H1]),
            "status": "consumed",
        },
        F5_HOLES_H1: {
            "buckets": sorted(NAMED_ALLOCATIONS[F5_HOLES_H1]),
            "status": "consumed",
        },
        F5_CHANNELS_H1: {
            "buckets": sorted(NAMED_ALLOCATIONS[F5_CHANNELS_H1]),
            "status": "sealed_unrevealed",
        },
        F5_PLATES_H1: {
            "buckets": sorted(NAMED_ALLOCATIONS[F5_PLATES_H1]),
            "status": "sealed_unrevealed",
        },
    }
    partition = DEVELOPMENT_BUCKETS | HOLDOUT_BUCKETS | set().union(*NAMED_ALLOCATIONS.values())
    assert len(partition) == 30
    assert partition.isdisjoint(set(range(30, 1000)))
    assert partition | set(range(30, 1000)) == set(range(1000))
    assert selection["selection"]["unselected_bucket_ranges"] == [[30, 999]]
    assert baseline["archive_inventory"] == {
        "selected_step_entries": 301,
        "complete_annotation_triples": 300,
        "incomplete_model_ids": ["20240125_003844_9903"],
    }
    assert baseline["selected_artifacts"] == {
        "files": 901,
        "sha256": "5383b0135da4705ffea3f27a27c30c090325ffa44645372448e2ef554ab22e83",
        "digest_contract": "sha256(relative-path + NUL + bytes + NUL), sorted by path",
    }
    assert baseline["holdout"] == {
        "membership_count_inspected": False,
        "models_opened": 0,
        "outcomes_inspected": False,
    }


def test_holdout_requires_an_explicit_post_review_reveal(tmp_path: Path) -> None:
    model_id = next(
        f"holdout-{at}" for at in range(10_000) if selection_of(f"holdout-{at}") == "holdout"
    )
    root = _dataset(tmp_path, model_id=model_id)

    with pytest.raises(ValueError, match="requires only its explicit holdout authority"):
        audit(root, selection="holdout", annotations_only=True)
    with pytest.raises(ValueError, match="requires only its explicit holdout authority"):
        discover_models(root, selection="holdout")
    assert (
        audit(
            root,
            selection="holdout",
            annotations_only=True,
            allow_holdout=True,
        )["summary"]["models"]
        == 1
    )


def test_all_selection_cannot_bypass_the_holdout_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _dataset(tmp_path)
    opened: list[str] = []
    monkeypatch.setattr(
        audit_module,
        "audit_model",
        lambda files, **kwargs: opened.append(files.model_id),
    )

    with pytest.raises(ValueError, match="selection 'all' is closed while named allocations exist"):
        audit(root, selection="all", annotations_only=True)
    assert opened == []


@pytest.mark.parametrize(
    ("token", "policy_id", "bucket", "status"),
    [
        ("f5_flats_h1", F5_FLATS_H1, 20, "consumed"),
        ("f5_fillets_h1", F5_FILLETS_H1, 21, "consumed"),
        ("f5_countersinks_h1", F5_COUNTERSINKS_H1, 22, "consumed"),
        ("f5_bosses_h1", F5_BOSSES_H1, 23, "consumed"),
        ("f5_double_d_bores_h1", F5_DOUBLE_D_BORES_H1, 24, "consumed"),
        (
            "f5_polygonal_bosses_h1",
            F5_POLYGONAL_BOSSES_H1,
            25,
            "consumed",
        ),
        ("f5_pads_h1", F5_PADS_H1, 26, "consumed"),
        ("f5_holes_h1", F5_HOLES_H1, 27, "consumed"),
        ("f5_channels_h1", F5_CHANNELS_H1, 28, "sealed_unrevealed"),
        ("f5_plates_h1", F5_PLATES_H1, 29, "sealed_unrevealed"),
    ],
)
def test_named_allocation_requires_exact_nontransferable_authority(
    tmp_path: Path, token: str, policy_id: str, bucket: int, status: str
) -> None:
    model_id = next(
        f"{token}-{at}" for at in range(10_000) if selection_of(f"{token}-{at}") == token
    )
    root = _dataset(tmp_path, model_id=model_id)

    with pytest.raises(ValueError, match=f"requires exact acknowledgement '{policy_id}'"):
        audit(root, selection=token, annotations_only=True)
    with pytest.raises(ValueError, match=f"requires exact acknowledgement '{policy_id}'"):
        discover_models(root, selection=token, allow_holdout=True)
    with pytest.raises(ValueError, match="does not accept reveal authority"):
        audit(
            root,
            selection="development",
            annotations_only=True,
            reveal_allocations=frozenset({policy_id}),
        )

    report = audit(
        root,
        selection=token,
        annotations_only=True,
        reveal_allocations=frozenset({policy_id}),
    )
    allocation = report["sealed_allocation"]
    assert allocation["id"] == policy_id
    assert allocation["buckets"] == [bucket]
    assert allocation["policy_status"] == status
    assert allocation["selection_policy_schema_version"] == 1
    assert allocation["selection_namespace"] == audit_module.SELECTION_NAMESPACE
    assert allocation["selection_modulus"] == audit_module.SELECTION_MODULUS
    assert len(allocation["selection_policy_sha256"]) == 64


@pytest.mark.parametrize(
    ("token", "policy_id", "wrong_policy_id"),
    [
        ("f5_fillets_h1", F5_FILLETS_H1, F5_FLATS_H1),
        ("f5_countersinks_h1", F5_COUNTERSINKS_H1, F5_FILLETS_H1),
        ("f5_bosses_h1", F5_BOSSES_H1, F5_COUNTERSINKS_H1),
        ("f5_double_d_bores_h1", F5_DOUBLE_D_BORES_H1, F5_BOSSES_H1),
        (
            "f5_polygonal_bosses_h1",
            F5_POLYGONAL_BOSSES_H1,
            F5_DOUBLE_D_BORES_H1,
        ),
        ("f5_pads_h1", F5_PADS_H1, F5_POLYGONAL_BOSSES_H1),
        ("f5_holes_h1", F5_HOLES_H1, F5_PADS_H1),
        ("f5_channels_h1", F5_CHANNELS_H1, F5_HOLES_H1),
        ("f5_plates_h1", F5_PLATES_H1, F5_CHANNELS_H1),
    ],
)
def test_named_allocation_requires_its_own_exact_authority(
    tmp_path: Path, token: str, policy_id: str, wrong_policy_id: str
) -> None:
    model_id = next(
        f"{token}-{at}" for at in range(10_000) if selection_of(f"{token}-{at}") == token
    )
    root = _dataset(tmp_path, model_id=model_id)
    for authority in (
        frozenset(),
        frozenset({wrong_policy_id}),
        frozenset({wrong_policy_id, policy_id}),
    ):
        with pytest.raises(ValueError, match=f"requires exact acknowledgement '{policy_id}'"):
            audit(
                root,
                selection=token,
                annotations_only=True,
                reveal_allocations=authority,
            )


@pytest.mark.parametrize(
    "token",
    [
        "f5_flats_h1",
        "f5_fillets_h1",
        "f5_countersinks_h1",
        "f5_bosses_h1",
        "f5_double_d_bores_h1",
        "f5_polygonal_bosses_h1",
        "f5_pads_h1",
        "f5_holes_h1",
        "f5_channels_h1",
        "f5_plates_h1",
    ],
)
def test_named_allocation_refuses_before_touching_the_root(tmp_path: Path, token: str) -> None:
    missing = tmp_path / "must-not-be-read"
    with pytest.raises(ValueError, match="requires exact acknowledgement"):
        audit(missing, selection=token, annotations_only=True)
    with pytest.raises(ValueError, match="requires exact acknowledgement"):
        discover_models(missing, selection=token)
    with pytest.raises(ValueError, match="requires exact acknowledgement"):
        audit_module._discover(
            missing,
            selection=token,
            record_invalid=False,
        )


@pytest.mark.parametrize(
    "token",
    [
        "f5_flats_h1",
        "f5_fillets_h1",
        "f5_countersinks_h1",
        "f5_bosses_h1",
        "f5_double_d_bores_h1",
        "f5_polygonal_bosses_h1",
        "f5_pads_h1",
        "f5_holes_h1",
        "f5_channels_h1",
        "f5_plates_h1",
    ],
)
def test_cli_named_allocation_refuses_before_touching_the_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mftrcad_audit.py",
            str(tmp_path / "must-not-be-read"),
            "--selection",
            token,
        ],
    )
    with pytest.raises(ValueError, match="requires exact acknowledgement"):
        audit_module.main()


def test_unknown_allocation_acknowledgement_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown sealed allocation acknowledgement"):
        audit(
            tmp_path / "must-not-be-read",
            reveal_allocations=frozenset({"F5-UNKNOWN-H1"}),
        )


@pytest.mark.parametrize("entry", ["_discover", "discover_models", "audit"])
def test_unknown_selection_fails_before_touching_the_root(tmp_path: Path, entry: str) -> None:
    root = tmp_path / "must-not-be-read"
    call = getattr(audit_module, entry)
    kwargs = {"selection": "unknown"}
    if entry == "_discover":
        kwargs["record_invalid"] = False
    with pytest.raises(ValueError, match="unknown selection 'unknown'"):
        call(root, **kwargs)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda policy: policy.update(schema_version=2), "schema version 1"),
        (
            lambda policy: policy["selection"].update(namespace="wrong"),
            "namespace differs",
        ),
        (
            lambda policy: policy["selection"]["named_allocations"].update(
                {"F5-EXTRA-H1": {"buckets": [21], "status": "sealed_unrevealed"}}
            ),
            "named allocations differ",
        ),
        (
            lambda policy: policy["selection"]["named_allocations"][F5_FLATS_H1].update(
                status="unknown"
            ),
            "named allocations differ",
        ),
        (
            lambda policy: policy["selection"].update(unselected_bucket_ranges=[[21, 999]]),
            "unselected complement differs",
        ),
    ],
)
def test_selection_policy_mutations_fail_closed(mutate, message: str) -> None:
    policy = json.loads((ROOT / "docs/corpora/mftrcad-selection.json").read_text(encoding="utf-8"))
    changed = deepcopy(policy)
    mutate(changed)
    with pytest.raises(ValueError, match=message):
        audit_module._validate_selection_policy(changed)


@pytest.mark.parametrize(
    "specs",
    [
        (
            audit_module.AllocationSpec(
                "F5-FLATS-H1", "f5_flats_h1", frozenset({20}), "sealed_unrevealed"
            ),
            audit_module.AllocationSpec(
                "F5-FLATS-H1", "f5_other_h1", frozenset({21}), "sealed_unrevealed"
            ),
        ),
        (
            audit_module.AllocationSpec("F5-FLATS-H1", "f5_flats_h1", frozenset({20}), "consumed"),
            audit_module.AllocationSpec(
                "F5-OTHER-H1", "f5_other_h1", frozenset({20}), "sealed_unrevealed"
            ),
        ),
        (
            audit_module.AllocationSpec(
                "F5-OTHER-H1", "f5_other_h1", frozenset({10}), "sealed_unrevealed"
            ),
        ),
        (
            audit_module.AllocationSpec(
                "F5-FLATS-H1", "f5_flats_h1", frozenset({20}), "sealed_unrevealed"
            ),
            audit_module.AllocationSpec(
                "F5-OTHER-H1", "f5_flats_h1", frozenset({21}), "sealed_unrevealed"
            ),
        ),
        (
            audit_module.AllocationSpec(
                "F5-FLATS-H1", "F5-FLATS-H1", frozenset({20}), "sealed_unrevealed"
            ),
        ),
    ],
)
def test_allocation_roster_refuses_duplicate_or_noncanonical_mappings(specs) -> None:
    with pytest.raises(ValueError, match="unique|canonical|disjoint"):
        audit_module._validate_allocation_specs(specs)


@pytest.mark.parametrize(
    "named",
    [
        "f5_flats_h1",
        "f5_fillets_h1",
        "f5_countersinks_h1",
        "f5_bosses_h1",
        "f5_double_d_bores_h1",
        "f5_polygonal_bosses_h1",
        "f5_pads_h1",
        "f5_holes_h1",
        "f5_channels_h1",
        "f5_plates_h1",
    ],
)
def test_unselected_excludes_a_named_allocation(tmp_path: Path, named: str) -> None:
    sealed = next(
        f"sealed-{named}-{at}"
        for at in range(10_000)
        if selection_of(f"sealed-{named}-{at}") == named
    )
    ordinary = next(
        f"ordinary-{at}" for at in range(10_000) if selection_of(f"ordinary-{at}") == "unselected"
    )
    root = _dataset(tmp_path, model_id=sealed)
    _dataset(tmp_path, model_id=ordinary)
    models = discover_models(root, selection="unselected")
    assert [model.model_id for model in models] == [ordinary]


def test_annotation_audit_is_deterministic_and_counts_instances_and_relations(
    tmp_path: Path,
) -> None:
    root = _dataset(tmp_path)
    first = audit(root, annotations_only=True)
    second = audit(root, annotations_only=True)
    assert first == second

    summary = first["summary"]
    assert summary["models"] == 1
    assert summary["faces"] == 6
    assert summary["present_instances"] == 2
    assert summary["empty_instances"] == 1
    assert summary["instance_labels"] == {"0": 1, "14": 1}
    assert summary["relationship_groups_by_type"] == {"intersecting": 1}
    assert summary["relationship_pairs_by_type"] == {"intersecting": 1}


def test_full_audit_proves_step_face_identity_and_uses_accepted_inventory(
    tmp_path: Path,
) -> None:
    result = audit(_dataset(tmp_path), annotations_only=False)
    recognition = result["summary"]["recognition"]
    assert "physical_proposals_by_family" in recognition
    assert "accepted_candidates_by_family" in recognition
    assert "dispositions_by_outcome_and_reason" in recognition
    assert recognition["taxonomy_alignment_diagnostic"]["policy"] == (
        "comparison only; never used for acceptance or reconciliation"
    )


def test_incomplete_model_is_refused(tmp_path: Path) -> None:
    root = _dataset(tmp_path)
    next((root / "labels").glob("*_result_rel.json")).unlink()
    with pytest.raises(ValueError, match="is incomplete; missing labels/"):
        discover_models(root)


def test_selected_incomplete_model_is_recorded_but_unselected_one_cannot_block(
    tmp_path: Path,
) -> None:
    root = _dataset(tmp_path)
    selected_relation = root / "labels" / f"{DEFAULT_MODEL_ID}_result_rel.json"
    selected_relation.unlink()
    result = audit(root, annotations_only=True, record_invalid=True)
    assert result["summary"]["models"] == 0
    assert result["summary"]["invalid_models"] == 1
    assert result["invalid"][0]["model_id"] == DEFAULT_MODEL_ID
    assert "missing labels/" in result["invalid"][0]["error"]

    unselected_id = next(
        f"unselected-{at}"
        for at in range(10_000)
        if selection_of(f"unselected-{at}") == "unselected"
    )
    _dataset(tmp_path, model_id=unselected_id)
    (root / "labels" / f"{unselected_id}_result_rel.json").unlink()
    _dataset(tmp_path, model_id=DEFAULT_MODEL_ID)
    result = audit(root, annotations_only=True)
    assert result["summary"]["models"] == 1
    assert result["summary"]["invalid_models"] == 0


def test_selected_orphan_annotation_is_recorded(tmp_path: Path) -> None:
    root = _dataset(tmp_path)
    (root / "steps" / f"{DEFAULT_MODEL_ID}_result.step").unlink()
    result = audit(root, annotations_only=True, record_invalid=True)
    assert result["summary"]["models"] == 0
    assert result["invalid"][0]["model_id"] == DEFAULT_MODEL_ID
    assert "missing steps/" in result["invalid"][0]["error"]


def test_noncontiguous_face_ids_are_refused(tmp_path: Path) -> None:
    root = _dataset(tmp_path)
    label_path = next((root / "labels").glob("*_result.json"))
    label = json.loads(label_path.read_text(encoding="utf-8"))
    label["cls"]["7"] = label["cls"].pop("5")
    label_path.write_text(json.dumps(label), encoding="utf-8")
    with pytest.raises(ValueError, match="contiguous and zero-based"):
        audit(root, annotations_only=True)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda label: label["cls"].update({"01": 24}), "canonical decimal"),
        (lambda label: label["cls"].update({"0": True}), "exact integers"),
        (lambda label: label["seg"].append([True]), "integer face ids"),
        (lambda label: label["bottom"].pop("0"), "cover exactly"),
        (lambda label: label["bottom"].update({"0": True}), "values must be 0 or 1"),
    ],
)
def test_noncanonical_annotation_scalars_fail_closed(tmp_path: Path, mutate, message: str) -> None:
    root = _dataset(tmp_path)
    label_path = root / "labels" / f"{DEFAULT_MODEL_ID}_result.json"
    label = json.loads(label_path.read_text(encoding="utf-8"))
    mutate(label)
    label_path.write_text(json.dumps(label), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        audit(root, annotations_only=True)


def test_unknown_relation_and_foreign_instance_are_refused(tmp_path: Path) -> None:
    root = _dataset(tmp_path)
    relation_path = next((root / "labels").glob("*_result_rel.json"))
    relation_path.write_text(json.dumps({"relation": [["touches", [0, 9]]]}), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown kind 'touches'"):
        audit(root, annotations_only=True)


def test_invalid_model_can_be_recorded_without_becoming_evidence(tmp_path: Path) -> None:
    root = _dataset(tmp_path)
    relation_path = next((root / "labels").glob("*_result_rel.json"))
    relation_path.write_text(json.dumps({"relation": [["intersecting", [0, 0]]]}), encoding="utf-8")

    result = audit(root, annotations_only=True, record_invalid=True)
    assert result["summary"]["models"] == 0
    assert result["summary"]["invalid_models"] == 1
    assert result["invalid"] == [
        {
            "model_id": DEFAULT_MODEL_ID,
            "error": f"<root>/labels/{DEFAULT_MODEL_ID}_result_rel.json: "
            "relation[0] repeats an instance id",
        }
    ]


@pytest.mark.parametrize(
    "error",
    [KeyError("scanner defect"), ValueError("scanner defect"), RuntimeError("scanner defect")],
)
def test_record_invalid_does_not_hide_scanner_programming_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    root = _dataset(tmp_path)
    monkeypatch.setattr(
        audit_module,
        "audit_model",
        lambda *args, **kwargs: (_ for _ in ()).throw(error),
    )
    with pytest.raises(type(error), match="scanner defect"):
        audit(root, annotations_only=True, record_invalid=True)


def test_record_invalid_does_not_relabel_annotation_programming_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _dataset(tmp_path)
    monkeypatch.setattr(
        audit_module,
        "_annotation",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("parser invariant failed")),
    )
    with pytest.raises(ValueError, match="parser invariant failed"):
        audit(root, annotations_only=True, record_invalid=True)


def test_record_invalid_retains_non_utf8_annotation_as_input_error(tmp_path: Path) -> None:
    root = _dataset(tmp_path)
    label_path = root / "labels" / f"{DEFAULT_MODEL_ID}_result.json"
    label_path.write_bytes(b"\xff")

    result = audit(root, annotations_only=True, record_invalid=True)

    assert result["summary"]["models"] == 0
    assert result["summary"]["invalid_models"] == 1
    assert result["invalid"] == [
        {
            "model_id": DEFAULT_MODEL_ID,
            "error": f"<root>/labels/{DEFAULT_MODEL_ID}_result.json: annotation is not valid UTF-8",
        }
    ]


@pytest.mark.parametrize("error_type", [ValueError, RuntimeError])
def test_record_invalid_does_not_hide_recognition_lifecycle_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception],
) -> None:
    root = _dataset(tmp_path)
    monkeypatch.setattr(
        audit_module,
        "_recognition",
        lambda *args, **kwargs: (_ for _ in ()).throw(error_type("lifecycle defect")),
    )
    with pytest.raises(error_type, match="lifecycle defect"):
        audit(root, annotations_only=False, record_invalid=True)


def test_duplicate_relationship_group_is_refused(tmp_path: Path) -> None:
    root = _dataset(tmp_path)
    relation_path = root / "labels" / f"{DEFAULT_MODEL_ID}_result_rel.json"
    relation_path.write_text(
        json.dumps(
            {
                "relation": [
                    ["intersecting", [0, 1]],
                    ["intersecting", [1, 0]],
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicates an earlier relationship"):
        audit(root, annotations_only=True)


def test_step_annotation_face_count_mismatch_is_refused(tmp_path: Path) -> None:
    root = _dataset(tmp_path)
    label_path = next((root / "labels").glob("*_result.json"))
    label = json.loads(label_path.read_text(encoding="utf-8"))
    label["cls"]["6"] = 24
    label["bottom"]["6"] = 0
    label_path.write_text(json.dumps(label), encoding="utf-8")
    with pytest.raises(ValueError, match="STEP has 6 faces but annotation has 7"):
        audit(root, annotations_only=False)


def test_generator_face_order_mismatch_refuses_attribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _dataset(tmp_path)
    original = audit_module._generator_face_order
    monkeypatch.setattr(
        audit_module,
        "_generator_face_order",
        lambda part: tuple(reversed(original(part))),
    )
    with pytest.raises(ValueError, match="traversal differs from the audited generator order"):
        audit(root, annotations_only=False)


def test_selected_artifact_digest_is_deterministic_and_content_bound(tmp_path: Path) -> None:
    root = _dataset(tmp_path)
    first = audit(root, annotations_only=True)["selected_artifacts"]
    second = audit(root, annotations_only=True)["selected_artifacts"]
    assert first == second

    relation_path = root / "labels" / f"{DEFAULT_MODEL_ID}_result_rel.json"
    relation_path.write_text(relation_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert audit(root, annotations_only=True)["selected_artifacts"]["sha256"] != first["sha256"]


def test_report_errors_use_portable_paths() -> None:
    root = PureWindowsPath(r"C:\external\mftrcad")
    error = ValueError(r"C:\external\mftrcad\labels\model_result.json: malformed")

    assert audit_module._portable_error(error, root) == (
        "<root>/labels/model_result.json: malformed"
    )


def test_compact_baseline_is_an_exact_checked_projection(tmp_path: Path) -> None:
    root = _dataset(tmp_path)
    report = audit(root, annotations_only=False)
    compact = compact_baseline(report)
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(compact), encoding="utf-8")

    assert check_compact_baseline(report, baseline) == compact

    changed = json.loads(json.dumps(compact))
    changed["scanner_summary"]["valid_models"] += 1
    baseline.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="differs"):
        check_compact_baseline(report, baseline)

    with pytest.raises(ValueError, match="full development recognition report"):
        compact_baseline(audit(root, annotations_only=True))
