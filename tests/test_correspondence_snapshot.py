# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""F6a private body descriptors and accepted RRP snapshot authority."""

from __future__ import annotations

import ast
import copy
import dataclasses
import math
from collections.abc import Mapping
from itertools import permutations, product
from pathlib import Path

import pytest
from build123d import (
    Align,
    Box,
    Compound,
    Cylinder,
    Edge,
    Face,
    Plane,
    Polygon,
    Pos,
    Rot,
    Solid,
    Sphere,
    Vector,
    Wire,
    export_step,
    extrude,
    import_step,
)
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepGProp import BRepGProp
from OCP.gp import gp_Pnt2d, gp_Trsf
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_Orientation

import b123d_recognisers
from b123d_recognisers import _body_geometry
from b123d_recognisers import _correspondence as correspondence_module
from b123d_recognisers._adjacency import BodyGeometryAuthorityError, FaceGraph
from b123d_recognisers._body_geometry import (
    FaceGeometry,
    UnsupportedBodyGeometry,
    matching_boundary_for_solid,
)
from b123d_recognisers._candidates import EvidenceIndex, FamilyId
from b123d_recognisers._correspondence import (
    CORRESPONDENCE_FAMILIES,
    CorrespondenceSnapshotError,
    MatchingBoundaryGraph,
    MatchingCurve,
    MatchingFace,
    MatchingHalfEdge,
    MatchingWire,
    MatchingWireVertex,
    correspondence_snapshot,
)
from b123d_recognisers.result import _take_inventory

ROOT = Path(__file__).parents[1]


def _proper_signed_permutations():
    matrices = []
    for axes in permutations(range(3)):
        for signs in product((-1, 1), repeat=3):
            matrix = tuple(
                tuple(signs[row] if axes[row] == column else 0 for column in range(3))
                for row in range(3)
            )
            determinant = round(
                matrix[0][0]
                * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
                - matrix[0][1]
                * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
                + matrix[0][2]
                * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
            )
            if determinant == 1:
                matrices.append(matrix)
    return tuple(matrices)


def _proper_transform(part, matrix):
    transform = gp_Trsf()
    values = tuple(item for row in matrix for item in row)
    transform.SetValues(
        values[0], values[1], values[2], 0.0,
        values[3], values[4], values[5], 0.0,
        values[6], values[7], values[8], 0.0,
    )
    return Solid(BRepBuilderAPI_Transform(part.wrapped, transform, True).Shape())


def _apply_rotation(matrix, value):
    return tuple(
        sum(matrix[row][column] * value[column] for column in range(3))
        for row in range(3)
    )


def test_schema_three_matching_values_freeze_global_reference_shape() -> None:
    line = MatchingCurve("LINE", (0, 1), 1.0, None, None, None, None, False)
    circle = MatchingCurve(
        "CIRCLE",
        None,
        2.0 * math.pi,
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
        1.0,
        2.0 * math.pi,
        True,
    )
    start = MatchingWireVertex(0, (0.0, 0.0))
    end = MatchingWireVertex(1, (1.0, 0.0))
    line_use = MatchingHalfEdge(0, 1, start, end)
    full_use = MatchingHalfEdge(1, -1, None, None)
    wire = MatchingWire("outer", 0, (line_use, full_use))
    face = MatchingFace(
        "PLANE",
        (0.0, 0.0, 1.0, 0.0),
        1.0,
        (0.0, 0.0, 0.0),
        1,
        (wire,),
    )
    graph = MatchingBoundaryGraph(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        (line, circle),
        (face,),
        ((0, ((0, 0, 0),)), (1, ((0, 0, 1),))),
        1,
        1,
        2,
        False,
    )
    assert graph.curves[0].vertices == (0, 1)
    assert graph.curves[1].vertices is None
    assert graph.faces[0].wires[0].cycle[1].start is None


def test_line_plane_matching_graph_erases_face_and_edge_traversal_order(monkeypatch) -> None:
    part = Box(10, 20, 30)
    graph = FaceGraph(part)
    solid = graph.common_valid_solid(graph.nodes)
    assert solid is not None
    descriptor = graph.body_geometry(solid).descriptor
    source = matching_boundary_for_solid(part, descriptor)
    solid_faces = Solid.faces
    wire_edges = Wire.edges
    monkeypatch.setattr(Solid, "faces", lambda self: list(reversed(solid_faces(self))))
    monkeypatch.setattr(Wire, "edges", lambda self: list(reversed(wire_edges(self))))
    assert matching_boundary_for_solid(part, descriptor) == source
    assert source.face_count == 6
    assert source.wire_count == 6
    assert source.edge_occurrence_count == 24


def test_schema_three_box_half_edges_covary_under_all_24_proper_rotations() -> None:
    source_part = Box(10, 20, 30)
    source_graph = FaceGraph(source_part)
    source_solid = source_graph.common_valid_solid(source_graph.nodes)
    assert source_solid is not None
    source = source_graph.matching_boundary(source_solid)

    for rotation in _proper_signed_permutations():
        target_part = _proper_transform(source_part, rotation)
        target_graph = FaceGraph(target_part)
        target_solid = target_graph.common_valid_solid(target_graph.nodes)
        assert target_solid is not None
        target = target_graph.matching_boundary(target_solid)
        vertex_map = {
            index: min(
                range(len(target.vertices)),
                key=lambda other: math.dist(
                    _apply_rotation(rotation, vertex), target.vertices[other]
                ),
            )
            for index, vertex in enumerate(source.vertices)
        }
        assert len(set(vertex_map.values())) == len(source.vertices)
        face_map = {
            index: min(
                range(len(target.faces)),
                key=lambda other: math.dist(
                    _apply_rotation(rotation, face.centroid), target.faces[other].centroid
                ),
            )
            for index, face in enumerate(source.faces)
        }
        assert len(set(face_map.values())) == len(source.faces)
        curve_map = {}
        presentation = {}
        for index, curve in enumerate(source.curves):
            assert curve.kind == "LINE" and curve.vertices is not None
            transformed = tuple(vertex_map[item] for item in curve.vertices)
            matches = tuple(
                other
                for other, candidate in enumerate(target.curves)
                if candidate.kind == "LINE"
                and candidate.vertices is not None
                and set(candidate.vertices) == set(transformed)
            )
            assert len(matches) == 1
            curve_map[index] = matches[0]
            presentation[index] = (
                1 if target.curves[matches[0]].vertices == transformed else -1
            )
        mapped = sorted(
            (
                face_map[face_index],
                curve_map[half_edge.curve],
                half_edge.direction * presentation[half_edge.curve],
            )
            for face_index, face in enumerate(source.faces)
            for wire in face.wires
            for half_edge in wire.cycle
        )
        expected = sorted(
            (face_index, half_edge.curve, half_edge.direction)
            for face_index, face in enumerate(target.faces)
            for wire in face.wires
            for half_edge in wire.cycle
        )
        assert mapped == expected


def test_planar_full_circle_cycle_has_no_serialized_seam() -> None:
    face = FaceGeometry(
        "PLANE",
        (0.0, 0.0, 1.0, 0.0),
        math.pi,
        (0.0, 0.0, 0.0),
        1,
        (),
    )
    curve = MatchingCurve(
        "CIRCLE",
        None,
        2.0 * math.pi,
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
        1.0,
        2.0 * math.pi,
        True,
    )

    wire = _body_geometry._planar_cycle(
        (0,), (curve,), "outer", face, 1e-9, ()
    )

    assert wire == MatchingWire(
        "outer", 0, (MatchingHalfEdge(0, 1, None, None),)
    )

    reversed_material = dataclasses.replace(face, material_side=-1)
    reversed_wire = _body_geometry._planar_cycle(
        (0,), (curve,), "outer", reversed_material, 1e-9, ()
    )
    assert reversed_wire.cycle[0].direction == -1


def test_planar_trimmed_circle_integral_reconstructs_the_arc() -> None:
    face = FaceGeometry(
        "PLANE",
        (0.0, 0.0, 1.0, 0.0),
        1.0,
        (0.0, 0.0, 0.0),
        1,
        (),
    )
    curve = MatchingCurve(
        "CIRCLE",
        (0, 1),
        0.5 * math.pi,
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
        1.0,
        0.5 * math.pi,
        False,
    )
    half_edge = MatchingHalfEdge(
        0,
        1,
        MatchingWireVertex(0, (1.0, 0.0)),
        MatchingWireVertex(1, (0.0, 1.0)),
    )

    assert _body_geometry._half_edge_integral(
        half_edge, (curve,), face, 1e-9
    ) == pytest.approx(0.25 * math.pi)


def test_cylindrical_seam_matching_graph_erases_wire_presentation(monkeypatch) -> None:
    part = Cylinder(10, 20)
    graph = FaceGraph(part)
    solid = graph.common_valid_solid(graph.nodes)
    assert solid is not None
    descriptor = graph.body_geometry(solid).descriptor
    source = matching_boundary_for_solid(part, descriptor)

    wire_edges = Wire.edges
    monkeypatch.setattr(Wire, "edges", lambda self: list(reversed(wire_edges(self))))

    assert matching_boundary_for_solid(part, descriptor) == source
    cylinder = next(face for face in source.faces if face.kind == "CYLINDER")
    assert cylinder.wires[0].theta_winding == 0
    seam_uses = tuple(
        item
        for item in cylinder.wires[0].cycle
        if source.curves[item.curve].kind == "LINE"
    )
    assert len(seam_uses) == 2
    assert seam_uses[0].curve == seam_uses[1].curve
    seam_thetas = sorted(
        item.start.parameter[0] for item in seam_uses if item.start is not None
    )
    assert seam_thetas == pytest.approx((0.0, 2.0 * math.pi), abs=_body_geometry.ANGLE_TOL)


def test_schema_three_matching_incidence_mutation_refuses() -> None:
    snapshot = correspondence_snapshot(_take_inventory(_rrp()))
    occurrence = snapshot.occurrences[0]
    matching = occurrence.matching_boundary
    malformed = dataclasses.replace(matching, incidence=())
    changed_occurrence = dataclasses.replace(occurrence, matching_boundary=malformed)
    changed = dataclasses.replace(snapshot, occurrences=(changed_occurrence,))

    with pytest.raises(CorrespondenceSnapshotError, match="matching boundary"):
        correspondence_module._validate_snapshot(changed)


@pytest.mark.parametrize("mutation", ["curve", "parameter", "material"])
def test_schema_three_nested_value_mutation_refuses(mutation: str) -> None:
    occurrence = correspondence_snapshot(_take_inventory(_rrp())).occurrences[0]
    graph = occurrence.matching_boundary
    if mutation == "curve":
        curve = graph.curves[0]
        changed = dataclasses.replace(
            graph, curves=(dataclasses.replace(curve, length=math.nan), *graph.curves[1:])
        )
    else:
        face = graph.faces[0]
        if mutation == "parameter":
            face_index, wire_index, half_edge_index = next(
                (face_index, wire_index, half_edge_index)
                for face_index, candidate_face in enumerate(graph.faces)
                for wire_index, candidate_wire in enumerate(candidate_face.wires)
                for half_edge_index, candidate in enumerate(candidate_wire.cycle)
                if candidate.start is not None
            )
            face = graph.faces[face_index]
            wire = face.wires[wire_index]
            half_edge = wire.cycle[half_edge_index]
            assert half_edge.start is not None
            start = dataclasses.replace(half_edge.start, parameter=(math.nan, 0.0))
            changed_half_edge = dataclasses.replace(half_edge, start=start)
            changed_wire = dataclasses.replace(
                wire,
                cycle=tuple(
                    changed_half_edge if index == half_edge_index else item
                    for index, item in enumerate(wire.cycle)
                ),
            )
            changed_face = dataclasses.replace(
                face,
                wires=tuple(
                    changed_wire if index == wire_index else item
                    for index, item in enumerate(face.wires)
                ),
            )
        else:
            changed_face = dataclasses.replace(face, material_side=0)
        changed = dataclasses.replace(
            graph,
            faces=tuple(
                changed_face if item is face else item for item in graph.faces
            ),
        )
    with pytest.raises(UnsupportedBodyGeometry, match="matching"):
        _body_geometry.validate_matching_boundary_graph(changed)


def test_schema_three_pcurve_reconstruction_refuses_displaced_surface_values(
    monkeypatch,
) -> None:
    face = Box(2, 3, 4).faces()[0]
    edge = face.edges()[0]
    original = _body_geometry.BRepAdaptor_Curve2d(edge.wrapped, face.wrapped)
    first = original.FirstParameter()
    last = original.LastParameter()

    class DisplacedPcurve:
        @staticmethod
        def FirstParameter():
            return first

        @staticmethod
        def LastParameter():
            return last

        @staticmethod
        def Value(_parameter):
            return gp_Pnt2d(1_000.0, 1_000.0)

    monkeypatch.setattr(
        _body_geometry, "BRepAdaptor_Curve2d", lambda _edge, _face: DisplacedPcurve()
    )
    with pytest.raises(UnsupportedBodyGeometry, match="does not reconstruct"):
        _body_geometry._validate_matching_pcurve(edge, face, 1e-7)


def test_schema_three_construction_budget_is_inclusive() -> None:
    budget = _body_geometry._MatchingConstructionBudget(
        _body_geometry.CANONICAL_SERIALIZATION_BUDGET - 1
    )
    budget.charge()
    assert budget.attempts == _body_geometry.CANONICAL_SERIALIZATION_BUDGET
    with pytest.raises(UnsupportedBodyGeometry, match="construction budget"):
        budget.charge()


def test_schema_three_joint_canonicalization_preserves_equal_topology_tokens() -> None:
    vertices = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    curves = (
        MatchingCurve("LINE", (0, 1), 1.0, None, None, None, None, False),
        MatchingCurve("LINE", (0, 1), 1.0, None, None, None, None, False),
    )
    parameter = (0.0, 0.0)
    faces = tuple(
        MatchingFace(
            "PLANE",
            (0.0, 0.0, 1.0, 0.0),
            1.0,
            (0.0, 0.0, 0.0),
            1,
            (
                MatchingWire(
                    "outer",
                    0,
                    (
                        MatchingHalfEdge(
                            curve,
                            1,
                            MatchingWireVertex(0, parameter),
                            MatchingWireVertex(1, parameter),
                        ),
                        MatchingHalfEdge(
                            curve,
                            -1,
                            MatchingWireVertex(1, parameter),
                            MatchingWireVertex(0, parameter),
                        ),
                    ),
                ),
            ),
        )
        for curve in range(2)
    )

    graph = _body_geometry._matching_graph_canonical(
        vertices, curves, faces, _body_geometry._MatchingConstructionBudget()
    )

    assert len(graph.vertices) == 2
    assert len(graph.curves) == 2
    assert graph.symmetric
    _body_geometry.validate_matching_boundary_graph(graph)


def _rrp(repeats: int = 5):
    part = Cylinder(20, 10)
    for index in range(repeats):
        part -= Rot(0, 0, 360 * index / repeats) * Pos(18, 0, 0) * Box(8, 3, 10)
    return part


@pytest.mark.parametrize("repeats", [5, 7])
def test_schema_three_rrp_half_edges_covary_under_all_24_proper_rotations(
    repeats: int,
) -> None:
    source_part = _rrp(repeats)
    source_graph = FaceGraph(source_part)
    source_solid = source_graph.common_valid_solid(source_graph.nodes)
    assert source_solid is not None
    source = source_graph.matching_boundary(source_solid)
    for rotation in _proper_signed_permutations():
        target_part = _proper_transform(source_part, rotation)
        target_graph = FaceGraph(target_part)
        target_solid = target_graph.common_valid_solid(target_graph.nodes)
        assert target_solid is not None
        target = target_graph.matching_boundary(target_solid)
        vertex_map = {
            index: min(
                range(len(target.vertices)),
                key=lambda other: math.dist(
                    _apply_rotation(rotation, vertex), target.vertices[other]
                ),
            )
            for index, vertex in enumerate(source.vertices)
        }
        assert len(set(vertex_map.values())) == len(source.vertices)
        curve_map = {}
        presentation = {}
        for index, curve in enumerate(source.curves):
            transformed_vertices = (
                None
                if curve.vertices is None
                else tuple(vertex_map[item] for item in curve.vertices)
            )
            transformed_centre = (
                None
                if curve.centre is None
                else _apply_rotation(rotation, curve.centre)
            )
            matches = tuple(
                other
                for other, candidate in enumerate(target.curves)
                if candidate.kind == curve.kind
                and abs(candidate.length - curve.length) < 1e-5
                and (
                    (
                        transformed_vertices is not None
                        and candidate.vertices is not None
                        and set(candidate.vertices) == set(transformed_vertices)
                    )
                    or (
                        transformed_vertices is None
                        and candidate.vertices is None
                        and candidate.centre is not None
                        and transformed_centre is not None
                        and math.dist(candidate.centre, transformed_centre) < 1e-5
                        and candidate.radius == pytest.approx(curve.radius, abs=1e-5)
                    )
                )
            )
            assert len(matches) == 1
            target_index = matches[0]
            curve_map[index] = target_index
            if transformed_vertices is not None:
                presentation[index] = (
                    1
                    if target.curves[target_index].vertices == transformed_vertices
                    else -1
                )
            else:
                assert curve.axis is not None
                transformed_axis = _apply_rotation(rotation, curve.axis)
                gauge = -1 if next(item for item in transformed_axis if item != 0.0) < 0 else 1
                presentation[index] = gauge
        face_map = {}
        for index, face in enumerate(source.faces):
            transformed_centre = _apply_rotation(rotation, face.centroid)
            matches = tuple(
                other
                for other, candidate in enumerate(target.faces)
                if candidate.kind == face.kind
                and abs(candidate.area - face.area) < 1e-4
                and math.dist(candidate.centroid, transformed_centre) < 1e-4
            )
            assert len(matches) == 1
            face_map[index] = matches[0]
        mapped = sorted(
            (
                face_map[face_index],
                curve_map[half_edge.curve],
                half_edge.direction * presentation[half_edge.curve],
            )
            for face_index, face in enumerate(source.faces)
            for wire in face.wires
            for half_edge in wire.cycle
        )
        expected = sorted(
            (face_index, half_edge.curve, half_edge.direction)
            for face_index, face in enumerate(target.faces)
            for wire in face.wires
            for half_edge in wire.cycle
        )
        assert mapped == expected


def _line_rrp(repeats: int):
    points = []
    for sector in range(repeats):
        for offset, radius in enumerate((20.0, 16.0, 20.0, 18.0)):
            angle = 2 * math.pi * (sector / repeats + offset / (4 * repeats))
            points.append((radius * math.cos(angle), radius * math.sin(angle)))
    return extrude(Polygon(*points), 10)


def _two_rrp_one_solid():
    left = Pos(-35, 0, 0) * _line_rrp(5)
    right = Pos(35, 0, 0) * _line_rrp(7)
    bridge = Pos(0, 0, 5) * Box(40, 4, 2, align=(Align.CENTER, Align.CENTER, Align.CENTER))
    part = left + right + bridge
    assert len(part.solids()) == 1
    return part


def _body_descriptor(part):
    graph = FaceGraph(part)
    solid = graph.common_valid_solid(graph.nodes)
    assert solid is not None
    return graph, solid, graph.body_geometry(solid)


def _raw_body_oracle(part):
    """Fresh raw-kernel facts collected before any production descriptor is read."""

    solids = tuple(part.solids())
    assert len(solids) == 1
    solid = solids[0]
    volume = GProp_GProps()
    surface_props = GProp_GProps()
    BRepGProp.VolumeProperties_s(solid.wrapped, volume)
    BRepGProp.SurfaceProperties_s(solid.wrapped, surface_props)
    faces = tuple(solid.faces())
    centre = tuple(float(value) for value in volume.CentreOfMass().Coord())
    face_geometry = []
    occurrence_tokens = []
    for face in faces:
        surface_adaptor = BRepAdaptor_Surface(face.wrapped)
        surface_kind = surface_adaptor.GetType().name.removeprefix("GeomAbs_").upper()
        if surface_kind == "PLANE":
            surface = surface_adaptor.Plane()
            raw_axis = _oracle_axis_raw(surface.Axis().Direction().Coord())
            axis = tuple(map(_rounded, raw_axis))
            location = tuple(float(value) for value in surface.Location().Coord())
            parameters = (
                *axis,
                _rounded(
                    sum(
                        direction * (value - origin)
                        for direction, value, origin in zip(raw_axis, location, centre, strict=True)
                    )
                ),
            )
        elif surface_kind == "CYLINDER":
            surface = surface_adaptor.Cylinder()
            raw_axis = _oracle_axis_raw(surface.Axis().Direction().Coord())
            axis = tuple(map(_rounded, raw_axis))
            location = tuple(float(value) for value in surface.Location().Coord())
            delta = tuple(value - origin for value, origin in zip(location, centre, strict=True))
            along = sum(value * direction for value, direction in zip(delta, raw_axis, strict=True))
            closest = tuple(
                value - along * direction for value, direction in zip(delta, raw_axis, strict=True)
            )
            parameters = (*axis, *map(_rounded, closest), _rounded(surface.Radius()))
        else:
            parameters = ()
        face_centre = face.center()
        normal = face.normal_at(face_centre)
        if surface_kind == "PLANE":
            gauge = parameters[:3]
            material_side = 1 if sum(a * b for a, b in zip(gauge, normal, strict=True)) >= 0 else -1
        else:
            gauge = parameters[:3]
            location = tuple(
                float(value) for value in surface_adaptor.Cylinder().Location().Coord()
            )
            sample_delta = tuple(
                value - origin for value, origin in zip(face_centre, location, strict=True)
            )
            along = sum(
                value * direction for value, direction in zip(sample_delta, gauge, strict=True)
            )
            radial = tuple(
                value - along * direction
                for value, direction in zip(sample_delta, gauge, strict=True)
            )
            material_side = (
                1 if sum(a * b for a, b in zip(radial, normal, strict=True)) >= 0 else -1
            )

        outer = face.outer_wire()
        wire_entries = []
        for wire in face.wires():
            edges = []
            for edge in wire.edges():
                curve = BRepAdaptor_Curve(edge.wrapped)
                kind = curve.GetType().name.removeprefix("GeomAbs_").upper()
                start = tuple(
                    _rounded(value - origin)
                    for value, origin in zip(tuple(edge.position_at(0)), centre, strict=True)
                )
                end = tuple(
                    _rounded(value - origin)
                    for value, origin in zip(tuple(edge.position_at(1)), centre, strict=True)
                )
                centre_label: tuple[float, ...] = ()
                axis_label: tuple[float, ...] = ()
                radius = 0.0
                sweep = 0.0
                full = False
                if kind == "CIRCLE":
                    raw = curve.Circle()
                    centre_label = tuple(
                        _rounded(value - origin)
                        for value, origin in zip(raw.Location().Coord(), centre, strict=True)
                    )
                    raw_axis = tuple(float(value) for value in raw.Axis().Direction().Coord())
                    canonical_axis = _oracle_axis_raw(raw_axis)
                    axis_sign = 1 if canonical_axis == raw_axis else -1
                    axis_label = tuple(map(_rounded, canonical_axis))
                    radius = _rounded(raw.Radius())
                    magnitude = float(edge.length) / float(raw.Radius())
                    midpoint = tuple(edge.position_at(0.5))
                    raw_centre = tuple(float(value) for value in raw.Location().Coord())
                    first_vector = tuple(
                        value - origin
                        for value, origin in zip(
                            tuple(edge.position_at(0)), raw_centre, strict=True
                        )
                    )
                    middle_vector = tuple(
                        value - origin for value, origin in zip(midpoint, raw_centre, strict=True)
                    )
                    cross = (
                        first_vector[1] * middle_vector[2] - first_vector[2] * middle_vector[1],
                        first_vector[2] * middle_vector[0] - first_vector[0] * middle_vector[2],
                        first_vector[0] * middle_vector[1] - first_vector[1] * middle_vector[0],
                    )
                    raw_sweep = (
                        magnitude
                        if sum(a * b for a, b in zip(cross, raw_axis, strict=True)) >= 0
                        else -magnitude
                    )
                    sweep = _rounded(axis_sign * raw_sweep)
                    full = abs(abs(raw_sweep) - 2 * math.pi) <= _body_geometry.ANGLE_TOL
                first = (start, end, sweep)
                second = (end, start, -sweep)
                canonical_start, canonical_end, canonical_sweep = min(first, second)
                label = (
                    kind,
                    canonical_start,
                    canonical_end,
                    _rounded(edge.length),
                    centre_label,
                    axis_label,
                    radius,
                    canonical_sweep,
                    full,
                )
                direction = (
                    -1 if edge.wrapped.Orientation() == TopAbs_Orientation.TopAbs_REVERSED else 1
                )
                edges.append((label, direction, edge))
            raw_wire_orientation = (
                -1 if wire.wrapped.Orientation() == TopAbs_Orientation.TopAbs_REVERSED else 1
            )
            canonical, semantic, alignments = _oracle_cycle(
                tuple(edges), raw_wire_orientation * material_side
            )
            wire_entries.append(
                (("outer" if wire == outer else "inner", semantic, canonical), alignments)
            )
        wire_entries.sort(key=lambda item: item[0])
        wires = tuple(item[0] for item in wire_entries)
        occurrence_tokens.extend(item[1] for item in wire_entries)
        face_label = (
            surface_kind,
            tuple(_rounded(value) for value in parameters),
            _rounded(face.area),
            tuple(
                _rounded(value - origin)
                for value, origin in zip(tuple(face_centre), centre, strict=True)
            ),
            material_side,
            wires,
        )
        face_geometry.append(face_label)

    ordered_faces = tuple(sorted(face_geometry))
    assert len(set(ordered_faces)) == len(ordered_faces), "oracle fixture needs unique face labels"
    face_indices = {label: index for index, label in enumerate(ordered_faces)}
    token_occurrences: dict[object, list[tuple[int, int, int, int]]] = {}
    token_labels: dict[object, object] = {}
    alignment_candidates = []
    for chosen_alignments in product(*occurrence_tokens):
        token_occurrences = {}
        token_labels = {}
        token_index = 0
        valid = True
        for face_label in face_geometry:
            canonical_face_index = face_indices[face_label]
            for wire_index, wire in enumerate(face_label[-1]):
                tokens = chosen_alignments[token_index]
                token_index += 1
                for edge_index, ((edge_label, direction), token) in enumerate(
                    zip(wire[2], tokens, strict=True)
                ):
                    prior = token_labels.setdefault(token, edge_label)
                    if prior != edge_label:
                        valid = False
                        break
                    token_occurrences.setdefault(token, []).append(
                        (canonical_face_index, wire_index, edge_index, direction)
                    )
                if not valid:
                    break
            if not valid:
                break
        if valid:
            alignment_candidates.append(
                tuple(
                    sorted(
                        (token_labels[token], tuple(sorted(items)))
                        for token, items in token_occurrences.items()
                    )
                )
            )
    assert alignment_candidates, "oracle found no consistent physical alignment"
    canonical_incidence = min(alignment_candidates)
    return {
        "volume": float(volume.Mass()),
        "surface_area": float(surface_props.Mass()),
        "centre": centre,
        "moments": tuple(sorted(float(value) for value in volume.PrincipalProperties().Moments())),
        "face_count": len(faces),
        "wire_count": sum(len(tuple(face.wires())) for face in faces),
        "edge_occurrence_count": sum(
            len(tuple(wire.edges())) for face in faces for wire in face.wires()
        ),
        "faces": ordered_faces,
        "incidence": canonical_incidence,
    }


def _rounded(value: float) -> float:
    result = round(float(value), 4)
    return 0.0 if result == 0.0 else result


def _oracle_axis(values) -> tuple[float, float, float]:
    return tuple(map(_rounded, _oracle_axis_raw(values)))  # type: ignore[return-value]


def _oracle_axis_raw(values) -> tuple[float, float, float]:
    axis = tuple(float(value) for value in values)
    sign = next((1 if value > 0 else -1 for value in axis if abs(value) >= 1e-10), 1)
    return tuple(sign * value for value in axis)  # type: ignore[return-value]


def _oracle_cycle(items, raw_orientation: int):
    candidates = []
    for reversed_presentation, source in (
        (False, items),
        (True, tuple((label, -direction, token) for label, direction, token in reversed(items))),
    ):
        for index in range(len(source)):
            rotated = source[index:] + source[:index]
            label = tuple((edge, direction) for edge, direction, _token in rotated)
            tokens = tuple(token for _edge, _direction, token in rotated)
            semantic = raw_orientation * (-1 if reversed_presentation else 1)
            candidates.append((label, semantic, tokens))
    canonical = min(label for label, _semantic, _tokens in candidates)
    matching = tuple(item for item in candidates if item[0] == canonical)
    semantics = {semantic for _label, semantic, _tokens in matching}
    assert len(semantics) == 1
    alignments = tuple({tokens for _label, semantic, tokens in matching if semantic in semantics})
    return canonical, semantics.pop(), alignments


def _descriptor_face_payload(face: FaceGeometry):
    wires = []
    for wire in face.wires:
        edges = []
        for edge, _direction in wire.edges:
            edges.append(_descriptor_edge_payload(edge))
        wires.append(
            (
                wire.role,
                wire.semantic_winding,
                tuple(zip(edges, (direction for _edge, direction in wire.edges), strict=True)),
            )
        )
    return (
        face.kind,
        tuple(map(_rounded, face.parameters)),
        _rounded(face.area),
        tuple(map(_rounded, face.centroid)),
        face.material_side,
        tuple(sorted(wires)),
    )


def _descriptor_edge_payload(edge):
    return (
        edge.kind,
        tuple(map(_rounded, edge.start)),
        tuple(map(_rounded, edge.end)),
        _rounded(edge.length),
        tuple(map(_rounded, edge.centre or ())),
        tuple(map(_rounded, edge.axis or ())),
        _rounded(edge.radius or 0.0),
        _rounded(edge.sweep or 0.0),
        edge.full,
    )


def _structure(value):
    if dataclasses.is_dataclass(value):
        fields = tuple(_structure(getattr(value, item.name)) for item in dataclasses.fields(value))
        return type(value).__name__, fields
    if isinstance(value, tuple):
        return tuple(_structure(item) for item in value)
    return "float" if isinstance(value, float) else value


def _numbers(value) -> tuple[float, ...]:
    if dataclasses.is_dataclass(value):
        return tuple(
            number
            for item in dataclasses.fields(value)
            for number in _numbers(getattr(value, item.name))
        )
    if isinstance(value, (tuple, list)):
        return tuple(number for item in value for number in _numbers(item))
    if isinstance(value, Mapping):
        return tuple(number for item in value.values() for number in _numbers(item))
    return (value,) if isinstance(value, float) else ()


def _alias_aware_calls(tree: ast.AST, target: str) -> tuple[ast.Call, ...]:
    """Find direct, qualified, imported, rebound and re-exported calls by leaf identity."""

    aliases = {target}
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            introduced: str | None = None
            source: str | None = None
            if isinstance(node, ast.ImportFrom):
                for item in node.names:
                    if item.name in aliases:
                        introduced = item.asname or item.name
                        source = item.name
                        break
            elif isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(
                node.value, (ast.Name, ast.Attribute)
            ):
                source = node.value.id if isinstance(node.value, ast.Name) else node.value.attr
                targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
                introduced = next((item.id for item in targets if isinstance(item, ast.Name)), None)
            if source in aliases and introduced is not None and introduced not in aliases:
                aliases.add(introduced)
                changed = True
    return tuple(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id in aliases)
            or (isinstance(node.func, ast.Attribute) and node.func.attr in aliases)
        )
    )


def test_body_geometry_is_translation_normalized_and_cached() -> None:
    graph, solid, source = _body_descriptor(_rrp())
    translated_graph, translated_solid, translated = _body_descriptor(Pos(7, 8, 9) * _rrp())

    assert graph.body_geometry(solid) is source
    assert source.descriptor.intrinsic == translated.descriptor.intrinsic
    assert source.descriptor.boundary == translated.descriptor.boundary
    assert graph.matching_boundary(solid) == translated_graph.matching_boundary(translated_solid)
    assert translated.descriptor.placement.centre_of_mass == pytest.approx((7.0, 8.0, 9.0))
    assert source.descriptor.placement != translated.descriptor.placement
    assert translated_graph is not graph


@pytest.mark.parametrize(
    ("transform", "expected_axis"),
    [
        (Pos(0, 0, 0), (0.0, 0.0, 1.0)),
        (Rot(0, 90, 0), (1.0, 0.0, 0.0)),
        (Rot(90, 0, 0), (0.0, 1.0, 0.0)),
    ],
)
def test_raw_ocp_oracle_independently_reconstructs_mass_and_topology(
    transform, expected_axis
) -> None:
    part = transform * _rrp(7)
    oracle = _raw_body_oracle(part)
    _graph, _solid, fact = _body_descriptor(part)

    scale = max(oracle["volume"] ** (1 / 3), math.sqrt(oracle["surface_area"]))
    metric = _body_geometry._metric_tolerance(scale)
    area_quantum = (scale + metric) ** 2 - scale**2
    volume_quantum = (scale + metric) ** 3 - scale**3
    moment_quantum = (scale + metric) ** 5 - scale**5
    assert abs(fact.descriptor.intrinsic.volume - oracle["volume"]) <= 2 * volume_quantum
    assert abs(fact.descriptor.intrinsic.surface_area - oracle["surface_area"]) <= 2 * area_quantum
    assert all(
        abs(actual - expected) <= 2 * moment_quantum
        for actual, expected in zip(
            fact.descriptor.intrinsic.principal_moments, oracle["moments"], strict=True
        )
    )
    assert fact.descriptor.placement.centre_of_mass == pytest.approx(oracle["centre"])
    assert fact.descriptor.boundary.face_count == oracle["face_count"]
    assert fact.descriptor.boundary.wire_count == oracle["wire_count"]
    assert fact.descriptor.boundary.edge_occurrence_count == oracle["edge_occurrence_count"]
    assert (
        tuple(sorted(map(_descriptor_face_payload, fact.descriptor.boundary.faces)))
        == oracle["faces"]
    )
    actual_incidence = tuple(
        sorted(
            (_descriptor_edge_payload(edge), occurrences)
            for edge, occurrences in fact.descriptor.boundary.incidence
        )
    )
    assert oracle["incidence"] == actual_incidence
    assert all(len(occurrences) == 2 for _edge, occurrences in oracle["incidence"])

    occurrence = correspondence_snapshot(_take_inventory(part)).occurrences[0]
    oracle_caps = tuple(
        face for face in oracle["faces"] if face[0] == "PLANE" and face[1][:3] == expected_axis
    )
    assert len(oracle_caps) == 2
    assert tuple(sorted(map(_descriptor_face_payload, occurrence.summary.defining))) == tuple(
        sorted(oracle_caps)
    )


def test_raw_oracle_enumerates_tied_outer_inner_and_seam_alignments() -> None:
    part = Cylinder(10, 5) - Cylinder(3, 5)
    oracle = _raw_body_oracle(part)
    descriptor = _body_descriptor(part)[2].descriptor
    assert oracle["faces"] == tuple(
        sorted(map(_descriptor_face_payload, descriptor.boundary.faces))
    )
    assert oracle["incidence"] == tuple(
        sorted(
            (_descriptor_edge_payload(edge), occurrences)
            for edge, occurrences in descriptor.boundary.incidence
        )
    )


def test_scalar_intrinsic_is_rigid_motion_invariant_but_boundary_is_world_oriented() -> None:
    _source_graph, _source_solid, source = _body_descriptor(_rrp())
    _turned_graph, _turned_solid, turned = _body_descriptor(Rot(13, 27, 9) * _rrp())

    assert source.descriptor.intrinsic == turned.descriptor.intrinsic
    assert source.descriptor.boundary != turned.descriptor.boundary

    _thin_graph, _thin_solid, thin = _body_descriptor(Box(100, 2, 0.5))
    _thin_rotated_graph, _thin_rotated_solid, thin_rotated = _body_descriptor(
        Rot(31, 17, 23) * Box(100, 2, 0.5)
    )
    assert thin.descriptor.intrinsic == thin_rotated.descriptor.intrinsic


def test_uniform_scale_obeys_mass_property_powers() -> None:
    _source_graph, _source_solid, source = _body_descriptor(_rrp())
    _scaled_graph, _scaled_solid, scaled = _body_descriptor(_rrp().scale(2))

    assert scaled.descriptor.intrinsic.volume == pytest.approx(
        8 * source.descriptor.intrinsic.volume, rel=1e-6
    )
    assert scaled.descriptor.intrinsic.surface_area == pytest.approx(
        4 * source.descriptor.intrinsic.surface_area, rel=1e-6
    )
    assert scaled.descriptor.intrinsic.principal_moments == pytest.approx(
        tuple(32 * value for value in source.descriptor.intrinsic.principal_moments),
        rel=5e-6,
    )


def test_mirror_and_translation_snapshots_preserve_intrinsic_multiplicity() -> None:
    source = correspondence_snapshot(_take_inventory(_line_rrp(8))).occurrences[0]
    mirrored = correspondence_snapshot(_take_inventory(_line_rrp(8).mirror(Plane.YZ))).occurrences[
        0
    ]
    translated = correspondence_snapshot(
        _take_inventory(Pos(17, -13, 29) * _line_rrp(8))
    ).occurrences[0]

    assert mirrored.body.intrinsic == source.body.intrinsic
    assert translated.body.intrinsic == source.body.intrinsic
    assert translated.body.boundary == source.body.boundary
    assert translated.body.placement.centre_of_mass == pytest.approx((17.0, -13.0, 34.0))


def test_representation_preserving_step_round_trip_has_the_same_descriptor(tmp_path) -> None:
    source = _rrp()
    target = tmp_path / "rrp.step"
    assert export_step(source, target)
    imported = import_step(target)

    _native_graph, _native_solid, native = _body_descriptor(source)
    _step_graph, _step_solid, stepped = _body_descriptor(imported)
    assert _structure(stepped.descriptor) == _structure(native.descriptor)
    assert _numbers(stepped.descriptor) == pytest.approx(
        _numbers(native.descriptor), rel=1e-8, abs=1e-7
    )
    assert stepped.descriptor.placement.centre_of_mass == pytest.approx(
        native.descriptor.placement.centre_of_mass, abs=1e-9
    )
    native_occurrence = correspondence_snapshot(_take_inventory(source)).occurrences[0]
    stepped_occurrence = correspondence_snapshot(_take_inventory(imported)).occurrences[0]
    assert native_occurrence.family == stepped_occurrence.family
    assert native_occurrence.record_type == stepped_occurrence.record_type
    assert native_occurrence.summary.repeat_count == stepped_occurrence.summary.repeat_count
    assert native_occurrence.summary.axis == stepped_occurrence.summary.axis
    assert _structure(native_occurrence.summary) == _structure(stepped_occurrence.summary)
    assert _numbers(native_occurrence.summary) == pytest.approx(
        _numbers(stepped_occurrence.summary), rel=1e-8, abs=1e-7
    )


def test_uniform_scale_snapshot_preserves_occurrence_and_named_powers() -> None:
    source = correspondence_snapshot(_take_inventory(_line_rrp(5))).occurrences[0]
    scaled = correspondence_snapshot(_take_inventory(_line_rrp(5).scale(2))).occurrences[0]
    assert scaled.summary.repeat_count == source.summary.repeat_count
    assert scaled.summary.axis == source.summary.axis
    assert scaled.body.intrinsic.volume == pytest.approx(8 * source.body.intrinsic.volume, rel=1e-6)
    assert scaled.body.intrinsic.surface_area == pytest.approx(
        4 * source.body.intrinsic.surface_area, rel=1e-6
    )
    assert scaled.summary.span == pytest.approx(
        tuple(2 * value for value in source.summary.span), rel=1e-6
    )


def test_face_and_cyclic_wire_traversal_permutations_are_descriptor_neutral(
    monkeypatch,
) -> None:
    part = _line_rrp(8)
    source = _body_descriptor(part)[2].descriptor
    solid_faces = Solid.faces
    wire_edges = Wire.edges

    monkeypatch.setattr(Solid, "faces", lambda self: list(reversed(solid_faces(self))))

    def shifted(self):
        edges = list(wire_edges(self))
        return edges[1:] + edges[:1] if edges else edges

    monkeypatch.setattr(Wire, "edges", shifted)
    permuted = _body_descriptor(part)[2].descriptor
    assert permuted == source


def test_whole_wire_reversal_with_reversed_half_edges_is_descriptor_neutral(
    monkeypatch,
) -> None:
    part = _line_rrp(5)
    source = _body_descriptor(part)[2].descriptor
    wire_edges = Wire.edges
    wire_orientation = _body_geometry._wire_orientation

    def reversed_wrapper(self):
        return [edge.reversed() for edge in reversed(wire_edges(self))]

    monkeypatch.setattr(Wire, "edges", reversed_wrapper)
    monkeypatch.setattr(_body_geometry, "_wire_orientation", lambda wire: -wire_orientation(wire))
    assert _body_descriptor(part)[2].descriptor == source


def test_controlled_material_face_reversal_changes_physical_orientation(monkeypatch) -> None:
    part = _line_rrp(5)
    source = _body_descriptor(part)[2].descriptor
    graph = FaceGraph(part)
    solid = graph.common_valid_solid(graph.nodes)
    assert solid is not None
    solid_faces = Solid.faces

    monkeypatch.setattr(
        Solid,
        "faces",
        lambda self: [Face.cast(face.wrapped.Reversed()) for face in solid_faces(self)],
    )
    reversed_descriptor = graph.body_geometry(solid).descriptor
    assert reversed_descriptor != source
    assert tuple(face.material_side for face in reversed_descriptor.boundary.faces) != tuple(
        face.material_side for face in source.boundary.faces
    )


def test_body_geometry_refuses_foreign_and_copied_solid_refs() -> None:
    graph, solid, _fact = _body_descriptor(_rrp())
    foreign, foreign_solid, _foreign_fact = _body_descriptor(_rrp())

    with pytest.raises(BodyGeometryAuthorityError, match="not issued"):
        graph.body_geometry(copy.copy(solid))
    with pytest.raises(BodyGeometryAuthorityError, match="not issued"):
        graph.body_geometry(foreign_solid)
    assert foreign is not graph

    mutated_graph, mutated, _mutated_fact = _body_descriptor(_rrp())
    object.__setattr__(mutated, "ordinal", 99)
    with pytest.raises(BodyGeometryAuthorityError, match="not issued"):
        mutated_graph.body_geometry(mutated)


def test_body_geometry_refuses_unsupported_surface_without_caching() -> None:
    graph = FaceGraph(Sphere(5))
    solid = graph.common_valid_solid(graph.nodes)
    assert solid is not None

    with pytest.raises(UnsupportedBodyGeometry, match="unsupported body face surface"):
        graph.body_geometry(solid)


def test_body_geometry_refuses_supported_surface_with_freeform_curve() -> None:
    spline = Edge.make_spline([Vector(0, 0), Vector(2, 1), Vector(4, 0)])
    wire = Wire(
        [
            spline,
            Edge.make_line((4, 0), (4, 4)),
            Edge.make_line((4, 4), (0, 4)),
            Edge.make_line((0, 4), (0, 0)),
        ]
    )
    part = extrude(Face(wire), 5)
    graph = FaceGraph(part)
    solid = graph.common_valid_solid(graph.nodes)
    assert solid is not None

    with pytest.raises(UnsupportedBodyGeometry, match="unsupported body face surface"):
        graph.body_geometry(solid)
    with pytest.raises(UnsupportedBodyGeometry, match="unsupported body edge curve"):
        _body_geometry._edge_geometry(spline, (0.0, 0.0, 0.0), 1e-7)


def test_invalid_open_geometry_and_unexpected_programmer_errors_do_not_cache(
    monkeypatch,
) -> None:
    shell = _rrp().shells()[0]
    with pytest.raises(UnsupportedBodyGeometry, match="valid closed solid"):
        _body_geometry.describe_solid(shell)

    graph = FaceGraph(_rrp())
    solid = graph.common_valid_solid(graph.nodes)
    assert solid is not None

    def programmer_error(*_args):
        raise KeyError("controlled programmer error")

    monkeypatch.setattr(BRepGProp, "VolumeProperties_s", programmer_error)
    with pytest.raises(KeyError, match="programmer error"):
        graph.body_geometry(solid)
    with pytest.raises(KeyError, match="programmer error"):
        graph.body_geometry(solid)


@pytest.mark.parametrize("mass", [float("nan"), 0.0, -1.0])
def test_nonfinite_zero_and_negative_mass_refuse(mass: float, monkeypatch) -> None:
    graph = FaceGraph(_rrp())
    solid = graph.common_valid_solid(graph.nodes)
    assert solid is not None
    monkeypatch.setattr(GProp_GProps, "Mass", lambda _self: mass)
    with pytest.raises(UnsupportedBodyGeometry, match="mass properties"):
        graph.body_geometry(solid)


@pytest.mark.parametrize("surface", [float("nan"), 0.0, -1.0])
def test_nonfinite_zero_and_negative_surface_area_refuse(surface: float, monkeypatch) -> None:
    graph = FaceGraph(_rrp())
    solid = graph.common_valid_solid(graph.nodes)
    assert solid is not None
    original = GProp_GProps.Mass
    calls = 0

    def mass(props):
        nonlocal calls
        calls += 1
        return surface if calls == 2 else original(props)

    monkeypatch.setattr(GProp_GProps, "Mass", mass)
    with pytest.raises(UnsupportedBodyGeometry, match="mass properties"):
        graph.body_geometry(solid)


@pytest.mark.parametrize("moment", [float("nan"), -1.0])
def test_nonfinite_and_negative_principal_moment_refuse(moment: float, monkeypatch) -> None:
    graph = FaceGraph(_rrp())
    solid = graph.common_valid_solid(graph.nodes)
    assert solid is not None
    original = GProp_GProps.PrincipalProperties

    class BrokenPrincipal:
        def Moments(self):
            return (moment, 1.0, 1.0)

    monkeypatch.setattr(GProp_GProps, "PrincipalProperties", lambda _self: BrokenPrincipal())
    with pytest.raises(UnsupportedBodyGeometry, match="mass properties"):
        graph.body_geometry(solid)
    monkeypatch.setattr(GProp_GProps, "PrincipalProperties", original)


@pytest.mark.parametrize("length", [float("nan"), 0.0, -1.0])
def test_nonfinite_zero_and_negative_curve_length_refuse(length: float, monkeypatch) -> None:
    edge = Edge.make_line((0, 0, 0), (1, 0, 0))
    monkeypatch.setattr(Edge, "length", property(lambda _self: length))
    with pytest.raises(UnsupportedBodyGeometry, match="edge length"):
        _body_geometry._edge_geometry(edge, (0.0, 0.0, 0.0), 1e-7)


def test_internal_runtime_boundary_failure_propagates_and_does_not_cache(
    monkeypatch,
) -> None:
    graph = FaceGraph(_rrp())
    solid = graph.common_valid_solid(graph.nodes)
    assert solid is not None

    monkeypatch.setattr(
        _body_geometry,
        "_face_geometry",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("controlled programmer failure")),
    )
    with pytest.raises(RuntimeError, match="programmer failure"):
        graph.body_geometry(solid)
    with pytest.raises(RuntimeError, match="programmer failure"):
        graph.body_geometry(solid)


def test_solid_face_enumeration_runtime_failure_is_closed_and_does_not_cache(monkeypatch) -> None:
    graph = FaceGraph(_rrp())
    solid_ref = graph.common_valid_solid(graph.nodes)
    assert solid_ref is not None

    monkeypatch.setattr(
        Solid,
        "faces",
        lambda _self: (_ for _ in ()).throw(RuntimeError("controlled wrapper failure")),
    )
    with pytest.raises(UnsupportedBodyGeometry, match="body boundary"):
        graph.body_geometry(solid_ref)
    with pytest.raises(UnsupportedBodyGeometry, match="body boundary"):
        graph.body_geometry(solid_ref)


@pytest.mark.parametrize("end_angle", [180, 270])
def test_trimmed_circle_geometry_is_direction_and_semicircle_safe(end_angle: float) -> None:
    edge = Edge.make_circle(5, Plane.XY, start_angle=0, end_angle=end_angle)
    direct = _body_geometry._edge_geometry(edge, (0.0, 0.0, 0.0), 1e-7)
    reversed_geometry = _body_geometry._edge_geometry(edge.reversed(), (0.0, 0.0, 0.0), 1e-7)

    assert direct == reversed_geometry
    assert direct.start != direct.end
    assert abs(direct.sweep or 0.0) == pytest.approx(
        end_angle * math.pi / 180, abs=_body_geometry.ANGLE_TOL
    )


def test_real_outer_inner_and_seam_wire_orientation_is_step_stable(tmp_path) -> None:
    tube = Cylinder(10, 5) - Cylinder(3, 5)
    target = tmp_path / "tube.step"
    assert export_step(tube, target)
    native = _body_descriptor(tube)[2].descriptor
    stepped = _body_descriptor(import_step(target))[2].descriptor

    native_roles = sorted(
        (wire.role, wire.semantic_winding) for face in native.boundary.faces for wire in face.wires
    )
    stepped_roles = sorted(
        (wire.role, wire.semantic_winding) for face in stepped.boundary.faces for wire in face.wires
    )
    assert native_roles == stepped_roles
    assert {role for role, _winding in native_roles} == {"inner", "outer"}
    assert all(len(incidence) == 2 for _edge, incidence in native.boundary.incidence)


def test_canonicalization_budget_is_inclusive(monkeypatch) -> None:
    label = FaceGeometry("PLANE", (), 1.0, (0.0, 0.0, 0.0), 1, ())
    builds = tuple(_body_geometry._FaceBuild(label, ()) for _ in range(8))

    monkeypatch.setattr(_body_geometry, "CANONICAL_SERIALIZATION_BUDGET", 40_320)
    _ordered, _incidence, symmetric = _body_geometry._canonical_topology(builds)
    assert symmetric

    monkeypatch.setattr(_body_geometry, "CANONICAL_SERIALIZATION_BUDGET", 40_319)
    with pytest.raises(UnsupportedBodyGeometry, match="budget"):
        _body_geometry._canonical_topology(builds)


def test_equal_wire_and_mixed_budget_counts_only_complete_serializations(monkeypatch) -> None:
    edge = _body_geometry.EdgeGeometry("LINE", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 1.0)
    wire = _body_geometry.WireGeometry("outer", 1, ((edge, 1), (edge, -1)))
    tokens = (object(), object())
    wire_builds = tuple(
        _body_geometry._WireBuild(wire, (((token, 1), (token, -1)),)) for token in tokens
    )
    face = FaceGeometry("PLANE", (), 1.0, (0.0, 0.0, 0.0), 1, (wire, wire))
    build = _body_geometry._FaceBuild(face, wire_builds)

    monkeypatch.setattr(_body_geometry, "CANONICAL_SERIALIZATION_BUDGET", 2)
    _body_geometry._canonical_topology((build,))
    monkeypatch.setattr(_body_geometry, "CANONICAL_SERIALIZATION_BUDGET", 1)
    with pytest.raises(UnsupportedBodyGeometry, match="budget"):
        _body_geometry._canonical_topology((build,))


@pytest.mark.parametrize("occurrence_count", [1, 3])
def test_invalid_edge_incidence_cardinality_refuses(occurrence_count: int) -> None:
    edge = _body_geometry.EdgeGeometry("LINE", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 1.0)
    wire = _body_geometry.WireGeometry("outer", 1, ((edge, 1),) * occurrence_count)
    token = object()
    build = _body_geometry._FaceBuild(
        FaceGeometry("PLANE", (), 1.0, (0.0, 0.0, 0.0), 1, (wire,)),
        (_body_geometry._WireBuild(wire, (tuple((token, 1) for _ in range(occurrence_count)),)),),
    )
    with pytest.raises(UnsupportedBodyGeometry, match="closed-shell pair"):
        _body_geometry._canonical_topology((build,))


def test_seam_pair_is_supported_but_conflicting_edge_labels_refuse() -> None:
    line = _body_geometry.EdgeGeometry("LINE", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 1.0)
    changed = dataclasses.replace(line, length=2.0)
    token = object()

    def build(labels):
        wire = _body_geometry.WireGeometry(
            "outer", 1, tuple((label, direction) for label, direction in labels)
        )
        return _body_geometry._FaceBuild(
            FaceGeometry("PLANE", (), 1.0, (0.0, 0.0, 0.0), 1, (wire,)),
            (
                _body_geometry._WireBuild(
                    wire,
                    (tuple((token, direction) for _label, direction in labels),),
                ),
            ),
        )

    _body_geometry._canonical_topology((build(((line, 1), (line, -1))),))
    with pytest.raises(UnsupportedBodyGeometry, match="conflicting analytic labels"):
        _body_geometry._canonical_topology((build(((line, 1), (changed, -1))),))


def test_numeric_degeneracy_and_reconstruction_boundaries_are_inclusive(monkeypatch) -> None:
    quantum = 0.25
    assert _body_geometry._positive_fact(quantum, quantum, name="fact") == quantum
    with pytest.raises(UnsupportedBodyGeometry, match="degenerate"):
        _body_geometry._positive_fact(math.nextafter(quantum, 0.0), quantum, name="fact")

    monkeypatch.setattr(_body_geometry, "_snap", lambda value, _quantum: value + 2.0 * quantum)
    assert _body_geometry._snap_checked(1.0, quantum, name="fact") == 1.5
    monkeypatch.setattr(
        _body_geometry,
        "_snap",
        lambda value, _quantum: math.nextafter(value + 2.0 * quantum, math.inf),
    )
    with pytest.raises(UnsupportedBodyGeometry, match="reconstruction"):
        _body_geometry._snap_checked(1.0, quantum, name="fact")


def test_vector_reconstruction_uses_combined_world_distance(monkeypatch) -> None:
    quantum = 0.25
    component = 2.0 * quantum / math.sqrt(3.0)
    monkeypatch.setattr(_body_geometry, "_snap", lambda value, _quantum: value + component)
    _body_geometry._relative_point((0.0, 0.0, 0.0), quantum, name="axis point")

    outside = math.nextafter(component, math.inf)
    monkeypatch.setattr(_body_geometry, "_snap", lambda value, _quantum: value + outside)
    with pytest.raises(UnsupportedBodyGeometry, match="axis point"):
        _body_geometry._relative_point((0.0, 0.0, 0.0), quantum, name="axis point")


def test_every_descriptor_numeric_field_routes_through_closed_validators(monkeypatch) -> None:
    part = _rrp(7)
    oracle = _raw_body_oracle(part)
    scale = max(oracle["volume"] ** (1 / 3), math.sqrt(oracle["surface_area"]))
    metric = _body_geometry._metric_tolerance(scale)
    area = (scale + metric) ** 2 - scale**2
    volume = (scale + metric) ** 3 - scale**3
    moment = (scale + metric) ** 5 - scale**5
    scalar_calls: list[tuple[str, float]] = []
    vector_calls: list[tuple[str, float]] = []
    axis_calls = 0
    original_scalar = _body_geometry._snap_checked
    original_vector = _body_geometry._relative_point
    original_axis = _body_geometry._qaxis

    def scalar(value, quantum, *, name):
        scalar_calls.append((name, quantum))
        return original_scalar(value, quantum, name=name)

    def vector(raw, quantum, *, name):
        vector_calls.append((name, quantum))
        return original_vector(raw, quantum, name=name)

    def axis(raw):
        nonlocal axis_calls
        axis_calls += 1
        return original_axis(raw)

    monkeypatch.setattr(_body_geometry, "_snap_checked", scalar)
    monkeypatch.setattr(_body_geometry, "_relative_point", vector)
    monkeypatch.setattr(_body_geometry, "_qaxis", axis)
    graph, solid, _fact = _body_descriptor(part)
    graph.matching_boundary(solid)

    expected_scalar_quantum = {
        "plane offset": metric,
        "pcurve u": metric,
        "pcurve v": metric,
        "edge length": metric,
        "circle radius": metric,
        "circle sweep": _body_geometry.ANGLE_TOL,
        "cylinder radius": metric,
        "cylinder theta": _body_geometry.ANGLE_TOL,
        "cylinder z": metric,
        "face area": area,
        "body volume": volume,
        "body surface area": area,
        "principal moment": moment,
    }
    assert set(expected_scalar_quantum) <= {name for name, _quantum in scalar_calls}
    for name, quantum in scalar_calls:
        assert quantum == pytest.approx(expected_scalar_quantum[name])
    expected_vector_names = {
        "edge endpoint",
        "circle centre",
        "face centroid",
        "cylinder axis point",
    }
    assert expected_vector_names <= {name for name, _quantum in vector_calls}
    assert all(quantum == pytest.approx(metric) for _name, quantum in vector_calls)
    assert axis_calls > 0

    # Every production scalar quantum uses the same inclusive closed validator. Exercise the
    # exact equality and nextafter-outside reconstruction rule for each caller-supplied quantum.
    for name, quantum in expected_scalar_quantum.items():
        with monkeypatch.context() as boundary:
            boundary.setattr(
                _body_geometry,
                "_snap",
                lambda value, _q, quantum=quantum: value + 2.0 * quantum,
            )
            assert _body_geometry._snap_checked(0.0, quantum, name=name) == 2.0 * quantum
        with monkeypatch.context() as boundary:
            boundary.setattr(
                _body_geometry,
                "_snap",
                lambda value, _q, quantum=quantum: math.nextafter(value + 2.0 * quantum, math.inf),
            )
            with pytest.raises(UnsupportedBodyGeometry, match="reconstruction"):
                _body_geometry._snap_checked(0.0, quantum, name=name)


def test_direction_quantization_boundaries_are_inclusive(monkeypatch) -> None:
    tolerance = _body_geometry.DIRECTION_TOL
    component = 2.0 * tolerance / math.sqrt(2.0)
    raw = (1.0, 0.0, 0.0)
    monkeypatch.setattr(
        _body_geometry,
        "_snap",
        lambda value, _quantum: value + (component if value == 0.0 else 0.0),
    )
    _body_geometry._qaxis(raw)
    outside = math.nextafter(component, math.inf)
    monkeypatch.setattr(
        _body_geometry,
        "_snap",
        lambda value, _quantum: value + (outside if value == 0.0 else 0.0),
    )
    with pytest.raises(UnsupportedBodyGeometry, match="direction"):
        _body_geometry._qaxis(raw)


@pytest.mark.parametrize("scale", [1e-3, 1e3])
def test_characteristic_quanta_remain_finite_at_supported_scale_extremes(scale: float) -> None:
    descriptor = _body_descriptor(_line_rrp(5).scale(scale))[2].descriptor
    assert descriptor.intrinsic.volume > 0.0
    assert descriptor.intrinsic.surface_area > 0.0
    assert all(math.isfinite(value) for value in _numbers(descriptor))


def test_plane_axis_parameterization_flip_is_identical_at_nonzero_offset() -> None:
    positive = _body_geometry._plane_parameters(
        (1.0, 0.0, 0.0), (7.0, 2.0, 3.0), (2.0, 2.0, 3.0), 1e-7
    )
    negative = _body_geometry._plane_parameters(
        (-1.0, 0.0, 0.0), (7.0, 2.0, 3.0), (2.0, 2.0, 3.0), 1e-7
    )
    assert positive == negative == (1.0, 0.0, 0.0, 5.0)


def test_complete_incidence_distinguishes_equal_labelled_nonisomorphic_graphs() -> None:
    edge = _body_geometry.EdgeGeometry("LINE", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 1.0)
    wire = _body_geometry.WireGeometry("outer", 1, ((edge, 1), (edge, 1)))
    face = FaceGeometry("PLANE", (), 1.0, (0.0, 0.0, 0.0), 1, (wire,))

    def builds(pairs):
        occurrences = [[] for _ in range(4)]
        for token, (left, right) in enumerate(pairs):
            occurrences[left].append((token, 1))
            occurrences[right].append((token, 1))
        return tuple(
            _body_geometry._FaceBuild(
                face,
                (_body_geometry._WireBuild(wire, (tuple(items),)),),
            )
            for items in occurrences
        )

    cycle = builds(((0, 1), (1, 2), (2, 3), (3, 0)))
    doubled = builds(((0, 1), (0, 1), (2, 3), (2, 3)))
    assert _body_geometry._canonical_topology(cycle) != _body_geometry._canonical_topology(doubled)


def test_wire_wrapper_reversal_normalizes_but_material_orientation_survives() -> None:
    first = _body_geometry.EdgeGeometry("LINE", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 1.0)
    second = _body_geometry.EdgeGeometry("LINE", (0.0, 1.0, 0.0), (2.0, 1.0, 0.0), 2.0)
    items = ((first, 1, "a"), (second, 1, "b"))
    direct = _body_geometry._canonical_cycle_with_tokens(items, 1)
    shallow_reversal = _body_geometry._canonical_cycle_with_tokens(
        tuple((edge, -direction, token) for edge, direction, token in reversed(items)), -1
    )
    material_reversal = _body_geometry._canonical_cycle_with_tokens(items, -1)

    assert direct[0] == shallow_reversal[0]
    assert direct[2] == shallow_reversal[2]
    assert direct[2] != material_reversal[2]


def test_snapshot_contains_only_exact_accepted_rrp_occurrences() -> None:
    product = _take_inventory(_rrp(7))
    physical = product.physical.candidate_set(FamilyId.REPEATING_RADIAL_PROFILES)
    accepted = product.reconciliation.accepted_set(physical)

    snapshot = correspondence_snapshot(product)

    assert CORRESPONDENCE_FAMILIES == (FamilyId.REPEATING_RADIAL_PROFILES,)
    assert len(snapshot.occurrences) == len(physical.candidates) == len(accepted.candidates) == 1
    occurrence = snapshot.occurrences[0]
    assert occurrence.family == FamilyId.REPEATING_RADIAL_PROFILES.value
    assert occurrence.record_type == "RepeatingRadialProfile"
    assert occurrence.summary.repeat_count == 7
    assert len(occurrence.summary.defining) == 2
    assert correspondence_snapshot(product) is snapshot


@pytest.mark.parametrize(
    "part, expected_axis, repeats",
    [
        (_line_rrp(5), "z", 5),
        (Rot(90, 0, 0) * _rrp(7), "y", 7),
        (Rot(0, 90, 0) * _line_rrp(8), "x", 8),
    ],
)
def test_accepted_snapshot_roster_covers_principal_axes_and_mixed_curves(
    part, expected_axis: str, repeats: int
) -> None:
    snapshot = correspondence_snapshot(_take_inventory(part))
    assert len(snapshot.occurrences) == 1
    summary = snapshot.occurrences[0].summary
    assert summary.axis == expected_axis
    assert summary.repeat_count == repeats
    kinds = {
        edge.kind
        for face in summary.defining
        for wire in face.wires
        for edge, _direction in wire.edges
    }
    assert kinds == {sector[0] for sector in summary.sector_signature}


def test_equal_coincident_bodies_retain_two_indistinguishable_occurrences() -> None:
    product = _take_inventory(Compound([_rrp(), _rrp()]))
    snapshot = correspondence_snapshot(product)

    assert len(snapshot.occurrences) == 2
    assert snapshot.occurrences[0] == snapshot.occurrences[1]
    assert snapshot.schema_version == 3
    assert snapshot.body_groups == ((0,), (1,))


def test_two_unequal_occurrences_on_one_valid_solid_retain_one_body_authority() -> None:
    part = _two_rrp_one_solid()
    snapshot = correspondence_snapshot(_take_inventory(part))
    assert len(snapshot.occurrences) == 2
    assert [item.summary.repeat_count for item in snapshot.occurrences] == [5, 7]
    assert snapshot.occurrences[0].body is snapshot.occurrences[1].body
    assert snapshot.occurrences[0].summary.centre != snapshot.occurrences[1].summary.centre
    assert snapshot.body_groups == ((0, 1),)


def test_arbitrary_rotation_changes_no_recognition_and_has_no_snapshot_entry() -> None:
    product = _take_inventory(Rot(13, 27, 9) * _rrp())
    assert not product.result.repeating_radial_profiles
    assert correspondence_snapshot(product).occurrences == ()
    assert correspondence_snapshot(product).body_groups == ()


def test_snapshot_revalidates_raw_derived_quantization_authority() -> None:
    product = _take_inventory(_rrp())
    snapshot = correspondence_snapshot(product)
    quantization = snapshot.occurrences[0].body.quantization

    assert quantization.metric_quantum == pytest.approx(
        _body_geometry.DESCRIPTOR_REL * quantization.characteristic_scale
        + _body_geometry.DESCRIPTOR_FLOOR
    )
    object.__setattr__(
        quantization,
        "metric_quantum",
        math.nextafter(quantization.metric_quantum, math.inf),
    )
    with pytest.raises(CorrespondenceSnapshotError, match="occurrence values changed"):
        correspondence_snapshot(product)


def test_snapshot_refuses_consistently_reforged_quantization_and_occurrence() -> None:
    product = _take_inventory(_rrp())
    snapshot = correspondence_snapshot(product)
    occurrence = snapshot.occurrences[0]
    quantization = occurrence.body.quantization
    scale = quantization.characteristic_scale * 2.0
    metric = _body_geometry.DESCRIPTOR_REL * scale + _body_geometry.DESCRIPTOR_FLOOR
    object.__setattr__(quantization, "characteristic_scale", scale)
    object.__setattr__(quantization, "metric_quantum", metric)
    object.__setattr__(quantization, "area_quantum", (scale + metric) ** 2 - scale**2)
    object.__setattr__(quantization, "volume_quantum", (scale + metric) ** 3 - scale**3)
    object.__setattr__(quantization, "moment_quantum", (scale + metric) ** 5 - scale**5)
    with pytest.raises(CorrespondenceSnapshotError, match="occurrence values changed"):
        correspondence_snapshot(product)

    other = _take_inventory(_rrp())
    other_snapshot = correspondence_snapshot(other)
    object.__setattr__(other_snapshot.occurrences[0], "family", "forged")
    with pytest.raises(CorrespondenceSnapshotError, match="occurrence values changed"):
        correspondence_snapshot(other)


def test_first_read_invalid_quantization_maps_to_snapshot_error(monkeypatch) -> None:
    product = _take_inventory(_rrp())
    original = FaceGraph.body_geometry

    def invalid(self, solid):
        fact = original(self, solid)
        object.__setattr__(fact.descriptor.quantization, "metric_quantum", 0.0)
        return fact

    monkeypatch.setattr(FaceGraph, "body_geometry", invalid)
    with pytest.raises(CorrespondenceSnapshotError, match="quantization is unavailable"):
        correspondence_snapshot(product)


def test_snapshot_revalidates_body_group_partition() -> None:
    product = _take_inventory(_two_rrp_one_solid())
    snapshot = correspondence_snapshot(product)
    object.__setattr__(snapshot, "body_groups", ((0,), (1,)))

    # Splitting one issuer-proved body into two groups is not made valid merely because both
    # occurrences carry equal descriptor values.
    with pytest.raises(CorrespondenceSnapshotError, match="body groups"):
        correspondence_snapshot(product)


@pytest.mark.parametrize("scale", [0.0, math.nan, math.inf])
def test_descriptor_quantization_refuses_invalid_characteristic_scale(scale: float) -> None:
    product = _take_inventory(_rrp())
    quantization = correspondence_snapshot(product).occurrences[0].body.quantization
    changed = dataclasses.replace(quantization, characteristic_scale=scale)
    with pytest.raises(UnsupportedBodyGeometry, match="characteristic scale"):
        _body_geometry.validate_descriptor_quantization(changed)


@pytest.mark.parametrize("value", [None, True, (1.0,), "invalid"])
def test_descriptor_quantization_refuses_wrong_runtime_types(value: object) -> None:
    if value is None or type(value) is not _body_geometry.DescriptorQuantization:
        with pytest.raises(UnsupportedBodyGeometry, match="runtime types"):
            _body_geometry.validate_descriptor_quantization(value)  # type: ignore[arg-type]

    product = _take_inventory(_rrp())
    snapshot = correspondence_snapshot(product)
    object.__setattr__(snapshot.occurrences[0].body, "quantization", value)
    with pytest.raises(CorrespondenceSnapshotError, match="occurrence values changed"):
        correspondence_snapshot(product)


def test_schema2_snapshot_validator_closes_schema_partition_and_group_geometry() -> None:
    one = correspondence_snapshot(_take_inventory(_rrp()))
    with pytest.raises(CorrespondenceSnapshotError, match="schema is unsupported"):
        correspondence_module._validate_snapshot(dataclasses.replace(one, schema_version=1))
    with pytest.raises(CorrespondenceSnapshotError, match="schema is malformed"):
        correspondence_module._validate_snapshot(dataclasses.replace(one, schema_version=True))
    for malformed in (
        dataclasses.replace(one, occurrences=list(one.occurrences)),
        dataclasses.replace(one, body_groups=list(one.body_groups)),
    ):
        with pytest.raises(CorrespondenceSnapshotError, match="body groups are malformed"):
            correspondence_module._validate_snapshot(malformed)
    with pytest.raises(CorrespondenceSnapshotError, match="occurrence schema is malformed"):
        correspondence_module._validate_snapshot(dataclasses.replace(one, occurrences=(object(),)))
    malformed_body = dataclasses.replace(one.occurrences[0], body=object())
    with pytest.raises(CorrespondenceSnapshotError, match="occurrence schema is malformed"):
        correspondence_module._validate_snapshot(
            dataclasses.replace(one, occurrences=(malformed_body,))
        )
    for groups in (((False,),), ((0.0,),), ([0],)):
        with pytest.raises(CorrespondenceSnapshotError, match="body groups are malformed"):
            correspondence_module._validate_snapshot(dataclasses.replace(one, body_groups=groups))
    for groups in (((0,), ()), ((1,),), ((0, 0),)):
        with pytest.raises(CorrespondenceSnapshotError, match="complete partition"):
            correspondence_module._validate_snapshot(dataclasses.replace(one, body_groups=groups))

    two = correspondence_snapshot(
        _take_inventory(Compound([Pos(-50, 0, 0) * _rrp(5), Pos(50, 0, 0) * _rrp(7)]))
    )
    assert two.body_groups == ((0,), (1,))
    with pytest.raises(CorrespondenceSnapshotError, match="unequal geometry"):
        correspondence_module._validate_snapshot(dataclasses.replace(two, body_groups=((0, 1),)))

    invalid_quantization = dataclasses.replace(
        one.occurrences[0].body.quantization,
        metric_quantum=0.0,
    )
    invalid_body = dataclasses.replace(
        one.occurrences[0].body,
        quantization=invalid_quantization,
    )
    invalid_occurrence = dataclasses.replace(one.occurrences[0], body=invalid_body)
    with pytest.raises(CorrespondenceSnapshotError, match="quantization is invalid"):
        correspondence_module._validate_snapshot(
            dataclasses.replace(one, occurrences=(invalid_occurrence,))
        )


def test_cached_snapshot_malformed_occurrence_refuses_before_dereference() -> None:
    product = _take_inventory(_rrp())
    snapshot = correspondence_snapshot(product)
    object.__setattr__(snapshot, "occurrences", (object(),))
    with pytest.raises(CorrespondenceSnapshotError, match="occurrence values changed"):
        correspondence_snapshot(product)


def test_snapshot_is_lazy_and_body_descriptor_runs_once(monkeypatch) -> None:
    calls = 0
    original = FaceGraph.body_geometry

    def counted(self, solid):
        nonlocal calls
        calls += 1
        return original(self, solid)

    monkeypatch.setattr(FaceGraph, "body_geometry", counted)
    product = _take_inventory(_rrp())
    assert calls == 0

    first = correspondence_snapshot(product)
    second = correspondence_snapshot(product)
    assert first is second
    assert calls == 1


def test_late_second_body_failure_returns_no_snapshot_and_can_retry(monkeypatch) -> None:
    part = Compound([Pos(-50, 0, 0) * _rrp(5), Pos(50, 0, 0) * _rrp(7)])
    product = _take_inventory(part)
    result = product.result
    candidate_snapshot = product.physical.candidate_set(
        FamilyId.REPEATING_RADIAL_PROFILES
    ).candidates
    evidence_snapshot = tuple(
        (candidate, product.evidence.defining_of(candidate)) for candidate in candidate_snapshot
    )
    original = FaceGraph.body_geometry
    calls = 0

    def fail_second(self, solid):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise UnsupportedBodyGeometry("controlled late body failure")
        return original(self, solid)

    monkeypatch.setattr(FaceGraph, "body_geometry", fail_second)
    with pytest.raises(CorrespondenceSnapshotError, match="body geometry is unavailable"):
        correspondence_snapshot(product)
    assert product.result is result
    assert (
        tuple(
            (candidate, product.evidence.defining_of(candidate)) for candidate in candidate_snapshot
        )
        == evidence_snapshot
    )
    assert (
        product.physical.candidate_set(FamilyId.REPEATING_RADIAL_PROFILES).candidates
        == candidate_snapshot
    )

    monkeypatch.setattr(FaceGraph, "body_geometry", original)
    snapshot = correspondence_snapshot(product)
    assert len(snapshot.occurrences) == 2


def test_cross_solid_defining_evidence_refuses_atomically(monkeypatch) -> None:
    part = Compound([Pos(-50, 0, 0) * _rrp(5), Pos(50, 0, 0) * _rrp(7)])
    product = _take_inventory(part)
    graph = product.context.graph
    selected = []
    owners = []
    for node in graph.nodes:
        owner = graph.common_valid_solid((node,))
        if owner is not None and all(owner is not previous for previous in owners):
            owners.append(owner)
            selected.append(node)
    assert len(selected) == 2

    original = EvidenceIndex.defining_of

    def mixed(self, subject):
        if getattr(subject, "family", None) is FamilyId.REPEATING_RADIAL_PROFILES:
            return frozenset(selected)
        return original(self, subject)

    monkeypatch.setattr(EvidenceIndex, "defining_of", mixed)
    with pytest.raises(CorrespondenceSnapshotError, match="one valid solid"):
        correspondence_snapshot(product)


def test_foreign_defining_nodes_refuse_before_body_projection(monkeypatch) -> None:
    product = _take_inventory(_rrp())
    foreign = FaceGraph(Pos(3, 4, 5) * _rrp())
    nodes = foreign.nodes[:2]
    original = EvidenceIndex.defining_of

    def stale(self, subject):
        if getattr(subject, "family", None) is FamilyId.REPEATING_RADIAL_PROFILES:
            return frozenset(nodes)
        return original(self, subject)

    monkeypatch.setattr(EvidenceIndex, "defining_of", stale)
    with pytest.raises(CorrespondenceSnapshotError, match="exactly two original faces"):
        correspondence_snapshot(product)


def test_deep_copied_defining_nodes_refuse_before_body_projection(monkeypatch) -> None:
    product = _take_inventory(_rrp())
    nodes = tuple(copy.deepcopy(node) for node in product.context.graph.nodes[:2])
    original = EvidenceIndex.defining_of

    def stale(self, subject):
        if getattr(subject, "family", None) is FamilyId.REPEATING_RADIAL_PROFILES:
            return frozenset(nodes)
        return original(self, subject)

    monkeypatch.setattr(EvidenceIndex, "defining_of", stale)
    with pytest.raises(CorrespondenceSnapshotError, match="exactly two original faces"):
        correspondence_snapshot(product)


def test_reused_defining_face_refuses_before_body_projection(monkeypatch) -> None:
    product = _take_inventory(_rrp())
    node = product.context.graph.nodes[0]
    original = EvidenceIndex.defining_of

    def reused(self, subject):
        if getattr(subject, "family", None) is FamilyId.REPEATING_RADIAL_PROFILES:
            return (node, node)
        return original(self, subject)

    monkeypatch.setattr(EvidenceIndex, "defining_of", reused)
    with pytest.raises(CorrespondenceSnapshotError, match="exactly two original faces"):
        correspondence_snapshot(product)


def test_copied_or_constructed_inventory_product_cannot_reuse_authority() -> None:
    product = _take_inventory(_rrp())
    copied = dataclasses.replace(product)
    unissued = dataclasses.replace(product, _correspondence_authority=None)

    with pytest.raises(CorrespondenceSnapshotError, match="not this authority"):
        correspondence_snapshot(copied)
    with pytest.raises(CorrespondenceSnapshotError, match="no snapshot authority"):
        correspondence_snapshot(unissued)
    assert correspondence_snapshot(product).occurrences


def test_record_mutation_after_inventory_binding_refuses() -> None:
    product = _take_inventory(_rrp())
    assert correspondence_snapshot(product).occurrences
    candidate = product.physical.candidate_set(FamilyId.REPEATING_RADIAL_PROFILES).candidates[0]
    object.__setattr__(candidate.record, "repeat_count", candidate.record.repeat_count + 1)

    with pytest.raises(CorrespondenceSnapshotError, match="identity or value changed"):
        correspondence_snapshot(product)


def test_bound_product_component_mutation_refuses() -> None:
    product = _take_inventory(_rrp())
    foreign = _take_inventory(_rrp(7))
    object.__setattr__(product, "evidence", foreign.evidence)

    with pytest.raises(CorrespondenceSnapshotError, match="not this authority"):
        correspondence_snapshot(product)


def test_forged_reconciliation_membership_refuses() -> None:
    product = _take_inventory(_rrp())
    object.__setattr__(product.reconciliation, "_membership", frozenset())
    with pytest.raises(CorrespondenceSnapshotError, match="stale or mixed"):
        correspondence_snapshot(product)


def test_wrong_record_type_refuses_authority_binding() -> None:
    product = _take_inventory(_rrp())
    candidate = product.physical.candidate_set(FamilyId.REPEATING_RADIAL_PROFILES).candidates[0]
    object.__setattr__(candidate, "record", object())
    authority = correspondence_module._CorrespondenceSnapshotAuthority()
    with pytest.raises(CorrespondenceSnapshotError, match="stale or mixed"):
        authority.bind(product)


@pytest.mark.parametrize("count", [0, 1, 3])
def test_wrong_defining_face_cardinality_refuses(count: int, monkeypatch) -> None:
    product = _take_inventory(_rrp())
    nodes = product.context.graph.nodes[:count]
    original = EvidenceIndex.defining_of

    def wrong(self, subject):
        if getattr(subject, "family", None) is FamilyId.REPEATING_RADIAL_PROFILES:
            return frozenset(nodes)
        return original(self, subject)

    monkeypatch.setattr(EvidenceIndex, "defining_of", wrong)
    with pytest.raises(CorrespondenceSnapshotError, match="exactly two"):
        correspondence_snapshot(product)


def test_nonplanar_defining_faces_refuse(monkeypatch) -> None:
    product = _take_inventory(_rrp())
    graph = product.context.graph
    nonplanar = tuple(node for node in graph.nodes if not graph.is_planar(node))[:2]
    assert len(nonplanar) == 2
    original = EvidenceIndex.defining_of

    def wrong(self, subject):
        if getattr(subject, "family", None) is FamilyId.REPEATING_RADIAL_PROFILES:
            return frozenset(nonplanar)
        return original(self, subject)

    monkeypatch.setattr(EvidenceIndex, "defining_of", wrong)
    with pytest.raises(CorrespondenceSnapshotError, match="non-planar"):
        correspondence_snapshot(product)


def test_snapshot_is_private_and_changes_no_public_result() -> None:
    before = _take_inventory(_rrp())
    result_before = before.result
    snapshot = correspondence_snapshot(before)

    assert snapshot.occurrences
    assert before.result is result_before
    assert "correspondence_snapshot" not in b123d_recognisers.__all__
    assert not hasattr(b123d_recognisers, "CorrespondenceSnapshot")


def test_private_correspondence_layering_and_handle_guards_are_closed() -> None:
    lower_path = ROOT / "src/b123d_recognisers/_body_geometry.py"
    upper_path = ROOT / "src/b123d_recognisers/_correspondence.py"
    lower = ast.parse(lower_path.read_text())
    upper = ast.parse(upper_path.read_text())

    forbidden_lower = {
        "_candidates",
        "_claims",
        "_registry",
        "_reconcile",
        "_dispositions",
        "result",
    }
    lower_imports = {
        node.module.rsplit(".", 1)[-1]
        for node in ast.walk(lower)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert lower_imports.isdisjoint(forbidden_lower)

    forbidden_attributes = {"ordinal", "index"}
    for tree in (lower, upper):
        assert (
            not {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
            & forbidden_attributes
        )

    body_callers = {
        node.name
        for node in ast.walk(upper)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(
            isinstance(item, ast.Call)
            and isinstance(item.func, ast.Attribute)
            and item.func.attr == "body_geometry"
            for item in ast.walk(node)
        )
    }
    assert body_callers == {"_occurrence"}

    source_paths = tuple((ROOT / "src/b123d_recognisers").glob("*.py"))
    all_body_callers = []
    correspondence_importers = []
    for path in source_paths:
        tree = ast.parse(path.read_text())
        body_call_nodes = {id(node) for node in _alias_aware_calls(tree, "body_geometry")}
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "b123d_recognisers._correspondence"
            ):
                correspondence_importers.append(path.name)
            if id(node) in body_call_nodes:
                owner = next(
                    (
                        parent.name
                        for parent in ast.walk(tree)
                        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and node in tuple(ast.walk(parent))
                    ),
                    None,
                )
                all_body_callers.append((path.name, owner))
    assert set(all_body_callers) == {
        ("_correspondence.py", "_occurrence"),
        ("_adjacency.py", "matching_boundary"),
    }
    matching_callers = set()
    for path in source_paths:
        tree = ast.parse(path.read_text())
        for node in _alias_aware_calls(tree, "matching_boundary"):
            owner = next(
                (
                    parent.name
                    for parent in ast.walk(tree)
                    if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node in tuple(ast.walk(parent))
                ),
                None,
            )
            matching_callers.add((path.name, owner))
    assert matching_callers == {("_correspondence.py", "_occurrence")}
    assert correspondence_importers == ["result.py"]

    lower_calls = {
        target: tuple(ast.unparse(node.func) for node in _alias_aware_calls(lower, target))
        for target in {
            "VolumeProperties_s",
            "SurfaceProperties_s",
            "Plane",
            "Cylinder",
            "Circle",
        }
    }
    assert lower_calls == {
        "VolumeProperties_s": ("BRepGProp.VolumeProperties_s",),
        "SurfaceProperties_s": ("BRepGProp.SurfaceProperties_s",),
        "Plane": ("adaptor.Plane",),
        "Cylinder": ("adaptor.Cylinder", "adaptor.Cylinder"),
        "Circle": ("curve.Circle",),
    }
    upper_names = {node.id for node in ast.walk(upper) if isinstance(node, ast.Name)}
    assert {"CORRESPONDENCE_FAMILIES", "RepeatingRadialProfile", "accepted"} <= upper_names
    assert not (
        {"digest", "hash", "unchanged", "moved", "resized", "split", "merged"} & upper_names
    )
    assert "correspondence_snapshot" not in b123d_recognisers.__all__
    assert not hasattr(b123d_recognisers, "CorrespondenceSnapshot")


@pytest.mark.parametrize(
    "source",
    [
        "def f(graph, solid):\n    return graph.body_geometry(solid)\n",
        "def f(graph, solid):\n    query = graph.body_geometry\n    return query(solid)\n",
        "from x import body_geometry as query\ndef f(solid):\n    return query(solid)\n",
        "import package\ndef f(graph, solid):\n    return package.graph.body_geometry(solid)\n",
    ],
)
def test_alias_aware_body_query_guard_detects_every_supported_call_form(source: str) -> None:
    assert len(_alias_aware_calls(ast.parse(source), "body_geometry")) == 1


def test_snapshot_values_contain_no_run_or_kernel_handles() -> None:
    snapshot = correspondence_snapshot(_take_inventory(_rrp()))

    def visit(value):
        if dataclasses.is_dataclass(value):
            for item in dataclasses.fields(value):
                yield from visit(getattr(value, item.name))
        elif isinstance(value, tuple):
            for item in value:
                yield from visit(item)
        else:
            yield value

    leaves = tuple(visit(snapshot))
    assert all(value is None or isinstance(value, (bool, int, float, str)) for value in leaves)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (float("nan"), "non-finite"),
        ({1: "value"}, "non-string key"),
        (object(), "unsupported object state"),
    ],
)
def test_snapshot_value_freezer_refuses_unstable_state(value, message: str) -> None:
    with pytest.raises(CorrespondenceSnapshotError, match=message):
        correspondence_module._freeze(value)


def test_snapshot_value_freezer_normalizes_nested_and_negative_zero() -> None:
    assert correspondence_module._freeze({"b": [-0.0], "a": None}) == (
        ("a", None),
        ("b", (0.0,)),
    )


@pytest.mark.parametrize(
    "call",
    [
        lambda: _body_geometry._finite(float("inf")),
        lambda: _body_geometry._snap(1.0, 0.0),
        lambda: _body_geometry._vector(Vector(2.0, 0.0, 0.0).wrapped),
        lambda: _body_geometry._canonical_cycle(()),
        lambda: _body_geometry._canonical_cycle_with_tokens((), 1),
    ],
)
def test_low_level_descriptor_refusals_are_named(call) -> None:
    with pytest.raises(UnsupportedBodyGeometry):
        call()


def test_positive_fact_refuses_quantization_collapse(monkeypatch) -> None:
    monkeypatch.setattr(_body_geometry, "_snap_checked", lambda *_args, **_kwargs: 0.0)
    with pytest.raises(UnsupportedBodyGeometry, match="collapses"):
        _body_geometry._positive_fact(1.0, 0.1, name="controlled fact")


def test_quantized_axis_refuses_nonunit_serialization(monkeypatch) -> None:
    monkeypatch.setattr(_body_geometry, "_snap", lambda _value, _quantum: 0.0)
    with pytest.raises(UnsupportedBodyGeometry, match="unit length"):
        _body_geometry._qaxis((1.0, 0.0, 0.0))


def test_ambiguous_wire_semantic_winding_refuses() -> None:
    edge = _body_geometry.EdgeGeometry("LINE", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 1.0)
    items = ((edge, 1, "a"), (edge, -1, "b"))
    with pytest.raises(UnsupportedBodyGeometry, match="semantic winding is ambiguous"):
        _body_geometry._canonical_cycle_with_tokens(items, 1)


def test_degenerate_circle_radius_refuses(monkeypatch) -> None:
    edge = Edge.make_circle(1.0)
    monkeypatch.setattr(type(edge), "radius", property(lambda _self: 0.0))
    with pytest.raises(UnsupportedBodyGeometry, match="circle radius"):
        _body_geometry._arc_sweep(edge, (0.0, 0.0, 1.0))


def test_degenerate_circle_sweep_refuses(monkeypatch) -> None:
    edge = Edge.make_circle(1.0)
    monkeypatch.setattr(type(edge), "length", property(lambda _self: 1e-12))
    with pytest.raises(UnsupportedBodyGeometry, match="circle sweep"):
        _body_geometry._arc_sweep(edge, (0.0, 0.0, 1.0))


def test_degenerate_face_area_refuses(monkeypatch) -> None:
    face = Box(1, 1, 1).faces()[0]
    monkeypatch.setattr(type(face), "area", property(lambda _self: 0.0))
    with pytest.raises(UnsupportedBodyGeometry, match="face area"):
        _body_geometry._face_geometry(face, (0.0, 0.0, 0.0), 1.0)


def test_snapshot_authority_cannot_bind_twice() -> None:
    product = _take_inventory(_rrp())
    authority = correspondence_module._CorrespondenceSnapshotAuthority()
    authority.bind(product)
    with pytest.raises(CorrespondenceSnapshotError, match="already bound"):
        authority.bind(product)


def test_body_fact_solid_identity_is_revalidated(monkeypatch) -> None:
    product = _take_inventory(_rrp())
    original = FaceGraph.body_geometry

    def wrong_solid(self, solid):
        fact = original(self, solid)
        return dataclasses.replace(fact, _solid=copy.copy(solid))

    monkeypatch.setattr(FaceGraph, "body_geometry", wrong_solid)
    with pytest.raises(CorrespondenceSnapshotError, match="lost its graph-issued solid"):
        correspondence_snapshot(product)


def test_defining_face_authority_failure_is_wrapped(monkeypatch) -> None:
    product = _take_inventory(_rrp())

    def refuse(_self, _node):
        raise BodyGeometryAuthorityError("controlled missing face")

    monkeypatch.setattr(
        "b123d_recognisers._adjacency.BodyGeometryFact._defining_face",
        refuse,
    )
    with pytest.raises(CorrespondenceSnapshotError, match="defining face geometry"):
        correspondence_snapshot(product)


def test_body_fact_rejects_a_nonmember_face_node() -> None:
    graph, solid, fact = _body_descriptor(_rrp())
    foreign = FaceGraph(Pos(3, 4, 5) * _rrp()).nodes[0]
    assert graph.owns(fact._faces[0][0])
    with pytest.raises(BodyGeometryAuthorityError, match="not part"):
        fact._defining_face(foreign)


def test_body_geometry_revalidates_reference_identity_and_closed_membership() -> None:
    graph, solid, _fact = _body_descriptor(_rrp())
    copied = copy.copy(solid)
    graph._issued_solid_refs[copied] = copied.ordinal
    with pytest.raises(BodyGeometryAuthorityError, match="identity changed"):
        graph.body_geometry(copied)

    graph._body_geometry.clear()
    assert graph._closed_solids is not None
    graph._closed_solids = frozenset()
    with pytest.raises(BodyGeometryAuthorityError, match="valid closed solid"):
        graph.body_geometry(solid)


def test_body_geometry_refuses_unowned_described_face(monkeypatch) -> None:
    graph = FaceGraph(_rrp())
    solid = graph.common_valid_solid(graph.nodes)
    assert solid is not None
    monkeypatch.setattr(FaceGraph, "node_of", lambda _self, _face: None)
    with pytest.raises(BodyGeometryAuthorityError, match="face is not owned"):
        graph.body_geometry(solid)


def test_evidence_index_rejects_a_different_graph_run() -> None:
    product = _take_inventory(_rrp())
    foreign = FaceGraph(_rrp())
    with pytest.raises(ValueError, match="another graph run"):
        product.evidence._validate_graph(foreign)


def test_plain_cycle_canonicalization_normalizes_reversal() -> None:
    first = _body_geometry.EdgeGeometry("LINE", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 1.0)
    second = _body_geometry.EdgeGeometry("LINE", (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), 1.0)
    direct = ((first, 1), (second, 1))
    reversed_items = tuple((edge, -direction) for edge, direction in reversed(direct))
    assert _body_geometry._canonical_cycle(direct) == _body_geometry._canonical_cycle(
        reversed_items
    )
