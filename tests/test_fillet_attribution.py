"""F5d: every Fillet occurrence owns only its original curved blend face."""

from __future__ import annotations

import ast
import copy
import math
from pathlib import Path

import pytest
from build123d import (
    Axis,
    Box,
    BuildPart,
    BuildSketch,
    Cylinder,
    GeomType,
    Pos,
    Rot,
    Shell,
    SlotOverall,
    Torus,
    export_step,
    extrude,
    fillet,
    import_step,
)
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Torus

import b123d_recognisers.fillets as fillets_module
from b123d_recognisers import recognise_fillets
from b123d_recognisers._adjacency import FaceEdges, FaceGraph, edge_face_map, neighbours
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._features import analyse_cylinders
from b123d_recognisers.fillets import _discover_fillets
from b123d_recognisers.result import _take_inventory


def _prismatic():
    box = Box(40, 30, 20)
    return fillet(list(box.edges().filter_by(Axis.Z)), 2.0)


def _prismatic_axis(axis: Axis, radius: float = 2.0):
    box = Box(40, 30, 20)
    return fillet(list(box.edges().filter_by(axis)), radius)


def _turned():
    shaft = Pos(0, 0, 20) * Cylinder(15, 40) + Pos(0, 0, 55) * Cylinder(8, 30)
    return fillet([edge for edge in shaft.edges() if edge.geom_type == GeomType.CIRCLE], 0.8)


def _internal_pocket_round():
    pocket = Box(40, 40, 20) - Pos(0, 0, 5) * Box(20, 20, 10)
    bottom = [
        edge
        for edge in pocket.edges()
        if abs(edge.center().Z) < 1e-6 and abs(edge.center().X) <= 10 and abs(edge.center().Y) <= 10
    ]
    return fillet(bottom, 2)


def _through_slot():
    with BuildPart() as slot_part:
        with BuildSketch():
            SlotOverall(30, 10)
        extrude(amount=20, both=True)
    return Box(50, 40, 20) - slot_part.part


def _claimed(part, **kwargs):
    call = {
        "min_radius": None,
        "max_radius_frac": 0.45,
        "face_edges": None,
        "cyls": analyse_cylinders(part),
        "include_cylindrical": True,
        **kwargs,
    }
    plain = recognise_fillets(part, **call)
    ledger = ClaimLedger(FaceGraph(part))
    measured = _discover_fillets(part, writer=ledger.writer, **call)
    assert measured == plain
    assert [record.to_dict() for record in measured] == [record.to_dict() for record in plain]
    candidates = ledger.candidate_set(FamilyId.FILLETS).candidates
    assert len(candidates) == len(measured)
    for candidate, record in zip(candidates, measured, strict=True):
        assert candidate.record is record
        defining = ledger.defining_of(candidate)
        assert len(defining) == 1
        assert ledger.graph.common_valid_solid(defining) is not None
        (node,) = defining
        face = ledger.graph.face(node)
        surface = BRepAdaptor_Surface(face.wrapped)
        expected_type = GeomAbs_Torus if record.turned else GeomAbs_Cylinder
        assert surface.GetType() == expected_type
        primitive = surface.Torus() if record.turned else surface.Cylinder()
        radius = primitive.MinorRadius() if record.turned else primitive.Radius()
        assert record.radius == round(radius, 3)
        direction = primitive.Axis().Direction()
        components = (abs(direction.X()), abs(direction.Y()), abs(direction.Z()))
        assert record.axis == "xyz"[max(range(3), key=components.__getitem__)]
        point = surface.Value(
            0.5 * (surface.FirstUParameter() + surface.LastUParameter()),
            0.5 * (surface.FirstVParameter() + surface.LastVParameter()),
        )
        assert record.at == tuple(round(value, 3) for value in (point.X(), point.Y(), point.Z()))
        assert all(math.isfinite(value) for value in record.at)
        context = set(neighbours(face, edge_face_map(part.faces())))
        assert all(ledger.graph.require_node(item) not in defining for item in context)
        if record.turned:
            owner_solid = ledger.graph.common_valid_solid(defining)
            external = [
                item
                for inventory in analyse_cylinders(part)
                for item in inventory
                if item["external"] and item["face"] in context
            ]
            assert external
            assert any(
                ledger.graph.common_valid_solid((node, ledger.graph.require_node(item["face"])))
                is owner_solid
                for item in external
            )
    return ledger, measured


@pytest.mark.parametrize(
    "part",
    [
        _prismatic_axis(Axis.X),
        _prismatic_axis(Axis.Y),
        _prismatic_axis(Axis.Z),
        _prismatic().mirror(),
        Rot(0, 90, 0) * _prismatic(),
        Rot(90, 0, 0) * _prismatic(),
        _prismatic().scale(3),
        Pos(13, -7, 5) * _prismatic(),
    ],
)
def test_prismatic_fillet_writer_preserves_records_and_owner_role(part) -> None:
    ledger, measured = _claimed(part)
    assert measured and all(not record.turned for record in measured)
    assert len(
        {ledger.defining_of(item) for item in ledger.candidate_set(FamilyId.FILLETS).candidates}
    ) == len(measured)


def test_turned_fillet_writer_preserves_records_and_owner_role_when_prismatic_is_suppressed() -> (
    None
):
    part = _turned()
    ledger, measured = _claimed(part, include_cylindrical=False)
    assert measured and all(record.turned for record in measured)
    assert len(ledger.candidate_set(FamilyId.FILLETS).candidates) == len(measured)


def test_mixed_inventory_suppresses_only_prismatic_fillets() -> None:
    part = Pos(-70, 0, 0) * _prismatic() + Pos(70, 0, 0) * _turned()
    _all_ledger, all_records = _claimed(part, include_cylindrical=True)
    turned_ledger, turned_records = _claimed(part, include_cylindrical=False)
    assert any(not record.turned for record in all_records)
    assert turned_records and all(record.turned for record in turned_records)
    assert turned_records == [record for record in all_records if record.turned]
    assert len(turned_ledger.candidate_set(FamilyId.FILLETS).candidates) == len(turned_records)


def test_equal_and_unequal_occurrences_keep_identity_and_order() -> None:
    equal_ledger, equal = _claimed(_prismatic())
    assert len(equal) == 4 and len({record.radius for record in equal}) == 1
    equal_candidates = equal_ledger.candidate_set(FamilyId.FILLETS).candidates
    assert len({id(candidate.record) for candidate in equal_candidates}) == 4
    assert len({equal_ledger.defining_of(candidate) for candidate in equal_candidates}) == 4

    part = Pos(-50, 0, 0) * _prismatic_axis(Axis.Z, 1.0) + Pos(50, 0, 0) * _prismatic_axis(
        Axis.Z, 2.0
    )
    unequal_ledger, unequal = _claimed(part)
    assert {record.radius for record in unequal} == {1.0, 2.0}
    assert tuple(unequal) == tuple(sorted(unequal, key=lambda record: (record.axis, record.at)))
    assert len(unequal_ledger.candidate_set(FamilyId.FILLETS).candidates) == len(unequal)


@pytest.mark.parametrize("route", ["two_bands", "sphere"])
def test_unavailable_torus_alternative_routes_use_bounded_real_face_mutations(
    monkeypatch, route
) -> None:
    """Pin algebraic branches whose bounded real-fixture scan found no isolated occurrence."""

    part = _turned()
    if route == "sphere":
        from build123d import Sphere

        part = part.fuse(Pos(0, 0, 70) * Sphere(3))
    inventory = analyse_cylinders(part)
    external = [item["face"] for group in inventory for item in group if item["external"]]
    sphere = next((face for face in part.faces() if face.geom_type == GeomType.SPHERE), None)
    real_neighbours = fillets_module.neighbours
    routed: list[tuple] = []

    def route_neighbours(face, edge_faces, *, face_edges=None):
        found = real_neighbours(face, edge_faces, face_edges=face_edges)
        if face.geom_type != GeomType.TORUS:
            return found
        adjacent_cylinders = [item for item in found if item.geom_type == GeomType.CYLINDER]
        if not adjacent_cylinders:
            return found
        owner_cylinder = adjacent_cylinders[0]
        if route == "sphere":
            assert sphere is not None
            result = [owner_cylinder, sphere]
            routed.append(tuple(result))
            return result
        owner_radius = BRepAdaptor_Surface(owner_cylinder.wrapped).Cylinder().Radius()
        other = next(
            item
            for item in external
            if BRepAdaptor_Surface(item.wrapped).Cylinder().Radius() != pytest.approx(owner_radius)
        )
        result = [owner_cylinder, other]
        routed.append(tuple(result))
        return result

    monkeypatch.setattr(fillets_module, "neighbours", route_neighbours)
    ledger, measured = _claimed(part, include_cylindrical=False, cyls=inventory)
    assert measured and all(record.turned for record in measured)
    assert all(
        len(ledger.defining_of(candidate)) == 1
        for candidate in ledger.candidate_set(FamilyId.FILLETS).candidates
    )
    assert routed
    for context in routed:
        assert all(face.geom_type != GeomType.PLANE for face in context)
        if route == "sphere":
            assert [face.geom_type for face in context].count(GeomType.CYLINDER) == 1
            assert [face.geom_type for face in context].count(GeomType.SPHERE) == 1
        else:
            assert all(face.geom_type == GeomType.CYLINDER for face in context)
            diameters = {
                round(2 * BRepAdaptor_Surface(face.wrapped).Cylinder().Radius(), 6)
                for face in context
            }
            assert len(diameters) == 2


@pytest.mark.parametrize(
    ("min_radius", "max_fraction", "accepted"),
    [
        (1.999, 0.45, True),
        (2.0, 0.45, True),
        (2.001, 0.45, False),
        (None, 0.05001, True),
        (None, 0.05, True),
        (None, 0.04999, False),
    ],
)
def test_radius_thresholds_are_independently_inclusive(min_radius, max_fraction, accepted) -> None:
    part = _prismatic()
    ledger = ClaimLedger(FaceGraph(part))
    measured = _discover_fillets(
        part,
        min_radius=min_radius,
        max_radius_frac=max_fraction,
        face_edges=None,
        cyls=analyse_cylinders(part),
        include_cylindrical=True,
        writer=ledger.writer,
    )
    assert bool(measured) is accepted
    assert bool(ledger.candidate_set(FamilyId.FILLETS).candidates) is accepted


def test_maximum_radius_gate_retains_existing_whole_part_bbox_scale() -> None:
    blend = _prismatic_axis(Axis.Z, 5.0)
    alone = ClaimLedger(FaceGraph(blend))
    assert (
        _discover_fillets(
            blend,
            min_radius=None,
            max_radius_frac=0.1,
            face_edges=None,
            cyls=analyse_cylinders(blend),
            include_cylindrical=True,
            writer=alone.writer,
        )
        == []
    )
    assert alone.candidate_set(FamilyId.FILLETS).candidates == ()

    enlarged = blend + Pos(200, 0, 0) * Box(100, 100, 100)
    _ledger, measured = _claimed(enlarged, max_radius_frac=0.1)
    assert measured and {record.radius for record in measured} == {5.0}


@pytest.mark.parametrize(("part", "rotational"), [(_prismatic(), False), (_turned(), True)])
def test_aggregate_inventory_publishes_complete_fillet_evidence(part, rotational) -> None:
    product = _take_inventory(part, rotational=rotational)
    candidates = product.physical.candidate_set(FamilyId.FILLETS).candidates
    assert candidates
    assert tuple(candidate.record for candidate in candidates) == product.result.fillets
    assert all(len(product.evidence.defining_of(candidate)) == 1 for candidate in candidates)


def test_custom_radius_parameters_and_injected_dependencies_preserve_writer_parity() -> None:
    part = _prismatic()
    _ledger, measured = _claimed(part, min_radius=2.0, max_radius_frac=0.05, face_edges=FaceEdges())
    assert measured
    ledger = ClaimLedger(FaceGraph(part))
    assert (
        _discover_fillets(
            part,
            min_radius=2.1,
            max_radius_frac=0.049,
            face_edges=None,
            cyls=analyse_cylinders(part),
            include_cylindrical=True,
            writer=ledger.writer,
        )
        == []
    )
    assert ledger.candidate_set(FamilyId.FILLETS).candidates == ()


def test_nonprincipal_prismatic_rotation_remains_out_of_scope_without_publication() -> None:
    part = _prismatic().rotate(Axis.X, 37)
    ledger = ClaimLedger(FaceGraph(part))
    assert (
        _discover_fillets(
            part,
            min_radius=None,
            max_radius_frac=0.45,
            face_edges=None,
            cyls=analyse_cylinders(part),
            include_cylindrical=True,
            writer=ledger.writer,
        )
        == []
    )
    assert ledger.candidate_set(FamilyId.FILLETS).candidates == ()


def test_real_step_round_trip_preserves_fillet_roles(tmp_path) -> None:
    target = tmp_path / "fillets.step"
    assert export_step(_turned(), target)
    part = import_step(target)
    _ledger, measured = _claimed(part, include_cylindrical=False)
    assert measured and all(record.turned for record in measured)


def test_prismatic_step_round_trip_preserves_fillet_roles(tmp_path) -> None:
    target = tmp_path / "prismatic-fillets.step"
    assert export_step(_prismatic(), target)
    part = import_step(target)
    ledger, measured = _claimed(part)
    assert measured and all(not record.turned for record in measured)
    assert len(ledger.candidate_set(FamilyId.FILLETS).candidates) == len(measured)


def test_later_fillet_binding_failure_publishes_no_prefix(monkeypatch) -> None:
    part = _prismatic()
    ledger = ClaimLedger(FaceGraph(part))
    real_require = ledger.graph.require_node
    calls = 0

    def fail_second(face):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("later fillet binding failed")
        return real_require(face)

    monkeypatch.setattr(ledger.graph, "require_node", fail_second)
    with pytest.raises(ValueError, match="later fillet binding failed"):
        _discover_fillets(
            part,
            min_radius=None,
            max_radius_frac=0.45,
            face_edges=None,
            cyls=analyse_cylinders(part),
            include_cylindrical=True,
            writer=ledger.writer,
        )
    assert ledger.candidate_set(FamilyId.FILLETS).candidates == ()


def test_later_fillet_body_failure_publishes_no_prefix(monkeypatch) -> None:
    part = _prismatic()
    ledger = ClaimLedger(FaceGraph(part))
    real_common = ledger.graph.common_valid_solid
    calls = 0

    def fail_second(nodes):
        nonlocal calls
        calls += 1
        if calls == 2:
            return None
        return real_common(nodes)

    monkeypatch.setattr(ledger.graph, "common_valid_solid", fail_second)
    with pytest.raises(ValueError, match="no unambiguous valid solid"):
        _discover_fillets(
            part,
            min_radius=None,
            max_radius_frac=0.45,
            face_edges=None,
            cyls=analyse_cylinders(part),
            include_cylindrical=True,
            writer=ledger.writer,
        )
    assert ledger.candidate_set(FamilyId.FILLETS).candidates == ()


def test_turned_context_must_share_the_owner_solid_before_publication(monkeypatch) -> None:
    part = _turned()
    ledger = ClaimLedger(FaceGraph(part))
    real_common = ledger.graph.common_valid_solid

    def reject_owner_with_context(nodes):
        materialized = tuple(nodes)
        if len(materialized) > 1:
            return None
        return real_common(materialized)

    monkeypatch.setattr(ledger.graph, "common_valid_solid", reject_owner_with_context)
    with pytest.raises(ValueError, match="no unambiguous valid solid"):
        _discover_fillets(
            part,
            min_radius=None,
            max_radius_frac=0.45,
            face_edges=None,
            cyls=analyse_cylinders(part),
            include_cylindrical=False,
            writer=ledger.writer,
        )
    assert ledger.candidate_set(FamilyId.FILLETS).candidates == ()


def test_foreign_fillet_writer_refuses_without_publication() -> None:
    part = _prismatic()
    foreign = ClaimLedger(FaceGraph(_turned()))
    with pytest.raises(ValueError):
        _discover_fillets(
            part,
            min_radius=None,
            max_radius_frac=0.45,
            face_edges=None,
            cyls=analyse_cylinders(part),
            include_cylindrical=True,
            writer=foreign.writer,
        )
    assert foreign.candidate_set(FamilyId.FILLETS).candidates == ()


def test_open_fillet_topology_refuses_before_publication() -> None:
    part = _prismatic()
    shell = Shell(part.faces()[:-1])
    ledger = ClaimLedger(FaceGraph(shell))
    with pytest.raises(ValueError, match="no unambiguous valid solid"):
        _discover_fillets(
            shell,
            min_radius=None,
            max_radius_frac=0.45,
            face_edges=None,
            cyls=analyse_cylinders(shell),
            include_cylindrical=True,
            writer=ledger.writer,
        )
    assert ledger.candidate_set(FamilyId.FILLETS).candidates == ()


@pytest.mark.parametrize("translated", [False, True])
def test_deep_cloned_fillet_binding_refuses_before_publication(monkeypatch, translated) -> None:
    part = _prismatic()
    ledger = ClaimLedger(FaceGraph(part))
    real_require = ledger.graph.require_node

    def cloned(face):
        changed = copy.deepcopy(face)
        if translated:
            changed = changed.translate((1, 0, 0))
        return real_require(changed)

    monkeypatch.setattr(ledger.graph, "require_node", cloned)
    with pytest.raises(ValueError):
        _discover_fillets(
            part,
            min_radius=None,
            max_radius_frac=0.45,
            face_edges=None,
            cyls=analyse_cylinders(part),
            include_cylindrical=True,
            writer=ledger.writer,
        )
    assert ledger.candidate_set(FamilyId.FILLETS).candidates == ()


def test_reversed_face_traversal_preserves_occurrence_roles(monkeypatch) -> None:
    part = _prismatic()
    baseline = [record.to_dict() for record in recognise_fillets(part)]
    part_type = type(part)
    real_faces = part_type.faces

    def reversed_faces(self):
        faces = real_faces(self)
        return type(faces)(reversed(faces))

    monkeypatch.setattr(part_type, "faces", reversed_faces)
    _ledger, measured = _claimed(part)
    assert [record.to_dict() for record in measured] == baseline


@pytest.mark.parametrize(
    "part",
    [
        Cylinder(10, 20),
        Box(30, 30, 20) - Cylinder(5, 20),
        _internal_pocket_round(),
        _through_slot(),
    ],
)
def test_rejected_round_context_issues_no_fillet_candidate(part) -> None:
    ledger = ClaimLedger(FaceGraph(part))
    assert (
        _discover_fillets(
            part,
            min_radius=None,
            max_radius_frac=0.45,
            face_edges=None,
            cyls=analyse_cylinders(part),
            include_cylindrical=True,
            writer=ledger.writer,
        )
        == []
    )
    assert ledger.candidate_set(FamilyId.FILLETS).candidates == ()


@pytest.mark.parametrize(
    "part",
    [
        Cylinder(10, 20) + Torus(10, 2),
        Torus(10, 2),
        fillet(
            (Box(60, 60, 20) - Cylinder(5, 20)).edges().filter_by(GeomType.CIRCLE)[0],
            1.0,
        ),
        _turned().rotate(Axis.X, 37),
    ],
)
def test_rejected_toroidal_context_issues_no_fillet_candidate(part) -> None:
    ledger = ClaimLedger(FaceGraph(part))
    assert (
        _discover_fillets(
            part,
            min_radius=None,
            max_radius_frac=0.45,
            face_edges=None,
            cyls=analyse_cylinders(part),
            include_cylindrical=False,
            writer=ledger.writer,
        )
        == []
    )
    assert ledger.candidate_set(FamilyId.FILLETS).candidates == ()


def test_multiple_valid_solids_emit_independent_fillet_occurrences() -> None:
    part = Pos(0, -60, 0) * _prismatic() + Pos(0, 60, 0) * _prismatic()
    ledger, measured = _claimed(part)
    candidates = ledger.candidate_set(FamilyId.FILLETS).candidates
    assert len(candidates) == len(measured) == 8
    solids = [ledger.graph.common_valid_solid(ledger.defining_of(item)) for item in candidates]
    assert len({id(solid) for solid in solids}) == 2


def test_registry_is_the_only_production_writer_enabled_fillet_caller() -> None:
    package = Path(__file__).parents[1] / "src" / "b123d_recognisers"
    importers = set()
    for path in package.glob("*.py"):
        if path.name == "fillets.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        direct = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "b123d_recognisers.fillets"
            and any(alias.name == "_discover_fillets" for alias in node.names)
            for node in ast.walk(tree)
        )
        qualified = any(
            isinstance(node, ast.Attribute) and node.attr == "_discover_fillets"
            for node in ast.walk(tree)
        )
        if direct or qualified:
            importers.add(path.name)
    assert importers == {"_registry.py"}


def test_fillet_constructor_and_torus_branch_source_roster_is_frozen() -> None:
    source = Path(fillets_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    constructors = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Fillet"
    ]
    assert len(constructors) == 2
    assert "transverse_planes" in source
    assert "bridges_two_bands" in source
    assert "round_continuations" in source
