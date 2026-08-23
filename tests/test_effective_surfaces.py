import math

import pytest
from build123d import Axis, Box, Cone, Cylinder, Face, Sphere
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.Geom import Geom_RectangularTrimmedSurface
from OCP.GeomConvert import GeomConvert

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._effective_surfaces import (
    AnalyticSurfaceFact,
    EffectiveSurfaceIndex,
    OrientationCapability,
    SurfaceKind,
    SurfaceProvenance,
    SurfaceRefusalReason,
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


def _as_bspline_face(face: Face) -> Face:
    adaptor = BRepAdaptor_Surface(face.wrapped)
    surface = BRep_Tool.Surface_s(face.wrapped)
    trimmed = Geom_RectangularTrimmedSurface(
        surface,
        adaptor.FirstUParameter(),
        adaptor.LastUParameter(),
        adaptor.FirstVParameter(),
        adaptor.LastVParameter(),
    )
    bspline = GeomConvert.SurfaceToBSplineSurface_s(trimmed)
    made = BRepBuilderAPI_MakeFace(
        bspline,
        adaptor.FirstUParameter(),
        adaptor.LastUParameter(),
        adaptor.FirstVParameter(),
        adaptor.LastVParameter(),
        1e-7,
    )
    return Face(made.Face())


def test_exact_bspline_plane_recovers_as_unoriented_original_node() -> None:
    native = max(Box(10, 5, 2).faces(), key=lambda face: face.area)
    graph = FaceGraph(_as_bspline_face(native))
    node = graph.nodes[0]
    fact = EffectiveSurfaceIndex(graph).fact(node)

    assert isinstance(fact, AnalyticSurfaceFact)
    assert fact.node is node
    assert fact.kind is SurfaceKind.PLANE
    assert fact.provenance is SurfaceProvenance.RECOVERED
    assert fact.orientation is OrientationCapability.RECOVERED_UNORIENTED
    assert fact.kernel_reported_gap == 0.0
    assert fact.requested_tolerance > 0.0

    with pytest.raises(ValueError, match="ORIENTATION_UNPROVEN"):
        EffectiveSurfaceIndex(graph).oriented_fact(node)


@pytest.mark.parametrize(
    ("native", "kind"),
    [
        (max(Cylinder(5, 12).faces(), key=lambda face: face.area), SurfaceKind.CYLINDER),
        (max(Cone(6, 3, 12).faces(), key=lambda face: face.area), SurfaceKind.CONE),
        (Sphere(7).faces()[0], SurfaceKind.SPHERE),
    ],
)
def test_exact_bspline_curved_primitives_recover_without_orientation(
    native: Face, kind: SurfaceKind
) -> None:
    graph = FaceGraph(_as_bspline_face(native))
    node = graph.nodes[0]
    fact = EffectiveSurfaceIndex(graph).fact(node)

    assert isinstance(fact, AnalyticSurfaceFact)
    assert fact.node is node
    assert fact.kind is kind
    assert fact.provenance is SurfaceProvenance.RECOVERED
    assert fact.orientation is OrientationCapability.RECOVERED_UNORIENTED
    assert fact.parameters


def test_multiple_passing_fits_refuse_instead_of_using_call_order(monkeypatch) -> None:
    class AmbiguousRecognition:
        def __init__(self, _shape) -> None:
            pass

        def IsPlane(self, _tolerance, _result) -> bool:
            return True

        def IsCylinder(self, _tolerance, _result) -> bool:
            return True

        def IsCone(self, _tolerance, _result) -> bool:
            return False

        def IsSphere(self, _tolerance, _result) -> bool:
            return False

        def GetStatus(self) -> int:
            return 0

        def GetGap(self) -> float:
            return 0.0

    monkeypatch.setattr(
        "b123d_recognisers._effective_surfaces.ShapeAnalysis_CanonicalRecognition",
        AmbiguousRecognition,
    )
    native = max(Box(10, 5, 2).faces(), key=lambda face: face.area)
    graph = FaceGraph(_as_bspline_face(native))
    fact = EffectiveSurfaceIndex(graph).fact(graph.nodes[0])

    assert fact.reason is SurfaceRefusalReason.AMBIGUOUS_PRIMITIVE


def test_kernel_errors_fail_closed(monkeypatch) -> None:
    class FailedRecognition:
        def __init__(self, _shape) -> None:
            pass

        def IsPlane(self, _tolerance, _result) -> bool:
            raise RuntimeError("kernel failure")

        IsCylinder = IsPlane
        IsCone = IsPlane
        IsSphere = IsPlane

    monkeypatch.setattr(
        "b123d_recognisers._effective_surfaces.ShapeAnalysis_CanonicalRecognition",
        FailedRecognition,
    )
    native = max(Box(10, 5, 2).faces(), key=lambda face: face.area)
    graph = FaceGraph(_as_bspline_face(native))
    fact = EffectiveSurfaceIndex(graph).fact(graph.nodes[0])

    assert fact.reason is SurfaceRefusalReason.FIT_UNAVAILABLE


@pytest.mark.parametrize(
    "native",
    [
        max(Box(10, 5, 2).faces(), key=lambda face: face.area),
        max(Cylinder(5, 12).faces(), key=lambda face: face.area),
        max(Cone(6, 3, 12).faces(), key=lambda face: face.area),
        Sphere(7).faces()[0],
    ],
)
def test_native_and_exact_bspline_use_the_same_canonical_parameters(native: Face) -> None:
    native_graph = FaceGraph(native)
    recovered_graph = FaceGraph(_as_bspline_face(native))
    native_fact = EffectiveSurfaceIndex(native_graph).fact(native_graph.nodes[0])
    recovered_fact = EffectiveSurfaceIndex(recovered_graph).fact(recovered_graph.nodes[0])

    assert isinstance(native_fact, AnalyticSurfaceFact)
    assert isinstance(recovered_fact, AnalyticSurfaceFact)
    assert recovered_fact.kind is native_fact.kind
    assert recovered_fact.parameters == pytest.approx(native_fact.parameters, abs=1e-9)
