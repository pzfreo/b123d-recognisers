"""F5: Step Levels own complete original horizontal face clusters."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
from build123d import Box, Compound, Pos, export_step, import_step
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
    source = inspect.getsource(module._discover_step_levels)
    assert not any(
        name in source
        for name in ("CandidateSet", "EvidenceIndex", "Inventory", "Disposition", "reconcile")
    )
