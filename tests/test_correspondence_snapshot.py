# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""F6a private body descriptors and accepted RRP snapshot authority."""

from __future__ import annotations

import ast
import copy
import dataclasses
import math
from collections.abc import Mapping
from pathlib import Path

import pytest
from build123d import (
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
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

import b123d_recognisers
from b123d_recognisers import _body_geometry
from b123d_recognisers import _correspondence as correspondence_module
from b123d_recognisers._adjacency import BodyGeometryAuthorityError, FaceGraph
from b123d_recognisers._body_geometry import FaceGeometry, UnsupportedBodyGeometry
from b123d_recognisers._candidates import EvidenceIndex, FamilyId
from b123d_recognisers._correspondence import (
    CORRESPONDENCE_FAMILIES,
    CorrespondenceSnapshotError,
    correspondence_snapshot,
)
from b123d_recognisers.result import _take_inventory

ROOT = Path(__file__).parents[1]


def _rrp(repeats: int = 5):
    part = Cylinder(20, 10)
    for index in range(repeats):
        part -= Rot(0, 0, 360 * index / repeats) * Pos(18, 0, 0) * Box(8, 3, 10)
    return part


def _line_rrp(repeats: int):
    points = []
    for sector in range(repeats):
        for offset, radius in enumerate((20.0, 16.0, 20.0, 18.0)):
            angle = 2 * math.pi * (sector / repeats + offset / (4 * repeats))
            points.append((radius * math.cos(angle), radius * math.sin(angle)))
    return extrude(Polygon(*points), 10)


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
    incidence: dict[object, int] = {}
    face_geometry = []
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
        outer = face.outer_wire()
        wires = []
        for wire in face.wires():
            edges = []
            for edge in wire.edges():
                incidence[edge] = incidence.get(edge, 0) + 1
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
                circle = None
                if kind == "CIRCLE":
                    raw = curve.Circle()
                    circle = (
                        tuple(
                            _rounded(value - origin)
                            for value, origin in zip(raw.Location().Coord(), centre, strict=True)
                        ),
                        _oracle_axis(raw.Axis().Direction().Coord()),
                        _rounded(raw.Radius()),
                        _rounded(abs(float(edge.length) / float(raw.Radius()))),
                    )
                edges.append(
                    (kind, min(start, end), max(start, end), _rounded(edge.length), circle)
                )
            wires.append(("outer" if wire == outer else "inner", tuple(sorted(edges))))
        face_centre = face.center()
        face_geometry.append(
            (
                surface_kind,
                tuple(_rounded(value) for value in parameters),
                _rounded(face.area),
                tuple(
                    _rounded(value - origin)
                    for value, origin in zip(tuple(face_centre), centre, strict=True)
                ),
                tuple(sorted(wires)),
            )
        )
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
        "faces": tuple(sorted(face_geometry)),
        "incidence": tuple(sorted(incidence.values())),
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


def _descriptor_face_payload(face: FaceGeometry):
    wires = []
    for wire in face.wires:
        edges = []
        for edge, _direction in wire.edges:
            circle = None
            if edge.kind == "CIRCLE":
                circle = (
                    tuple(map(_rounded, edge.centre or ())),
                    tuple(map(_rounded, edge.axis or ())),
                    _rounded(edge.radius or 0.0),
                    _rounded(abs(edge.sweep or 0.0)),
                )
            edges.append(
                (
                    edge.kind,
                    tuple(map(_rounded, min(edge.start, edge.end))),
                    tuple(map(_rounded, max(edge.start, edge.end))),
                    _rounded(edge.length),
                    circle,
                )
            )
        wires.append((wire.role, tuple(sorted(edges))))
    return (
        face.kind,
        tuple(map(_rounded, face.parameters)),
        _rounded(face.area),
        tuple(map(_rounded, face.centroid)),
        tuple(sorted(wires)),
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


def test_body_geometry_is_translation_normalized_and_cached() -> None:
    graph, solid, source = _body_descriptor(_rrp())
    translated_graph, _translated_solid, translated = _body_descriptor(Pos(7, 8, 9) * _rrp())

    assert graph.body_geometry(solid) is source
    assert source.descriptor.intrinsic == translated.descriptor.intrinsic
    assert source.descriptor.boundary == translated.descriptor.boundary
    assert translated.descriptor.placement.centre_of_mass == pytest.approx((7.0, 8.0, 9.0))
    assert source.descriptor.placement != translated.descriptor.placement
    assert translated_graph is not graph


def test_raw_ocp_oracle_independently_reconstructs_mass_and_topology() -> None:
    part = _rrp(7)
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
    assert oracle["incidence"] and set(oracle["incidence"]) == {2}
    assert all(len(occurrences) == 2 for _edge, occurrences in fact.descriptor.boundary.incidence)

    occurrence = correspondence_snapshot(_take_inventory(part)).occurrences[0]
    oracle_caps = tuple(
        face for face in oracle["faces"] if face[0] == "PLANE" and face[1][:3] == (0.0, 0.0, 1.0)
    )
    assert len(oracle_caps) == 2
    assert tuple(sorted(map(_descriptor_face_payload, occurrence.summary.defining))) == tuple(
        sorted(oracle_caps)
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


@pytest.mark.parametrize("length", [float("nan"), 0.0, -1.0])
def test_nonfinite_zero_and_negative_curve_length_refuse(length: float, monkeypatch) -> None:
    edge = Edge.make_line((0, 0, 0), (1, 0, 0))
    monkeypatch.setattr(Edge, "length", property(lambda _self: length))
    with pytest.raises(UnsupportedBodyGeometry, match="edge length"):
        _body_geometry._edge_geometry(edge, (0.0, 0.0, 0.0), 1e-7)


def test_kernel_boundary_failure_is_closed_but_programmer_failure_propagates(
    monkeypatch,
) -> None:
    graph = FaceGraph(_rrp())
    solid = graph.common_valid_solid(graph.nodes)
    assert solid is not None

    monkeypatch.setattr(
        _body_geometry,
        "_face_geometry",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("controlled kernel failure")),
    )
    with pytest.raises(UnsupportedBodyGeometry, match="body boundary"):
        graph.body_geometry(solid)
    with pytest.raises(UnsupportedBodyGeometry, match="body boundary"):
        graph.body_geometry(solid)


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


def test_arbitrary_rotation_changes_no_recognition_and_has_no_snapshot_entry() -> None:
    product = _take_inventory(Rot(13, 27, 9) * _rrp())
    assert not product.result.repeating_radial_profiles
    assert correspondence_snapshot(product).occurrences == ()


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
