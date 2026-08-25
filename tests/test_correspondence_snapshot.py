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
    Plane,
    Pos,
    Rot,
    Sphere,
    export_step,
    import_step,
)

import b123d_recognisers
from b123d_recognisers import _body_geometry
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


def _body_descriptor(part):
    graph = FaceGraph(part)
    solid = graph.common_valid_solid(graph.nodes)
    assert solid is not None
    return graph, solid, graph.body_geometry(solid)


def _structure(value):
    if dataclasses.is_dataclass(value):
        fields = tuple(
            _structure(getattr(value, item.name)) for item in dataclasses.fields(value)
        )
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
    with pytest.raises(UnsupportedBodyGeometry, match="unsupported body face surface"):
        graph.body_geometry(solid)


@pytest.mark.parametrize("end_angle", [180, 270])
def test_trimmed_circle_geometry_is_direction_and_semicircle_safe(end_angle: float) -> None:
    edge = Edge.make_circle(5, Plane.XY, start_angle=0, end_angle=end_angle)
    direct = _body_geometry._edge_geometry(edge, (0.0, 0.0, 0.0), 1e-7)
    reversed_geometry = _body_geometry._edge_geometry(
        edge.reversed(), (0.0, 0.0, 0.0), 1e-7
    )

    assert direct == reversed_geometry
    assert direct.start != direct.end
    assert abs(direct.sweep or 0.0) == pytest.approx(
        end_angle * math.pi / 180, abs=_body_geometry.ANGLE_TOL
    )


def test_canonicalization_budget_is_inclusive(monkeypatch) -> None:
    class EmptyFace:
        def outer_wire(self):
            return None

        def wires(self):
            return ()

    label = FaceGeometry("PLANE", (), 1.0, (0.0, 0.0, 0.0), 1, ())
    faces = tuple(EmptyFace() for _ in range(8))
    labels = (label,) * 8

    monkeypatch.setattr(_body_geometry, "CANONICAL_SERIALIZATION_BUDGET", 40_320)
    _ordered, _incidence, symmetric = _body_geometry._canonical_topology(
        faces, labels, (0.0, 0.0, 0.0), 1.0
    )
    assert symmetric

    monkeypatch.setattr(_body_geometry, "CANONICAL_SERIALIZATION_BUDGET", 40_319)
    with pytest.raises(UnsupportedBodyGeometry, match="budget"):
        _body_geometry._canonical_topology(faces, labels, (0.0, 0.0, 0.0), 1.0)


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


def test_copied_or_constructed_inventory_product_cannot_reuse_authority() -> None:
    product = _take_inventory(_rrp())
    copied = dataclasses.replace(product)
    unissued = dataclasses.replace(product, _correspondence_authority=None)

    with pytest.raises(CorrespondenceSnapshotError, match="not this authority"):
        correspondence_snapshot(copied)
    with pytest.raises(CorrespondenceSnapshotError, match="no snapshot authority"):
        correspondence_snapshot(unissued)
    assert correspondence_snapshot(product).occurrences


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
        assert not {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        } & forbidden_attributes

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
