import math

import pytest
from build123d import Axis, Box, Cylinder, Sphere

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._effective_surfaces import (
    AnalyticSurfaceFact,
    EffectiveSurfaceIndex,
    OrientationCapability,
    SurfaceKind,
    recovery_nominal,
    recovery_tolerance,
)
from b123d_recognisers._geometry import COORD_FLOOR


def test_recovery_nominal_is_width_controlled_and_rotation_invariant() -> None:
    face = max(Box(100, 1, 1).faces(), key=lambda item: item.area)
    moved = face.rotate(Axis.Z, 45)

    assert recovery_nominal(face) == pytest.approx(recovery_nominal(moved))
    assert recovery_nominal(face) == pytest.approx(2 * 100 / 202)
    assert recovery_tolerance(face) == pytest.approx(
        1e-6 * recovery_nominal(face) + COORD_FLOOR
    )


def test_periodic_seams_do_not_enter_the_physical_boundary_nominal() -> None:
    cylinder_side = max(Cylinder(10, 20).faces(), key=lambda face: face.area)
    sphere = Sphere(10).faces()[0]

    assert recovery_nominal(cylinder_side) == pytest.approx(20.0)
    assert recovery_nominal(sphere) == pytest.approx(math.sqrt(400 * math.pi))


def test_effective_surface_index_keeps_original_node_identity() -> None:
    graph = FaceGraph(Box(1, 2, 3))
    index = EffectiveSurfaceIndex(graph)
    node = graph.nodes[0]

    first = index.fact(node)
    assert index.fact(node) is first
    assert isinstance(first, AnalyticSurfaceFact)
    assert first.node is node
    assert first.kind is SurfaceKind.PLANE
    assert first.orientation is OrientationCapability.NATIVE_ORIENTED
    assert index.oriented_fact(node) is first


def test_effective_surface_index_rejects_foreign_nodes() -> None:
    left = EffectiveSurfaceIndex(FaceGraph(Box(1, 1, 1)))
    foreign = FaceGraph(Box(1, 1, 1)).nodes[0]

    with pytest.raises(ValueError, match="not issued"):
        left.fact(foreign)
