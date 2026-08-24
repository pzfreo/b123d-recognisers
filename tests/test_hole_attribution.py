"""F5: Hole occurrences own their complete original cylindrical roles."""

from __future__ import annotations

import ast
import copy
import math
from pathlib import Path

import pytest
from build123d import Box, Compound, Cone, Cylinder, Pos, Rot, Shell
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder

from b123d_recognisers import recognise_holes
from b123d_recognisers._adjacency import FaceGraph, frame_points_outward
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._hole_features import HoleRecord, _discover_holes
from b123d_recognisers._registry import PHYSICAL_DEFINITIONS
from b123d_recognisers.countersinks import _discover_countersinks, recognise_countersinks
from b123d_recognisers.result import _take_inventory

ROOT = Path(__file__).parents[1]


def _through():
    return Box(60, 60, 20) - Cylinder(5, 20)


def _blind():
    return Box(60, 60, 20) - Pos(0, 0, 4) * Cylinder(5, 12)


def _counterbore():
    return Box(60, 60, 20) - Cylinder(5, 20) - Pos(0, 0, 7) * Cylinder(9, 6)


def _spotface_stack():
    return (
        Box(100, 100, 40)
        - Pos(0, 0, 17.5) * Cylinder(30, 5)
        - Pos(0, 0, 12) * Cylinder(9, 6)
        - Pos(0, 0, 1.5) * Cylinder(5.05, 15)
    )


def _countersunk():
    return Box(60, 60, 20) - Cylinder(2.5, 20) - Pos(0, 0, 7.5) * Cone(2.5, 5, 5)


def _line_distance(point, line, direction) -> float:
    offset = tuple(point[i] - line[i] for i in range(3))
    along = sum(offset[i] * direction[i] for i in range(3))
    return math.sqrt(sum((offset[i] - along * direction[i]) ** 2 for i in range(3)))


def _expected_cylindrical_nodes(graph: FaceGraph, record: HoleRecord):
    """Fresh topology-first oracle for the fixtures in this module.

    It reads original surfaces directly, before Candidate evidence, and selects internal,
    coaxial patches whose diameters are serialized by the Hole occurrence. Context cones,
    end planes, external cylinders and unrelated axes cannot enter the result.
    """

    diameters = {record.diameter}
    if record.cbore is not None:
        diameters.add(record.cbore.diameter)
    if record.spotface is not None:
        diameters.add(record.spotface.diameter)
    expected = []
    for node in graph.nodes:
        face = graph.face(node)
        surface = BRepAdaptor_Surface(face.wrapped)
        if surface.GetType() != GeomAbs_Cylinder or frame_points_outward(face):
            continue
        cylinder = surface.Cylinder()
        axis = cylinder.Axis()
        direction = axis.Direction()
        unit = (direction.X(), direction.Y(), direction.Z())
        if abs(sum(a * b for a, b in zip(record.axis, unit, strict=True))) < 0.999999:
            continue
        origin = axis.Location()
        line = (origin.X(), origin.Y(), origin.Z())
        if _line_distance(record.location, line, unit) > 1e-5:
            continue
        diameter = 2 * cylinder.Radius()
        serialized_land = any(
            diameter == pytest.approx(value, rel=1e-5, abs=1e-7) for value in diameters
        )
        bounds = face.bounding_box()
        corners = [
            (x, y, z)
            for x in (bounds.min.X, bounds.max.X)
            for y in (bounds.min.Y, bounds.max.Y)
            for z in (bounds.min.Z, bounds.max.Z)
        ]
        deep = tuple(record.location[i] + record.depth * record.axis[i] for i in range(3))
        deep_s = sum(deep[i] * unit[i] for i in range(3))
        projections = [sum(point[i] * unit[i] for i in range(3)) for point in corners]
        blind_deep_extension = record.bottom != "through" and (
            min(projections) - 1e-5 <= deep_s <= max(projections) + 1e-5
        )
        if serialized_land or blind_deep_extension:
            expected.append(node)
    return frozenset(expected)


def _claimed(part, **kwargs):
    public = recognise_holes(part, **kwargs)
    ledger = ClaimLedger(FaceGraph(part))
    records = _discover_holes(part, writer=ledger.writer, **kwargs)
    assert [type(record) for record in records] == [type(record) for record in public]
    assert [record.to_dict() for record in records] == [record.to_dict() for record in public]
    candidates = ledger.candidate_set(FamilyId.HOLES).candidates
    assert len(candidates) == len(records)
    for record, candidate in zip(records, candidates, strict=True):
        assert candidate.record is record
        expected = _expected_cylindrical_nodes(ledger.graph, record)
        assert expected
        assert ledger.defining_of(candidate) == expected
        assert ledger.graph.common_valid_solid(expected) is not None
    return records, candidates, ledger


@pytest.mark.parametrize("part", [_through(), _blind(), _counterbore(), _spotface_stack()])
def test_basic_hole_routes_have_exact_cylindrical_owners(part) -> None:
    _claimed(part)


def test_split_and_interrupted_bore_retains_every_original_patch() -> None:
    keyed = (
        Box(60, 40, 10)
        - Cylinder(5, 12)
        - Pos(0, 5, 0) * Box(2, 4, 12)
        - Pos(0, -5, 0) * Box(2, 4, 12)
    )
    records, candidates, ledger = _claimed(keyed)
    assert len(records) == 1
    assert len(ledger.defining_of(candidates[0])) > 1

    crossed = Box(60, 60, 40) - Cylinder(5, 40) - Cylinder(3, 60, rotation=(0, 90, 0))
    records, candidates, ledger = _claimed(crossed)
    assert len(records) == len(candidates) == 2
    for record, candidate in zip(records, candidates, strict=True):
        assert ledger.defining_of(candidate) == _expected_cylindrical_nodes(ledger.graph, record)


def test_near_step_and_bottom_relief_roles_exclude_transition_context() -> None:
    grooved = Box(60, 60, 20) - Cylinder(5, 20) - Pos(0, 0, 7) * Cylinder(9, 6) - Pos(
        0, 0, 7
    ) * Cylinder(10, 2)
    records, candidates, ledger = _claimed(grooved)
    (record,) = records
    assert record.cbore is not None and record.spotface is None
    defining = ledger.defining_of(candidates[0])
    assert all(
        BRepAdaptor_Surface(ledger.graph.face(node).wrapped).GetType() == GeomAbs_Cylinder
        for node in defining
    )

    relief = Box(60, 60, 40) - Pos(0, 0, 12.5) * Cylinder(4.25, 15) - Pos(
        0, 0, 6
    ) * Cylinder(5, 2)
    records, candidates, ledger = _claimed(relief)
    assert records[0].bottom == "flat"
    assert {round(BRepAdaptor_Surface(ledger.graph.face(node).wrapped).Cylinder().Radius() * 2, 2)
            for node in ledger.defining_of(candidates[0])} == {8.5, 10.0}


def test_nested_countersink_stays_predecessor_owned_and_hole_consulted() -> None:
    product = _take_inventory(_countersunk())
    holes = product.physical.candidate_set(FamilyId.HOLES).candidates
    countersinks = product.physical.candidate_set(FamilyId.COUNTERSINKS).candidates
    assert len(holes) == len(countersinks) == 1
    hole, countersink = holes[0], countersinks[0]
    assert hole.record.csink is countersink.record
    hole_nodes = product.evidence.defining_of(hole)
    cone_nodes = product.evidence.defining_of(countersink)
    assert hole_nodes and cone_nodes and hole_nodes.isdisjoint(cone_nodes)
    assert all(
        BRepAdaptor_Surface(product.context.graph.face(node).wrapped).GetType() == GeomAbs_Cylinder
        for node in hole_nodes
    )
    assert all(
        BRepAdaptor_Surface(product.context.graph.face(node).wrapped).GetType() == GeomAbs_Cone
        for node in cone_nodes
    )


def _completed_countersinks(part):
    ledger = ClaimLedger(FaceGraph(part), definitions=PHYSICAL_DEFINITIONS)
    records = _discover_countersinks(part, writer=ledger.writer)
    ledger.candidate_set_for(FamilyId.COUNTERSINKS, records)
    holes = next(item for item in PHYSICAL_DEFINITIONS if item.family is FamilyId.HOLES)
    occurrences = ledger.restricted_inputs(holes).occurrences(
        FamilyId.COUNTERSINKS, type(records[0])
    )
    return ledger, records, occurrences


def test_matched_countersink_requires_exact_completed_predecessor() -> None:
    part = _countersunk()
    records = recognise_countersinks(part)
    ledger = ClaimLedger(FaceGraph(part))
    with pytest.raises(ValueError, match="predecessor identity"):
        _discover_holes(part, csinks=records, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.HOLES).candidates == ()

    # An injected sibling record which does not match this Hole remains irrelevant context.
    unrelated = recognise_countersinks(Pos(100, 0, 0) * _countersunk())
    records = _discover_holes(part, csinks=unrelated, writer=ledger.writer)
    assert records and records[0].csink is None
    assert ledger.candidate_set(FamilyId.HOLES).candidates


def test_completed_countersink_from_another_run_refuses_body_link_atomically() -> None:
    part = _countersunk()
    foreign, records, occurrences = _completed_countersinks(copy.deepcopy(part))
    assert foreign is not None
    ledger = ClaimLedger(FaceGraph(part))
    with pytest.raises(ValueError, match="different solids"):
        _discover_holes(
            part,
            csinks=records,
            predecessor_occurrences=occurrences,
            writer=ledger.writer,
        )
    assert ledger.candidate_set(FamilyId.HOLES).candidates == ()


def test_duplicate_hole_face_ownership_refuses_without_prefix(monkeypatch) -> None:
    import b123d_recognisers._hole_features as module

    part = _through()
    ledger = ClaimLedger(FaceGraph(part))
    original = module._merge_stacks

    def duplicate(stacks, edge_faces, cache=None):
        merged = original(stacks, edge_faces, cache)
        return [*merged, merged[0]]

    monkeypatch.setattr(module, "_merge_stacks", duplicate)
    with pytest.raises(ValueError, match="share defining"):
        _discover_holes(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.HOLES).candidates == ()


def test_equal_holes_keep_occurrence_and_body_identity() -> None:
    original = _through()
    part = Compound([Pos(-80, 0, 0) * original, Pos(80, 0, 0) * copy.deepcopy(original)])
    records, candidates, ledger = _claimed(part)
    assert len(records) == 2
    assert records[0].diameter == records[1].diameter
    first, second = (ledger.defining_of(candidate) for candidate in candidates)
    assert first.isdisjoint(second)
    assert ledger.graph.common_valid_solid(first) != ledger.graph.common_valid_solid(second)


@pytest.mark.parametrize("transform", [Rot(0, 90, 0), Rot(31, 17, 43)])
def test_cross_and_nonprincipal_axes_keep_exact_roles(transform) -> None:
    _claimed(transform * _through())


def test_open_shell_public_compatibility_refuses_aggregate_without_prefix() -> None:
    shell = Shell(_through().faces())
    assert recognise_holes(shell)
    ledger = ClaimLedger(FaceGraph(shell))
    with pytest.raises(ValueError, match="one valid solid"):
        _discover_holes(shell, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.HOLES).candidates == ()


def test_foreign_writer_and_late_binding_fail_atomically(monkeypatch) -> None:
    foreign = ClaimLedger(FaceGraph(Pos(100, 0, 0) * _through()))
    with pytest.raises(ValueError):
        _discover_holes(_through(), writer=foreign.writer)
    assert foreign.candidate_set(FamilyId.HOLES).candidates == ()

    part = Compound([Pos(-50, 0, 0) * _through(), Pos(50, 0, 0) * _through()])
    ledger = ClaimLedger(FaceGraph(part))
    original = ledger.graph.require_node
    calls = 0

    def fail_late(face):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise ValueError("late Hole binding")
        return original(face)

    monkeypatch.setattr(ledger.graph, "require_node", fail_late)
    with pytest.raises(ValueError, match="late Hole binding"):
        _discover_holes(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.HOLES).candidates == ()


def test_box_boss_and_slot_issue_no_hole_evidence() -> None:
    for part in (
        Box(20, 20, 20),
        Box(40, 40, 10) + Pos(0, 0, 10) * Cylinder(5, 10),
    ):
        assert recognise_holes(part) == []
        ledger = ClaimLedger(FaceGraph(part))
        assert _discover_holes(part, writer=ledger.writer) == []
        assert ledger.candidate_set(FamilyId.HOLES).candidates == ()


def _qualified_calls(tree: ast.AST) -> list[tuple[str, ast.Call]]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    def qualified(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return f"{qualified(node.value)}.{node.attr}"
        return ""

    return [(qualified(node.func), node) for node in ast.walk(tree) if isinstance(node, ast.Call)]


def test_private_hole_core_has_one_writer_caller_and_declared_predecessor() -> None:
    sites = []
    for path in (ROOT / "src/b123d_recognisers").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        sites.extend(
            (path.name, call)
            for qualified, call in _qualified_calls(tree)
            if qualified.endswith("._discover_holes") or qualified == "_discover_holes"
        )
    assert {name for name, _call in sites} == {"_hole_features.py", "_registry.py"}
    registry = next(call for name, call in sites if name == "_registry.py")
    keywords = {keyword.arg: keyword.value for keyword in registry.keywords}
    writer = keywords["writer"]
    assert isinstance(writer, ast.Attribute) and writer.attr == "writer"
    predecessor = keywords["predecessor_occurrences"]
    assert isinstance(predecessor, ast.Name) and predecessor.id == "occurrences"


def test_terminal_inventory_retains_complete_hole_identity() -> None:
    product = _take_inventory(_counterbore())
    candidates = product.physical.candidate_set(FamilyId.HOLES).candidates
    assert len(candidates) == len(product.result.holes) == 1
    assert candidates[0].record is product.result.holes[0]
    assert product.evidence.defining_of(candidates[0])
