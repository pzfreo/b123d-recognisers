"""F5: Step Levels own complete original horizontal face clusters."""

from __future__ import annotations

import ast
import copy
import inspect
from pathlib import Path

import pytest
from build123d import Box, Compound, Pos, Rot, export_step, import_step
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._geometry import AXIS_ALIGNED_COS
from b123d_recognisers._registry import PHYSICAL_DEFINITIONS, FullyAttributed, NotCounted
from b123d_recognisers.levels import (
    FaceLevel,
    _discover_step_levels,
    _FaceLevelProposal,
    _StepLevelAttributionError,
    step_level_records,
)
from b123d_recognisers.result import _take_inventory

ROOT = Path(__file__).parents[1]


def _stepped(*, fragmented: bool = False):
    base = Box(60, 40, 10)
    if fragmented:
        return base + Pos(-20, 0, 7.5) * Box(10, 40, 5) + Pos(20, 0, 7.5) * Box(10, 40, 5)
    return base + Pos(15, 0, 7.5) * Box(30, 40, 5)


def _oracle(part):
    """Fresh topology-first filtered level oracle without production level helpers."""

    graph = FaceGraph(part)
    horizontal = []
    for node in graph.nodes:
        face = graph.face(node)
        surface = BRepAdaptor_Surface(face.wrapped)
        if surface.GetType() != GeomAbs_Plane:
            continue
        direction = surface.Plane().Axis().Direction()
        if abs(direction.Z()) <= AXIS_ALIGNED_COS:
            continue
        bb = face.bounding_box()
        horizontal.append(
            (
                surface.Plane().Location().Z(),
                face.area,
                (bb.min.X, bb.min.Y, bb.max.X, bb.max.Y),
                node,
            )
        )
    part_bb = part.bounding_box()
    threshold = 0.01 * (part_bb.max.X - part_bb.min.X) * (part_bb.max.Y - part_bb.min.Y)
    margin = min(0.6, max(part_bb.max.Z - part_bb.min.Z, 0.0) * 0.25)
    groups = []
    for item in sorted(horizontal, key=lambda value: value[0]):
        if not groups or item[0] - groups[-1][-1][0] > 0.5:
            groups.append([item])
        else:
            groups[-1].append(item)
    expected = []
    for group in groups:
        z = min(item[0] for item in group)
        if sum(item[1] for item in group) <= threshold:
            continue
        if not (part_bb.min.Z + margin < z < part_bb.max.Z - margin):
            continue
        spans = [item[2] for item in group]
        record = FaceLevel(
            z,
            (min(span[0] for span in spans), max(span[2] for span in spans)),
            (min(span[1] for span in spans), max(span[3] for span in spans)),
        )
        nodes = frozenset(item[3] for item in group)
        solid = graph.common_valid_solid(nodes)
        assert solid is not None
        expected.append((record, nodes, solid))
    return graph, expected


@pytest.mark.parametrize("part", [_stepped(), _stepped(fragmented=True)])
def test_step_level_lifecycle_matches_independent_complete_cluster_oracle(part) -> None:
    oracle_graph, expected = _oracle(part)
    ledger = ClaimLedger(FaceGraph(part))
    records = _discover_step_levels(part, writer=ledger.writer)

    assert records == step_level_records(part)
    assert [record.to_dict() for record in records] == [item[0].to_dict() for item in expected]
    candidates = ledger.candidate_set(FamilyId.STEP_LEVELS).candidates
    assert len(records) == len(candidates) == len(expected)
    for record, candidate, (_expected_record, oracle_nodes, _solid) in zip(
        records, candidates, expected, strict=True
    ):
        assert candidate.record is record
        actual = ledger.defining_of(candidate)
        assert sorted(ledger.graph.bounds(node) for node in actual) == sorted(
            oracle_graph.bounds(node) for node in oracle_nodes
        )
        assert ledger.graph.common_valid_solid(actual) is not None


def test_fragmented_cluster_retains_every_original_patch_and_union_span() -> None:
    part = _stepped(fragmented=True)
    ledger = ClaimLedger(FaceGraph(part))
    (record,) = _discover_step_levels(part, writer=ledger.writer)
    (candidate,) = ledger.candidate_set(FamilyId.STEP_LEVELS).candidates

    assert record.x_span == (-30.0, 30.0) and record.y_span == (-20.0, 20.0)
    assert len(ledger.defining_of(candidate)) == 3


def test_mixed_body_cluster_refuses_atomically_but_public_output_is_preserved() -> None:
    first = _stepped()
    second = Pos(100, 0, 0) * _stepped()
    part = Compound([first, second])
    public = step_level_records(part)
    ledger = ClaimLedger(FaceGraph(part))

    assert public
    with pytest.raises(_StepLevelAttributionError, match="one valid solid"):
        _discover_step_levels(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.STEP_LEVELS).candidates == ()


def test_foreign_writer_refuses_without_candidate_prefix() -> None:
    part = _stepped()
    foreign = ClaimLedger(FaceGraph(Pos(100, 0, 0) * part))
    with pytest.raises(_StepLevelAttributionError, match="identity"):
        _discover_step_levels(part, writer=foreign.writer)
    assert foreign.candidate_set(FamilyId.STEP_LEVELS).candidates == ()


@pytest.mark.parametrize("failure", ["empty", "reuse", "late"])
def test_malformed_or_late_role_failure_is_atomic(monkeypatch, failure: str) -> None:
    import b123d_recognisers.levels as module

    part = _stepped(fragmented=True)
    proposals = module._face_level_proposals(part, min_area_frac=module._STEP_MIN_AREA_FRAC)
    retained = [item for item in proposals if item.record in step_level_records(part)]
    assert len(retained) == 1
    if failure == "empty":
        staged = [_FaceLevelProposal(retained[0].record, ())]
    elif failure == "reuse":
        staged = [
            retained[0],
            _FaceLevelProposal(
                FaceLevel(
                    retained[0].record.z + 1,
                    retained[0].record.x_span,
                    retained[0].record.y_span,
                ),
                retained[0].faces,
            ),
        ]
    else:
        staged = [retained[0]]
    monkeypatch.setattr(module, "_face_level_proposals", lambda *_args, **_kwargs: staged)
    ledger = ClaimLedger(FaceGraph(part))
    if failure == "late":
        real = ledger.graph.require_node
        calls = 0

        def fail_last(face):
            nonlocal calls
            calls += 1
            if calls == len(retained[0].faces):
                raise ValueError("late binding")
            return real(face)

        monkeypatch.setattr(ledger.graph, "require_node", fail_last)
    with pytest.raises(_StepLevelAttributionError):
        _discover_step_levels(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.STEP_LEVELS).candidates == ()


def test_equal_bound_wrapper_occurrence_collapses_but_competing_roles_refuse(monkeypatch) -> None:
    import b123d_recognisers.levels as module

    part = _stepped()
    proposals = module._face_level_proposals(part, min_area_frac=module._STEP_MIN_AREA_FRAC)
    retained = [item for item in proposals if item.record in step_level_records(part)]
    assert len(retained) == 1

    ledger = ClaimLedger(FaceGraph(part))
    alias = _FaceLevelProposal(
        retained[0].record, tuple(copy.copy(face) for face in retained[0].faces)
    )
    monkeypatch.setattr(
        module, "_face_level_proposals", lambda *_args, **_kwargs: [retained[0], alias]
    )
    records = _discover_step_levels(part, writer=ledger.writer)
    assert records == [retained[0].record, retained[0].record]
    assert len(ledger.candidate_set(FamilyId.STEP_LEVELS).candidates) == 1

    graph = FaceGraph(part)
    horizontal = [graph.face(node) for node in graph.nodes if graph.is_planar(node)]
    competing = _FaceLevelProposal(retained[0].record, (horizontal[0],))
    monkeypatch.setattr(
        module, "_face_level_proposals", lambda *_args, **_kwargs: [retained[0], competing]
    )
    refused = ClaimLedger(FaceGraph(part))
    with pytest.raises(_StepLevelAttributionError, match="competing"):
        _discover_step_levels(part, writer=refused.writer)
    assert refused.candidate_set(FamilyId.STEP_LEVELS).candidates == ()


def test_body_pure_levels_on_separate_solids_remain_distinct() -> None:
    part = Compound([_stepped(), Pos(100, 0, 30) * _stepped()])
    ledger = ClaimLedger(FaceGraph(part))
    records = _discover_step_levels(part, writer=ledger.writer)
    candidates = ledger.candidate_set(FamilyId.STEP_LEVELS).candidates
    # Whole-part end context retains each body's otherwise-envelope level too; all four
    # clusters nevertheless remain independently body-pure.
    assert len(records) == len(candidates) == 4
    owners = [ledger.graph.common_valid_solid(ledger.defining_of(item)) for item in candidates]
    assert len(set(owners)) == 2 and None not in owners
    assert ledger.defining_of(candidates[0]).isdisjoint(ledger.defining_of(candidates[1]))


@pytest.mark.parametrize(
    "part",
    [
        Pos(37, -19, 11) * _stepped(fragmented=True),
        Rot(0, 0, 90) * _stepped(fragmented=True),
        _stepped(fragmented=True).mirror(),
        _stepped(fragmented=True).scale(0.2),
        _stepped(fragmented=True).scale(5),
    ],
)
def test_translation_rotation_mirror_and_scale_keep_complete_roles(part) -> None:
    records = _discover_step_levels(part, writer=(ledger := ClaimLedger(FaceGraph(part))).writer)
    assert records == step_level_records(part)
    assert len(records) == len(ledger.candidate_set(FamilyId.STEP_LEVELS).candidates) == 1


def test_public_tolerance_routes_and_strict_interior_boundaries() -> None:
    part = _stepped()
    assert step_level_records(part, tol=4.99)
    assert step_level_records(part, tol=5.0) == []
    assert step_level_records(part, tol=6.0) == []
    assert _discover_step_levels(part, tol=4.99) == step_level_records(part, tol=4.99)
    assert _discover_step_levels(part, tol=5.0) == []


def test_step_round_trip_preserves_record_and_complete_roles(tmp_path: Path) -> None:
    path = tmp_path / "levels.step"
    assert export_step(_stepped(fragmented=True), path)
    part = import_step(path)
    ledger = ClaimLedger(FaceGraph(part))
    records = _discover_step_levels(part, writer=ledger.writer)
    assert records == step_level_records(part)
    assert [
        len(ledger.defining_of(candidate))
        for candidate in ledger.candidate_set(FamilyId.STEP_LEVELS).candidates
    ] == [3]


def test_terminal_identity_status_and_not_counted_disposition() -> None:
    product = _take_inventory(_stepped(fragmented=True))
    candidates = product.physical.candidate_set(FamilyId.STEP_LEVELS).candidates
    assert len(candidates) == len(product.result.step_levels) == 1
    assert candidates[0].record is product.result.step_levels[0]
    assert len(product.evidence.defining_of(candidates[0])) == 3
    definition = next(item for item in PHYSICAL_DEFINITIONS if item.family is FamilyId.STEP_LEVELS)
    assert isinstance(definition.attribution, FullyAttributed)
    assert isinstance(definition.census, NotCounted)
    assert definition.census.reason == "level substrate is not a distinct feature"


def test_public_signatures_and_private_registry_seam_are_closed() -> None:
    import b123d_recognisers.levels as module

    assert tuple(inspect.signature(module.recognise_face_levels).parameters) == (
        "part",
        "tol",
        "min_area_frac",
    )
    assert tuple(inspect.signature(module.step_level_records).parameters) == ("part", "tol")
    assert tuple(inspect.signature(module.step_level_zs).parameters) == ("part", "tol")
    assert all(
        "writer" not in inspect.signature(function).parameters
        for function in (
            module.recognise_face_levels,
            module.step_level_records,
            module.step_level_zs,
        )
    )

    registry = ast.parse((ROOT / "src/b123d_recognisers/_registry.py").read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(registry)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_discover_step_levels"
    ]
    assert len(calls) == 1
    keywords = {keyword.arg: keyword.value for keyword in calls[0].keywords}
    assert isinstance(keywords["writer"], ast.Attribute)
    assert keywords["writer"].attr == "writer"
    assert isinstance(keywords["writer"].value, ast.Name)
    assert keywords["writer"].value.id == "s"

    importers = []
    for path in (ROOT / "src/b123d_recognisers").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            isinstance(node, ast.ImportFrom)
            and any(alias.name == "_discover_step_levels" for alias in node.names)
            for node in ast.walk(tree)
        ):
            importers.append(path.name)
    assert importers == ["_registry.py"]
    source = inspect.getsource(module._discover_step_levels)
    assert not any(
        name in source
        for name in ("CandidateSet", "EvidenceIndex", "Inventory", "Disposition", "reconcile")
    )
