# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

import json
import math
from pathlib import Path

import pytest
from build123d import (
    Box,
    BuildPart,
    BuildSketch,
    Plane,
    Polygon,
    Pos,
    export_step,
    extrude,
    import_step,
)

from b123d_recognisers._section_adapters import (
    occurrence_to_passage,
    occurrence_to_prismatic_pocket,
    passage_to_occurrence,
    prismatic_pocket_to_occurrence,
)
from b123d_recognisers._sections import (
    BodyRef,
    BodyRefIssuer,
    LocalFrame,
    PlanarSection,
    SectionEnds,
    SectionOccurrence,
    SectionVertex,
    occurrence_geometry_dict,
    section_vertex_dict,
)
from b123d_recognisers.passages import Passage, recognise_passages
from b123d_recognisers.prismatic_pockets import PrismaticPocket, recognise_prismatic_pockets


def _square() -> tuple[tuple[float, float], ...]:
    return ((-2.0, -1.0), (2.0, -1.0), (2.0, 1.0), (-2.0, 1.0))


@pytest.mark.parametrize("axis", ["x", "y", "z"])
def test_passage_private_section_round_trip_is_exact(axis: str) -> None:
    axis_index = "xyz".index(axis)
    transverse = [index for index in range(3) if index != axis_index]
    at = [0.0, 0.0, 0.0]
    at[axis_index] = 7.0
    # Section coordinates use the record's two transverse axes.
    at[transverse[0]] = 0.0
    at[transverse[1]] = 0.0
    record = Passage(axis, 4, 6.0, tuple(at), _square())  # type: ignore[arg-type]
    issuer = BodyRefIssuer()
    body = issuer.issue(signature="body-a")

    occurrence = passage_to_occurrence(record, body_ref=body, body_refs=issuer)

    assert occurrence.ends == SectionEnds(False, False)
    assert occurrence_to_passage(occurrence, body_refs=issuer) == record
    assert occurrence_to_passage(occurrence, body_refs=issuer).to_dict() == record.to_dict()


@pytest.mark.parametrize("open_sign", [-1, 1])
def test_blind_end_topology_preserves_both_open_signs(open_sign: int) -> None:
    record = PrismaticPocket("z", 4, 5.0, open_sign, (0.0, 0.0, 4.0), _square())
    issuer = BodyRefIssuer()
    body = issuer.issue()

    occurrence = prismatic_pocket_to_occurrence(record, body_ref=body, body_refs=issuer)

    assert occurrence.ends == SectionEnds(open_sign == 1, open_sign == -1)
    assert occurrence_to_prismatic_pocket(occurrence, body_refs=issuer) == record


def test_body_references_are_run_local_and_revalidated() -> None:
    first, second = BodyRefIssuer(), BodyRefIssuer()
    body = first.issue(signature="same")
    other = second.issue(signature="same")
    record = Passage("z", 4, 2.0, (0.0, 0.0, 0.0), _square())

    with pytest.raises(ValueError, match="not issued"):
        passage_to_occurrence(record, body_ref=other, body_refs=first)

    forged = object.__new__(BodyRef)
    object.__setattr__(forged, "signature", body.signature)
    object.__setattr__(forged, "_issuer", body._issuer)
    with pytest.raises(ValueError, match="not issued"):
        passage_to_occurrence(record, body_ref=forged, body_refs=first)

    occurrence = passage_to_occurrence(record, body_ref=body, body_refs=first)
    object.__setattr__(body, "signature", "changed")
    with pytest.raises(ValueError, match="mutated"):
        occurrence_to_passage(occurrence, body_refs=first)


def test_proposal_projection_is_primitive_only_and_omits_run_identity() -> None:
    issuer = BodyRefIssuer()
    body = issuer.issue(signature="private")
    record = Passage("z", 4, 2.0, (0.0, 0.0, 0.0), _square())
    occurrence = passage_to_occurrence(record, body_ref=body, body_refs=issuer)

    projected = occurrence_geometry_dict(occurrence, body_refs=issuer)

    assert "body" not in projected
    assert projected["ends"] == {"low_capped": False, "high_capped": False}
    assert json.loads(json.dumps(projected)) == projected


def test_two_arc_circle_has_exact_arc_area_and_centroid() -> None:
    circle = PlanarSection(
        (
            SectionVertex((-1.0, 0.0), -1.0),
            SectionVertex((1.0, 0.0), -1.0),
        )
    )
    assert circle.area == pytest.approx(math.pi)
    assert circle.centroid == pytest.approx((0.0, 0.0), abs=1e-12)


def test_asymmetric_arc_loop_uses_circular_segment_centroid() -> None:
    half_disk = PlanarSection((SectionVertex((-1.0, 0.0), -1.0), SectionVertex((1.0, 0.0))))
    assert half_disk.area == pytest.approx(math.pi / 2)
    assert half_disk.centroid == pytest.approx((0.0, 4 / (3 * math.pi)), abs=1e-12)


def test_equivalent_arc_subdivision_preserves_area_and_centroid() -> None:
    half = math.tan(math.pi / 8)
    two = PlanarSection((SectionVertex((-1.0, 0.0), -1.0), SectionVertex((1.0, 0.0), -1.0)))
    four = PlanarSection(
        (
            SectionVertex((-1.0, 0.0), -half),
            SectionVertex((0.0, 1.0), -half),
            SectionVertex((1.0, 0.0), -half),
            SectionVertex((0.0, -1.0), -half),
        )
    )
    assert four.area == pytest.approx(two.area, abs=1e-12)
    assert four.centroid == pytest.approx(two.centroid, abs=1e-12)


def test_reversed_mixed_loop_has_same_canonical_boundary() -> None:
    original = (
        SectionVertex((0.0, 0.0), 0.5),
        SectionVertex((2.0, 0.0), 0.0),
        SectionVertex((2.0, 2.0), 0.0),
        SectionVertex((0.0, 2.0), 0.0),
    )
    reversed_loop = (
        SectionVertex((0.0, 0.0), 0.0),
        SectionVertex((0.0, 2.0), 0.0),
        SectionVertex((2.0, 2.0), 0.0),
        SectionVertex((2.0, 0.0), -0.5),
    )
    assert PlanarSection(original) == PlanarSection(reversed_loop)


def test_major_arc_and_primitive_projection_are_preserved() -> None:
    section = PlanarSection(
        (
            SectionVertex((-1.0, 0.0), -2.0),
            SectionVertex((1.0, 0.0), -0.5),
        )
    )
    projected = tuple(section_vertex_dict(vertex) for vertex in section.boundary)
    bulges = tuple(item["bulge"] for item in projected)
    assert all(isinstance(value, float) for value in bulges)
    assert any(abs(value) > 1 for value in bulges if isinstance(value, float))
    json.dumps(projected)


def test_tiny_arc_that_serializes_as_zero_fails_closed() -> None:
    with pytest.raises(ValueError, match="collapse a nonzero arc"):
        PlanarSection(
            (
                SectionVertex((0.0, 0.0), 1e-13),
                SectionVertex((1.0, 0.0)),
                SectionVertex((0.0, 1.0)),
            )
        )


def test_self_crossing_line_loop_fails_closed() -> None:
    with pytest.raises(ValueError, match="simple|shared endpoint"):
        PlanarSection(
            tuple(
                SectionVertex(point) for point in ((0.0, 0.0), (2.0, 2.0), (0.0, 2.0), (2.0, 0.0))
            )
        )


@pytest.mark.parametrize(
    "boundary",
    [
        ((0.0, 0.0, 1.0), (2.0, 0.0, 0.0), (0.0, 1.0, 0.0), (2.0, 1.0, 0.0)),
        ((-2.0, 0.0, 1.0), (2.0, 0.0, 0.0), (0.0, -2.0, 1.0), (0.0, 2.0, 0.0)),
    ],
    ids=("line-arc", "arc-arc"),
)
def test_mixed_boundary_intersections_fail_closed(
    boundary: tuple[tuple[float, float, float], ...],
) -> None:
    with pytest.raises(ValueError, match="simple|shared endpoint"):
        PlanarSection(tuple(SectionVertex((x, y), bulge) for x, y, bulge in boundary))


def test_legacy_projection_refuses_arcs_and_inconsistent_records() -> None:
    issuer = BodyRefIssuer()
    body = issuer.issue()
    frame = LocalFrame.principal("z", (0.0, 0.0, 0.0))
    arc = PlanarSection((SectionVertex((-1.0, 0.0), -1.0), SectionVertex((1.0, 0.0), -1.0)))
    occurrence = SectionOccurrence(body, frame, (-1.0, 1.0), arc, SectionEnds(False, False))
    with pytest.raises(ValueError, match="cannot represent arc"):
        occurrence_to_passage(occurrence, body_refs=issuer)

    inconsistent = Passage("z", 4, 2.0, (3.0, 0.0, 0.0), _square())
    with pytest.raises(ValueError, match="centre disagrees"):
        passage_to_occurrence(inconsistent, body_ref=body, body_refs=issuer)


@pytest.mark.parametrize(
    "record, message",
    [
        (Passage("q", 4, 2.0, (0.0, 0.0, 0.0), _square()), "axis"),
        (Passage("z", 4, 0.0, (0.0, 0.0, 0.0), _square()), "span"),
        (Passage("z", 3, 2.0, (0.0, 0.0, 0.0), _square()), "side count"),
    ],
)
def test_invalid_hand_built_passages_fail_closed(record: Passage, message: str) -> None:
    issuer = BodyRefIssuer()
    with pytest.raises(ValueError, match=message):
        passage_to_occurrence(record, body_ref=issuer.issue(), body_refs=issuer)


def test_invalid_hand_built_pocket_open_sign_fails_closed() -> None:
    issuer = BodyRefIssuer()
    record = PrismaticPocket("z", 4, 2.0, 0, (0.0, 0.0, 0.0), _square())
    with pytest.raises(ValueError, match="open_sign"):
        prismatic_pocket_to_occurrence(record, body_ref=issuer.issue(), body_refs=issuer)


def test_legacy_centroid_double_rounding_keeps_exact_record_projection() -> None:
    record = Passage(
        "z",
        3,
        2.0,
        (0.0, 0.0, 0.0),
        ((0.0, 0.0), (0.001, 0.0), (0.0, 0.001)),
    )
    issuer = BodyRefIssuer()
    occurrence = passage_to_occurrence(record, body_ref=issuer.issue(), body_refs=issuer)
    assert occurrence.section.centroid == pytest.approx((0.0, 0.0), abs=1e-12)
    assert occurrence_to_passage(occurrence, body_refs=issuer) == record


def test_free_axis_frame_sign_and_dominant_tie_are_deterministic() -> None:
    positive = LocalFrame.canonical((1.0, 1.0, 1.0), (2.0, 3.0, 4.0))
    reversed_run = LocalFrame.canonical((-1.0, -1.0, -1.0), (2.0, 3.0, 4.0))
    assert positive == reversed_run
    assert positive.run[2] > 0  # Z wins the exact dominant-component tie.


def test_scale_preserves_normalized_section_shape() -> None:
    base = PlanarSection(tuple(SectionVertex(point) for point in _square()))
    scaled = PlanarSection(
        tuple(SectionVertex((point[0] * 1000, point[1] * 1000)) for point in _square())
    )
    assert scaled.area == pytest.approx(base.area * 1_000_000)
    assert scaled.centroid == pytest.approx((base.centroid[0] * 1000, base.centroid[1] * 1000))


def test_cyclic_traversal_produces_the_same_section() -> None:
    vertices = tuple(SectionVertex(point) for point in _square())
    assert PlanarSection(vertices) == PlanarSection(vertices[2:] + vertices[:2])


def _mat_vec(
    matrix: tuple[tuple[float, float, float], ...], point: tuple[float, float, float]
) -> tuple[float, float, float]:
    values = tuple(sum(row[index] * point[index] for index in range(3)) for row in matrix)
    return (float(values[0]), float(values[1]), float(values[2]))


@pytest.mark.parametrize(
    "matrix",
    [
        (
            (1.0, 0.0, 0.0),
            (0.0, math.cos(0.61), -math.sin(0.61)),
            (0.0, math.sin(0.61), math.cos(0.61)),
        ),
        ((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    ],
    ids=("rotation", "mirror"),
)
def test_transformed_section_reconstructs_the_transformed_world_geometry(
    matrix: tuple[tuple[float, float, float], ...],
) -> None:
    source_frame = LocalFrame.principal("z", (3.0, 4.0, 0.0))
    source = PlanarSection(tuple(SectionVertex(point) for point in _square()))
    world: tuple[tuple[float, float, float], ...] = tuple(
        (
            source_frame.origin[0]
            + source_frame.u[0] * vertex.point[0]
            + source_frame.v[0] * vertex.point[1],
            source_frame.origin[1]
            + source_frame.u[1] * vertex.point[0]
            + source_frame.v[1] * vertex.point[1],
            source_frame.origin[2]
            + source_frame.u[2] * vertex.point[0]
            + source_frame.v[2] * vertex.point[1],
        )
        for vertex in source.boundary
    )
    transformed = tuple(_mat_vec(matrix, point) for point in world)
    run = _mat_vec(matrix, source_frame.run)
    centroid = tuple(
        sum(point[index] for point in transformed) / len(transformed) for index in range(3)
    )
    frame = LocalFrame.canonical(run, centroid)  # type: ignore[arg-type]
    local = tuple(
        SectionVertex(
            (
                sum((point[i] - frame.origin[i]) * frame.u[i] for i in range(3)),
                sum((point[i] - frame.origin[i]) * frame.v[i] for i in range(3)),
            )
        )
        for point in transformed
    )
    section = PlanarSection(local)
    reconstructed = tuple(
        tuple(
            frame.origin[index]
            + frame.u[index] * vertex.point[0]
            + frame.v[index] * vertex.point[1]
            for index in range(3)
        )
        for vertex in section.boundary
    )

    assert sorted(reconstructed) == pytest.approx(sorted(transformed), abs=1e-9)


def _step_round_trip(part, path: Path):
    export_step(part, str(path))
    return import_step(str(path))


def test_step_records_pass_through_private_adapters_byte_identically(tmp_path: Path) -> None:
    with BuildPart() as cutter:
        with BuildSketch(Plane.XY):
            Polygon((-8, -6), (8, -6), (0, 8))
        extrude(amount=60, both=True)
    assert cutter.part is not None
    passage_part = Box(60, 40, 20) - cutter.part

    with BuildPart() as pocket_cutter:
        with BuildSketch(Plane.XY):
            Polygon((-8, -6), (8, -6), (0, 8))
        extrude(amount=14)
    assert pocket_cutter.part is not None
    pocket_part = Box(60, 40, 20) - Pos(0, 0, 2) * pocket_cutter.part

    (passage,) = recognise_passages(_step_round_trip(passage_part, tmp_path / "passage.step"))
    (pocket,) = recognise_prismatic_pockets(_step_round_trip(pocket_part, tmp_path / "pocket.step"))
    issuer = BodyRefIssuer()
    passage_body, pocket_body = issuer.issue(), issuer.issue()

    projected_passage = occurrence_to_passage(
        passage_to_occurrence(passage, body_ref=passage_body, body_refs=issuer),
        body_refs=issuer,
    )
    projected_pocket = occurrence_to_prismatic_pocket(
        prismatic_pocket_to_occurrence(pocket, body_ref=pocket_body, body_refs=issuer),
        body_refs=issuer,
    )
    assert projected_passage.to_dict() == passage.to_dict()
    assert projected_pocket.to_dict() == pocket.to_dict()
