from __future__ import annotations

import json
import math

import pytest
from build123d import Box, Cylinder, Pos, Rot

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
