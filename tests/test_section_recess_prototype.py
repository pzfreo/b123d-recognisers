from __future__ import annotations

import json
import math

import pytest
from build123d import (
    Box,
    BuildPart,
    BuildSketch,
    Compound,
    Cylinder,
    Plane,
    Polygon,
    Pos,
    Rot,
    export_step,
    extrude,
    import_step,
)

from b123d_recognisers._section_recess_prototype import (
    SectionRecessClassification,
    build_section_recess_prototype,
    project_section_recess_geometry,
)
from b123d_recognisers._sections import (
    BodyRefIssuer,
    LocalFrame,
    PlanarSection,
    SectionEnds,
    SectionOccurrence,
    SectionVertex,
)


def _obround(*, straight: float = 12, width: float = 6, depth: float = 8):
    radius = width / 2
    return (
        Box(straight, width, depth)
        + Pos(-straight / 2, 0, 0) * Cylinder(radius, depth)
        + Pos(straight / 2, 0, 0) * Cylinder(radius, depth)
    )


def _blind_pocket(*, angle: float = 30):
    return Box(60, 50, 12) - Pos(0, 0, 4) * Rot(0, 0, angle) * _obround()


def _polygonal_cutter(points, *, depth: float = 8):
    with BuildPart() as cutter:
        with BuildSketch(Plane.XY):
            Polygon(*points)
        extrude(amount=depth)
    return cutter.part


def _polygonal_pocket(points, *, placement=None):
    if placement is None:
        placement = Rot(17, 31, 43)
    raw = Box(60, 50, 12) - Pos(0, 0, 4) * _polygonal_cutter(points)
    return placement * raw


def test_prototype_emits_reconstructible_indexed_json() -> None:
    document = build_section_recess_prototype(_blind_pocket())

    assert [body.index for body in document.bodies] == [0]
    assert [face.index for face in document.faces] == list(range(11))
    (occurrence,) = document.occurrences
    assert occurrence.index == 0
    assert occurrence.body == 0
    assert occurrence.classification.to_dict() == {
        "feature_kind": "pocket",
        "section_shape": "obround",
    }
    assert len(occurrence.evidence.defining_faces) == 4
    assert len(occurrence.evidence.constituent_faces) == 5
    assert occurrence.geometry.run_interval == (0.0, 6.0)
    assert occurrence.geometry.ends.low.condition == "capped"
    assert occurrence.geometry.ends.high.condition == "open"

    boundary = occurrence.geometry.profile.boundary
    section = PlanarSection(tuple(SectionVertex(vertex.point, vertex.bulge) for vertex in boundary))
    assert section.centroid == pytest.approx((0.0, 0.0), abs=8e-4)
    assert section.area == pytest.approx(72 + 9 * math.pi, abs=2e-2)
    json.dumps(document.to_dict())


@pytest.mark.parametrize(
    "placement",
    [Rot(90, 0, 0), Rot(0, 90, 0), Rot(17, 31, 43) * Pos(11, -7, 5)],
)
def test_prototype_is_covariant_under_rigid_presentation(placement) -> None:
    document = build_section_recess_prototype(placement * _blind_pocket())

    (occurrence,) = document.occurrences
    span = occurrence.geometry.run_interval[1] - occurrence.geometry.run_interval[0]
    assert span == pytest.approx(6.0, abs=2e-3)
    assert occurrence.geometry.profile.closure == "closed"
    assert tuple(vertex.bulge for vertex in occurrence.geometry.profile.boundary).count(1.0) == 2


def test_prototype_does_not_publish_a_boss_as_a_pocket() -> None:
    boss = Box(60, 50, 6) + Pos(0, 0, 7) * Rot(0, 0, 30) * _obround()

    assert build_section_recess_prototype(boss).occurrences == ()


@pytest.mark.parametrize(
    ("shape", "points"),
    [
        ("triangular", ((-4.0, -2.0), (4.0, -2.0), (0.0, 4.0))),
        ("rectangular", ((-4.0, -2.0), (4.0, -2.0), (4.0, 2.0), (-4.0, 2.0))),
        (
            "hexagonal",
            ((-4.0, 0.0), (-2.0, -3.0), (2.0, -3.0), (4.0, 0.0), (2.0, 3.0), (-2.0, 3.0)),
        ),
    ],
)
def test_unified_contract_projects_free_axis_polygonal_sections(shape, points) -> None:
    issuer = BodyRefIssuer()
    occurrence = SectionOccurrence(
        issuer.issue(),
        LocalFrame.canonical((1.0, 2.0, 3.0), (0.0, 0.0, 0.0)),
        (-2.0, 5.0),
        PlanarSection(tuple(SectionVertex(point) for point in points)),
        SectionEnds(True, False),
    )

    geometry = project_section_recess_geometry(occurrence, body_refs=issuer)
    classification = SectionRecessClassification("pocket", shape)

    assert geometry.type == "section_recess"
    assert geometry.run_interval == (-2.0, 5.0)
    assert all(vertex.bulge == 0.0 for vertex in geometry.profile.boundary)
    assert classification.section_shape == shape


@pytest.mark.parametrize(
    ("shape", "points"),
    [
        ("triangular", ((-4.0, -3.0), (4.0, -3.0), (0.0, 5.0))),
        ("rectangular", ((-5.0, -3.0), (5.0, -3.0), (5.0, 3.0), (-5.0, 3.0))),
        (
            "hexagonal",
            ((-5.0, 0.0), (-2.5, -4.0), (2.5, -4.0), (5.0, 0.0), (2.5, 4.0), (-2.5, 4.0)),
        ),
    ],
)
def test_free_frame_floor_proof_recognises_polygonal_pockets(shape, points) -> None:
    document = build_section_recess_prototype(_polygonal_pocket(points))

    (occurrence,) = document.occurrences
    assert occurrence.classification.section_shape == shape
    assert len(occurrence.evidence.defining_faces) == len(points)
    assert len(occurrence.evidence.constituent_faces) == len(points) + 1


def test_polygonal_proof_is_stable_after_step_round_trip(tmp_path) -> None:
    path = tmp_path / "oriented-triangle.step"
    export_step(_polygonal_pocket(((-4, -3), (4, -3), (0, 5))), path)

    (occurrence,) = build_section_recess_prototype(import_step(path)).occurrences

    assert occurrence.classification.section_shape == "triangular"


def test_polygonal_proof_rejects_through_cut_and_boss() -> None:
    points = ((-4.0, -3.0), (4.0, -3.0), (0.0, 5.0))
    through = Box(60, 50, 12) - Pos(0, 0, -7) * _polygonal_cutter(points, depth=14)
    boss = Box(60, 50, 6) + Pos(0, 0, 7) * _polygonal_cutter(points)

    assert build_section_recess_prototype(through).occurrences == ()
    assert build_section_recess_prototype(boss).occurrences == ()


def test_equal_polygonal_pockets_on_separate_bodies_keep_ownership() -> None:
    points = ((-4.0, -3.0), (4.0, -3.0), (0.0, 5.0))
    first = _polygonal_pocket(points)
    second = Pos(100, 0, 0) * _polygonal_pocket(points)

    document = build_section_recess_prototype(Compound([first, second]))

    assert len(document.occurrences) == 2
    assert {occurrence.body for occurrence in document.occurrences} == {0, 1}
