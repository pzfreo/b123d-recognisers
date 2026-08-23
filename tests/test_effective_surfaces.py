import math

import pytest
from build123d import (
    Axis,
    Box,
    Compound,
    Cone,
    Cylinder,
    Face,
    Plane,
    Sphere,
    Torus,
    export_step,
    import_step,
)
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.Geom import Geom_BezierSurface, Geom_RectangularTrimmedSurface
from OCP.GeomConvert import GeomConvert
from OCP.gp import gp_Ax3, gp_Cylinder, gp_Dir, gp_Pnt
from OCP.TColgp import TColgp_Array2OfPnt

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
    assert recovery_tolerance(face) == pytest.approx(1e-6 * recovery_nominal(face) + COORD_FLOOR)


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
    assert fact.certificate is not None
    assert fact.certificate.occt_version == "7.9.3.1"
    assert fact.certificate.maximum_distance_bound == fact.requested_tolerance

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


def test_recogniser_constructor_errors_fail_closed(monkeypatch) -> None:
    class FailedConstruction:
        def __init__(self, _shape) -> None:
            raise RuntimeError("constructor failure")

    monkeypatch.setattr(
        "b123d_recognisers._effective_surfaces.ShapeAnalysis_CanonicalRecognition",
        FailedConstruction,
    )
    native = max(Box(10, 5, 2).faces(), key=lambda face: face.area)
    graph = FaceGraph(_as_bspline_face(native))

    assert (
        EffectiveSurfaceIndex(graph).fact(graph.nodes[0]).reason
        is SurfaceRefusalReason.FIT_UNAVAILABLE
    )


def test_invalid_accepted_primitive_fails_closed(monkeypatch) -> None:
    class InvalidPlaneRecognition:
        def __init__(self, _shape) -> None:
            pass

        def IsPlane(self, _tolerance, result) -> bool:
            result.SetLocation(gp_Pnt(float("nan"), 0, 0))
            return True

        def IsCylinder(self, _tolerance, _result) -> bool:
            return False

        IsCone = IsCylinder
        IsSphere = IsCylinder

        def GetStatus(self) -> int:
            return 0

        def GetGap(self) -> float:
            return 0.0

    monkeypatch.setattr(
        "b123d_recognisers._effective_surfaces.ShapeAnalysis_CanonicalRecognition",
        InvalidPlaneRecognition,
    )
    native = max(Box(10, 5, 2).faces(), key=lambda face: face.area)
    graph = FaceGraph(_as_bspline_face(native))

    assert (
        EffectiveSurfaceIndex(graph).fact(graph.nodes[0]).reason
        is SurfaceRefusalReason.INVALID_RESULT
    )


def test_over_tolerance_success_uses_residual_refusal(monkeypatch) -> None:
    class ExcessiveGapRecognition:
        def __init__(self, _shape) -> None:
            pass

        def IsPlane(self, _tolerance, _result) -> bool:
            return True

        def IsCylinder(self, _tolerance, _result) -> bool:
            return False

        IsCone = IsCylinder
        IsSphere = IsCylinder

        def GetStatus(self) -> int:
            return 0

        def GetGap(self) -> float:
            return 1.0

    monkeypatch.setattr(
        "b123d_recognisers._effective_surfaces.ShapeAnalysis_CanonicalRecognition",
        ExcessiveGapRecognition,
    )
    native = max(Box(10, 5, 2).faces(), key=lambda face: face.area)
    graph = FaceGraph(_as_bspline_face(native))

    assert (
        EffectiveSurfaceIndex(graph).fact(graph.nodes[0]).reason
        is SurfaceRefusalReason.RESIDUAL_EXCEEDED
    )


def test_unpinned_occt_version_disables_recovery_globally(monkeypatch) -> None:
    monkeypatch.setattr("b123d_recognisers._effective_surfaces.OCP.__version__", "future")
    native = max(Box(10, 5, 2).faces(), key=lambda face: face.area)
    graph = FaceGraph(_as_bspline_face(native))

    assert (
        EffectiveSurfaceIndex(graph).fact(graph.nodes[0]).reason
        is SurfaceRefusalReason.UNSUPPORTED_OCCT_CONTRACT
    )


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


def test_locally_bumped_bezier_surface_fails_closed() -> None:
    poles = TColgp_Array2OfPnt(1, 3, 1, 3)
    for u in range(1, 4):
        for v in range(1, 4):
            poles.SetValue(u, v, gp_Pnt(u - 1, v - 1, 0.2 if (u, v) == (2, 2) else 0.0))
    made = BRepBuilderAPI_MakeFace(Geom_BezierSurface(poles), 1e-7)
    graph = FaceGraph(Face(made.Face()))
    fact = EffectiveSurfaceIndex(graph).fact(graph.nodes[0])

    assert fact.reason is SurfaceRefusalReason.FIT_UNAVAILABLE


def test_cone_parameters_retain_apex_position_along_the_axis() -> None:
    lower = max(Cone(6, 3, 12).faces(), key=lambda face: face.area)
    upper = lower.translate((0, 0, 5))
    lower_graph = FaceGraph(lower)
    upper_graph = FaceGraph(upper)
    lower_fact = EffectiveSurfaceIndex(lower_graph).fact(lower_graph.nodes[0])
    upper_fact = EffectiveSurfaceIndex(upper_graph).fact(upper_graph.nodes[0])

    assert isinstance(lower_fact, AnalyticSurfaceFact)
    assert isinstance(upper_fact, AnalyticSurfaceFact)
    assert upper_fact.parameters[2] - lower_fact.parameters[2] == pytest.approx(5.0)
    assert upper_fact.parameters != lower_fact.parameters


@pytest.mark.parametrize(
    "transformed",
    [
        max(Cylinder(5, 12).faces(), key=lambda face: face.area).rotate(
            Axis((0, 0, 0), (1, 1, 0)), 37
        ),
        max(Cylinder(5, 12).faces(), key=lambda face: face.area).mirror(Plane.YZ),
        max(Cylinder(5, 12).faces(), key=lambda face: face.area).scale(3),
    ],
)
def test_transformed_exact_bspline_keeps_native_parameters(transformed: Face) -> None:
    native_graph = FaceGraph(transformed)
    recovered_graph = FaceGraph(_as_bspline_face(transformed))
    native = EffectiveSurfaceIndex(native_graph).fact(native_graph.nodes[0])
    recovered = EffectiveSurfaceIndex(recovered_graph).fact(recovered_graph.nodes[0])

    assert isinstance(native, AnalyticSurfaceFact)
    assert isinstance(recovered, AnalyticSurfaceFact)
    assert recovered.kind is native.kind
    assert recovered.parameters == pytest.approx(native.parameters, abs=1e-8)


def test_step_round_trip_retains_recovery_and_original_imported_node(tmp_path) -> None:
    source = _as_bspline_face(max(Box(10, 5, 2).faces(), key=lambda face: face.area))
    path = tmp_path / "bspline-plane.step"
    assert export_step(source, path)
    imported = import_step(path)
    graph = FaceGraph(imported)
    node = graph.nodes[0]
    fact = EffectiveSurfaceIndex(graph).fact(node)

    assert isinstance(fact, AnalyticSurfaceFact)
    assert fact.node is node
    assert fact.kind is SurfaceKind.PLANE
    assert fact.provenance is SurfaceProvenance.RECOVERED


def test_real_huge_radius_patch_refuses_plane_cylinder_ambiguity() -> None:
    cylinder = gp_Cylinder(gp_Ax3(gp_Pnt(), gp_Dir(0, 0, 1)), 1e8)
    patch = Face(BRepBuilderAPI_MakeFace(cylinder, 0, 1e-7, 0, 1).Face())
    graph = FaceGraph(_as_bspline_face(patch))

    assert (
        EffectiveSurfaceIndex(graph).fact(graph.nodes[0]).reason
        is SurfaceRefusalReason.AMBIGUOUS_PRIMITIVE
    )


def test_equivalent_periodic_seam_parameterisations_have_one_nominal() -> None:
    first_axis = gp_Ax3(gp_Pnt(), gp_Dir(0, 0, 1), gp_Dir(1, 0, 0))
    second_axis = gp_Ax3(gp_Pnt(), gp_Dir(0, 0, 1), gp_Dir(0, 1, 0))
    first = Face(BRepBuilderAPI_MakeFace(gp_Cylinder(first_axis, 10), 0, 2 * math.pi, 0, 20).Face())
    second = Face(
        BRepBuilderAPI_MakeFace(gp_Cylinder(second_axis, 10), 0, 2 * math.pi, 0, 20).Face()
    )

    assert recovery_nominal(first) == pytest.approx(recovery_nominal(second))
    assert recovery_tolerance(first) == pytest.approx(recovery_tolerance(second))


def test_split_equal_surfaces_keep_distinct_original_nodes() -> None:
    left = _as_bspline_face(max(Box(5, 5, 1).faces(), key=lambda face: face.area))
    right = left.translate((5, 0, 0))
    graph = FaceGraph(Compound(children=[left, right]))
    first = EffectiveSurfaceIndex(graph).fact(graph.nodes[0])
    second = EffectiveSurfaceIndex(graph).fact(graph.nodes[1])

    assert isinstance(first, AnalyticSurfaceFact)
    assert isinstance(second, AnalyticSurfaceFact)
    assert first.node is graph.nodes[0]
    assert second.node is graph.nodes[1]
    assert first.node is not second.node


def test_torus_recovery_is_explicitly_unsupported() -> None:
    graph = FaceGraph(Torus(10, 2))

    assert (
        EffectiveSurfaceIndex(graph).fact(graph.nodes[0]).reason
        is SurfaceRefusalReason.UNSUPPORTED_TORUS_RECOVERY
    )
