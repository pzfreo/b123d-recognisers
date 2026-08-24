"""F5e: every CounterSink occurrence owns only its original conical seat face."""

from __future__ import annotations

import ast
import copy
import math
from pathlib import Path

import pytest
from build123d import Box, Cone, Cylinder, GeomType, Pos, Rot, Shell, export_step, import_step
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder

from b123d_recognisers import recognise_countersinks
from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers.countersinks import _discover_countersinks
from b123d_recognisers.result import _take_inventory


def _plate(points=((0, 0),)):
    part = Box(90, 60, 12)
    for x, y in points:
        part -= Pos(x, y, 0) * Cylinder(3, 12)
        part -= Pos(x, y, 4) * Cone(3, 7, 4)
    return part


def _angle_plate(included_angle: float):
    depth = 4.0
    minor = 3.0
    major = minor + depth * math.tan(math.radians(included_angle / 2))
    return Box(100, 100, 16) - Cylinder(minor, 16) - Pos(0, 0, depth) * Cone(minor, major, depth)


def _assert_role(ledger, candidate, record) -> None:
    defining = ledger.defining_of(candidate)
    assert len(defining) == 1
    assert ledger.graph.common_valid_solid(defining) is not None
    (node,) = defining
    face = ledger.graph.face(node)
    surface = BRepAdaptor_Surface(face.wrapped)
    assert surface.GetType() == GeomAbs_Cone
    circles = sorted(face.edges().filter_by(GeomType.CIRCLE), key=lambda edge: edge.radius)
    assert len(circles) >= 2
    minor, major = circles[0], circles[-1]
    opening = major.arc_center
    inner = minor.arc_center
    delta = (inner.X - opening.X, inner.Y - opening.Y, inner.Z - opening.Z)
    depth = math.sqrt(sum(value * value for value in delta))
    axis = tuple(round(value / depth, 4) for value in delta)
    assert record.axis == axis
    assert record.location == tuple(round(value, 4) for value in (opening.X, opening.Y, opening.Z))
    assert record.major_diameter == round(2 * major.radius, 4)
    assert record.drill_diameter == round(2 * minor.radius, 4)
    assert record.depth == round(depth, 4)
    assert record.included_angle == round(2 * abs(math.degrees(surface.Cone().SemiAngle())), 2)
    matching_cylinders = []
    for other in ledger.graph.nodes:
        other_surface = BRepAdaptor_Surface(ledger.graph.face(other).wrapped)
        if other_surface.GetType() != GeomAbs_Cylinder:
            continue
        cylinder = other_surface.Cylinder()
        axis_line = cylinder.Axis()
        direction = axis_line.Direction()
        line_direction = (direction.X(), direction.Y(), direction.Z())
        if abs(sum(a * b for a, b in zip(record.axis, line_direction, strict=True))) <= 0.999:
            continue
        line_point = axis_line.Location()
        offset = tuple(
            record.location[index] - (line_point.X(), line_point.Y(), line_point.Z())[index]
            for index in range(3)
        )
        along = sum(offset[index] * line_direction[index] for index in range(3))
        distance = math.sqrt(
            sum((offset[index] - along * line_direction[index]) ** 2 for index in range(3))
        )
        if abs(2 * cylinder.Radius() - record.drill_diameter) <= 0.001 and distance <= 0.001:
            matching_cylinders.append(other)
    assert matching_cylinders
    assert all(context not in defining for context in matching_cylinders)


def _claimed(part):
    plain = recognise_countersinks(part)
    ledger = ClaimLedger(FaceGraph(part))
    measured = _discover_countersinks(part, writer=ledger.writer)
    assert measured == plain
    assert [record.to_dict() for record in measured] == [record.to_dict() for record in plain]
    candidates = ledger.candidate_set(FamilyId.COUNTERSINKS).candidates
    assert len(candidates) == len(measured)
    for candidate, record in zip(candidates, measured, strict=True):
        assert candidate.record is record
        _assert_role(ledger, candidate, record)
    return ledger, measured


@pytest.mark.parametrize(
    "transform",
    [None, Rot(90, 0, 0), Rot(0, 90, 0), Rot(31, 17, 43), Rot(0, 0, 180)],
)
def test_countersink_owner_is_rotation_invariant(transform) -> None:
    part = _plate()
    if transform is not None:
        part = transform * part
    _ledger, records = _claimed(part)
    assert len(records) == 1


def test_multiple_countersinks_keep_sorted_occurrence_identity() -> None:
    ledger, records = _claimed(_plate(((-30, -15), (5, 12), (30, -8))))
    assert len(records) == 3
    assert records == sorted(records, key=lambda record: (record.location, record.major_diameter))
    assert (
        len(
            {
                next(iter(ledger.defining_of(candidate)))
                for candidate in ledger.candidate_set(FamilyId.COUNTERSINKS).candidates
            }
        )
        == 3
    )


@pytest.mark.parametrize("angle", [60.0, 82.0, 90.0, 100.0, 120.0, 160.0])
def test_standard_and_inclusive_maximum_angles_keep_exact_owner(angle: float) -> None:
    _ledger, records = _claimed(_angle_plate(angle))
    assert len(records) == 1
    assert records[0].included_angle == pytest.approx(angle, abs=0.02)


def test_translation_and_uniform_scale_keep_owner_correspondence() -> None:
    original = _plate()
    for part in (Pos(17, -9, 4) * original, original.scale(3), original.mirror()):
        _ledger, records = _claimed(part)
        assert len(records) == 1


@pytest.mark.parametrize(
    "part",
    [
        Cylinder(3, 12),
        Box(40, 40, 12) - Cylinder(3, 12),
        Box(40, 40, 12) - Cylinder(3, 12) - Pos(0, 0, 2) * Cone(3, 4, 2),
        _angle_plate(165.0),
    ],
)
def test_rejected_shapes_issue_no_countersink_candidate(part) -> None:
    ledger = ClaimLedger(FaceGraph(part))
    assert _discover_countersinks(part, writer=ledger.writer) == []
    assert ledger.candidate_set(FamilyId.COUNTERSINKS).candidates == ()


def test_geometry_only_open_shell_result_has_no_aggregate_publication() -> None:
    shell = Shell(_plate().faces())
    assert recognise_countersinks(shell)
    ledger = ClaimLedger(FaceGraph(shell))
    with pytest.raises(ValueError, match="no unambiguous valid solid"):
        _discover_countersinks(shell, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.COUNTERSINKS).candidates == ()


def test_step_round_trip_preserves_conical_owner_role(tmp_path: Path) -> None:
    path = tmp_path / "countersink.step"
    export_step(_plate(), path)
    imported = import_step(path)
    _ledger, records = _claimed(imported)
    assert len(records) == 1


def test_aggregate_inventory_publishes_terminal_countersink_evidence() -> None:
    product = _take_inventory(_plate(((-20, 0), (20, 0))))
    candidates = product.physical.candidate_set(FamilyId.COUNTERSINKS).candidates
    assert candidates
    assert tuple(candidate.record for candidate in candidates) == product.result.countersinks
    assert product.accepted.candidate_set(FamilyId.COUNTERSINKS).candidates == candidates
    assert all(len(product.evidence.defining_of(candidate)) == 1 for candidate in candidates)


def test_multiple_valid_solids_publish_independent_owner_bodies() -> None:
    part = _plate() + Pos(150, 0, 0) * _plate()
    ledger, records = _claimed(part)
    candidates = ledger.candidate_set(FamilyId.COUNTERSINKS).candidates
    assert len(records) == len(candidates) == 2
    solids = {ledger.graph.common_valid_solid(ledger.defining_of(item)) for item in candidates}
    assert None not in solids and len(solids) == 2


def test_late_owner_validation_refuses_before_publication(monkeypatch: pytest.MonkeyPatch) -> None:
    part = _plate(((-20, 0), (20, 0)))
    ledger = ClaimLedger(FaceGraph(part))
    original = ledger.graph.common_valid_solid
    calls = 0

    def fail_second(nodes):
        nonlocal calls
        calls += 1
        return original(nodes) if calls == 1 else None

    monkeypatch.setattr(ledger.graph, "common_valid_solid", fail_second)
    with pytest.raises(ValueError, match="no unambiguous valid solid"):
        _discover_countersinks(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.COUNTERSINKS).candidates == ()


def test_late_owner_binding_refuses_before_publication(monkeypatch: pytest.MonkeyPatch) -> None:
    part = _plate(((-20, 0), (20, 0)))
    ledger = ClaimLedger(FaceGraph(part))
    original = ledger.graph.require_node
    calls = 0

    def fail_second(face):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("later countersink binding failed")
        return original(face)

    monkeypatch.setattr(ledger.graph, "require_node", fail_second)
    with pytest.raises(ValueError, match="later countersink binding failed"):
        _discover_countersinks(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.COUNTERSINKS).candidates == ()


def test_foreign_writer_refuses_without_publication() -> None:
    part = _plate()
    foreign = ClaimLedger(FaceGraph(Box(20, 20, 20)))
    with pytest.raises(ValueError):
        _discover_countersinks(part, writer=foreign.writer)
    assert foreign.candidate_set(FamilyId.COUNTERSINKS).candidates == ()


@pytest.mark.parametrize("translated", [False, True])
def test_deep_cloned_owner_refuses_without_publication(
    monkeypatch: pytest.MonkeyPatch, translated: bool
) -> None:
    part = _plate()
    ledger = ClaimLedger(FaceGraph(part))
    original = ledger.graph.require_node

    def cloned(face):
        changed = copy.deepcopy(face)
        if translated:
            changed = changed.translate((1, 0, 0))
        return original(changed)

    monkeypatch.setattr(ledger.graph, "require_node", cloned)
    with pytest.raises(ValueError):
        _discover_countersinks(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.COUNTERSINKS).candidates == ()


def test_reversed_face_traversal_preserves_occurrence_roles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    part = _plate(((-20, 0), (20, 0)))
    baseline = [record.to_dict() for record in recognise_countersinks(part)]
    part_type = type(part)
    original = part_type.faces

    def reversed_faces(self):
        faces = original(self)
        return type(faces)(reversed(faces))

    monkeypatch.setattr(part_type, "faces", reversed_faces)
    ledger, records = _claimed(part)
    assert [record.to_dict() for record in records] == baseline
    assert len(ledger.candidate_set(FamilyId.COUNTERSINKS).candidates) == 2


def test_only_registry_may_call_writer_enabled_core() -> None:
    root = Path(__file__).parents[1]
    references: list[str] = []
    for path in (root / "src").rglob("*.py"):
        if path.name == "countersinks.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            isinstance(node, ast.Name | ast.Attribute)
            and (
                isinstance(node, ast.Name)
                and node.id == "_discover_countersinks"
                or isinstance(node, ast.Attribute)
                and node.attr == "_discover_countersinks"
            )
            for node in ast.walk(tree)
        ):
            references.append(path.name)
    assert references == ["_registry.py"]


def test_counter_sink_constructor_roster_is_closed() -> None:
    root = Path(__file__).parents[1]
    sites: list[tuple[str, str]] = []
    for path in (root / "src" / "b123d_recognisers").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "CounterSink"
            ):
                function = next(
                    (
                        parent.name
                        for parent in ast.walk(tree)
                        if isinstance(parent, ast.FunctionDef) and node in ast.walk(parent)
                    ),
                    "",
                )
                sites.append((path.name, function))
    assert sites == [("countersinks.py", "_discover_countersinks")]
