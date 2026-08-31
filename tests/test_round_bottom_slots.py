# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Exact analytic U-section blind-slot recognition."""

from __future__ import annotations

import pytest
from build123d import (
    Axis,
    Box,
    BuildLine,
    BuildSketch,
    Compound,
    Cylinder,
    GeomType,
    Keep,
    Line,
    Plane,
    Pos,
    RadiusArc,
    Rot,
    Shell,
    Solid,
    Vector,
    export_step,
    extrude,
    import_step,
    make_face,
)

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers.evidence import build_recognition_evidence
from b123d_recognisers.frames import FramedRecognitionResult, build_framed_recognition_result
from b123d_recognisers.result import build_recognition_result
from b123d_recognisers.round_bottom_slots import (
    RoundBottomBlindSlot,
    _length_tolerance,
    _same_cylinder,
    recognise_round_bottom_blind_slots,
)


def _profile(width: float, radius: float):
    flat = width - 2 * radius
    half_width = width / 2
    half_flat = flat / 2
    with BuildLine() as boundary:
        Line((-half_width, 0), (half_width, 0))
        RadiusArc((half_width, 0), (half_flat, -radius), radius)
        Line((half_flat, -radius), (-half_flat, -radius))
        RadiusArc((-half_flat, -radius), (-half_width, 0), radius)
    with BuildSketch() as sketch:
        make_face(boundary.line)
    return sketch.sketch


def _slot(scale: float = 1.0):
    width, radius, length = 10 * scale, 3 * scale, 20 * scale
    stock = Pos(0, -5 * scale, 0) * Box(30 * scale, 10 * scale, 40 * scale)
    tool = extrude(_profile(width, radius), amount=length, dir=Vector(0, 0, 1))
    return stock - tool


def _split_faces(part, predicate, plane) -> Solid:
    faces = []
    for face in part.faces():
        if predicate(face):
            top, bottom = face.split(plane, Keep.BOTH)
            faces.extend((top, bottom))
        else:
            faces.append(face)
    rebuilt = Solid(Shell(faces))
    assert rebuilt.is_valid
    return rebuilt


def test_round_bottom_blind_slot_has_truthful_dimensions_and_evidence():
    part = _slot()
    ledger = ClaimLedger(FaceGraph(part))

    actual = recognise_round_bottom_blind_slots(part, ledger=ledger)
    assert actual == [
        RoundBottomBlindSlot(
            axis="z",
            open_sign=1,
            length=20.0,
            width_axis="x",
            depth_axis="y",
            radius=3.0,
            flat_width=4.0,
            at=(0.0, -1.5, 10.0),
        )
    ]
    assert len(ledger.claims) == 1
    assert len(ledger.claims[0].defining) == 4

    evidence = build_recognition_evidence(part)
    (feature,) = tuple(ref for ref in evidence.features if evidence.record(ref) == actual[0])
    assert evidence.constituent_faces(feature) == evidence.defining_faces(feature)
    assert len(evidence.defining_faces(feature)) == 4


def test_axis_open_sign_scale_and_step_roundtrip_are_stable(tmp_path):
    base = _slot()
    path = tmp_path / "round-bottom-slot.step"
    export_step(base, path)
    assert recognise_round_bottom_blind_slots(
        import_step(path)
    ) == recognise_round_bottom_blind_slots(base)

    for part, axis, sign in (
        (base, "z", 1),
        (Rot(180, 0, 0) * base, "z", -1),
        (Rot(90, 0, 0) * base, "y", -1),
        (Rot(0, 90, 0) * base, "x", 1),
    ):
        assert [
            (record.axis, record.open_sign) for record in recognise_round_bottom_blind_slots(part)
        ] == [(axis, sign)]

    for scale in (0.001, 1000.0):
        (record,) = recognise_round_bottom_blind_slots(_slot(scale))
        assert record.length == pytest.approx(20 * scale, abs=max(0.001, scale * 1e-6))
        assert record.radius == pytest.approx(3 * scale, abs=max(0.001, scale * 1e-6))


def test_local_cylinder_equality_accepts_and_rejects_both_sides_of_the_tolerance():
    radius = 3.0
    tolerance = _length_tolerance(radius)
    reference = (radius, 2, (0.0, 0.0, 0.0))

    assert _same_cylinder(reference, (radius + 0.5 * tolerance, 2, (0.0, 0.0, 1.0)))
    assert not _same_cylinder(reference, (radius + 2 * tolerance, 2, (0.0, 0.0, 1.0)))
    assert not _same_cylinder(reference, (radius, 2, (2 * tolerance, 0.0, 1.0)))


def test_translation_mirror_and_arbitrary_framed_presentation_preserve_the_feature():
    base = _slot()
    (translated,) = recognise_round_bottom_blind_slots(Pos(17, -23, 9) * base)
    assert translated.at == pytest.approx((17.0, -24.5, 19.0), abs=1e-3)
    assert (translated.axis, translated.open_sign) == ("z", 1)

    (mirrored,) = recognise_round_bottom_blind_slots(base.mirror(Plane.XY))
    assert (mirrored.axis, mirrored.open_sign) == ("z", -1)
    assert (mirrored.radius, mirrored.flat_width, mirrored.length) == (3.0, 4.0, 20.0)

    presented = Pos(-31, 17, 23) * base.rotate(Axis((0, 0, 0), (1, 1, 0)), 37)
    assert recognise_round_bottom_blind_slots(presented) == []
    framed = build_framed_recognition_result(presented, rotational=False)
    assert isinstance(framed, FramedRecognitionResult)
    (record,) = framed.result.round_bottom_blind_slots
    assert (record.radius, record.flat_width, record.length) == (3.0, 4.0, 20.0)


def test_cap_side_and_context_subdivisions_preserve_the_logical_feature():
    base = _slot()
    expected = recognise_round_bottom_blind_slots(base)
    cap_split = _split_faces(
        base,
        lambda face: abs(face.center().Z) < 1e-8 and face.area < 30,
        Plane.YZ,
    )
    side_split = _split_faces(
        base,
        lambda face: (
            face.geom_type == GeomType.CYLINDER
            or (abs(face.center().Y + 3) < 1e-7 and abs(face.center().Z - 10) < 1e-7)
        ),
        Plane.XY.offset(10),
    )
    mouth_split = _split_faces(
        base,
        lambda face: abs(face.center().Z - 20) < 1e-7,
        Plane.YZ,
    )

    for part in (cap_split, side_split, mouth_split):
        ledger = ClaimLedger(FaceGraph(part))
        assert recognise_round_bottom_blind_slots(part, ledger=ledger) == expected
        assert set(ledger.claims[0].defining) <= set(ledger.graph.nodes)


def test_cap_holes_and_stock_continuations_are_rejected():
    base = _slot()
    cap_hole = base - Pos(0, -1.5, -5) * Cylinder(0.5, 10)
    cap_breakout = base - Pos(0, -1.5, -5) * Box(2, 2, 10)

    assert recognise_round_bottom_blind_slots(cap_hole) == []
    assert recognise_round_bottom_blind_slots(cap_breakout) == []


def test_floor_holes_and_boundary_notches_are_rejected():
    base = _slot()
    floor_hole = base - Pos(0, -3, 10) * Rot(90, 0, 0) * Cylinder(0.5, 7)
    floor_notch = base - Pos(0, -4, 10) * Box(1, 4, 2)

    assert recognise_round_bottom_blind_slots(floor_hole) == []
    assert recognise_round_bottom_blind_slots(floor_notch) == []


def test_through_and_doubly_capped_u_sections_are_rejected():
    stock = Pos(0, -5, 0) * Box(30, 10, 40)
    through = stock - Pos(0, 0, -20) * extrude(_profile(10, 3), amount=40, dir=Vector(0, 0, 1))
    sealed = stock - Pos(0, 0, -10) * extrude(_profile(10, 3), amount=20, dir=Vector(0, 0, 1))

    assert recognise_round_bottom_blind_slots(through) == []
    assert recognise_round_bottom_blind_slots(sealed) == []


def test_rectangular_notches_and_top_open_obround_pockets_are_other_families():
    stock = Pos(0, -5, 0) * Box(30, 10, 40)
    rectangular = stock - Pos(0, -1.5, 10) * Box(10, 3, 20)
    sealed_mouth = stock - Pos(0, -1, 0) * extrude(_profile(10, 3), amount=20, dir=Vector(0, 0, 1))

    assert recognise_round_bottom_blind_slots(rectangular) == []
    assert recognise_round_bottom_blind_slots(sealed_mouth) == []


def test_material_inside_the_claimed_sweep_rejects_the_candidate():
    interrupted = _slot() + Pos(0, -2, 10) * Box(1, 2, 10)
    assert recognise_round_bottom_blind_slots(interrupted) == []


def test_compound_members_and_equal_occurrences_remain_distinct():
    first = _slot()
    second = Pos(100, 0, 0) * _slot()
    part = Compound(children=[first, second])

    records = recognise_round_bottom_blind_slots(part)
    assert len(records) == 2
    assert records[0].at != records[1].at

    evidence = build_recognition_evidence(Compound(children=[_slot(), _slot()]))
    refs = tuple(
        ref for ref in evidence.features if isinstance(evidence.record(ref), RoundBottomBlindSlot)
    )
    assert len(refs) == 2
    assert refs[0] is not refs[1]


def test_two_slots_on_one_body_are_distinct_and_do_not_overlap_recess_families():
    stock = Pos(0, -5, 0) * Box(50, 10, 40)
    tool = extrude(_profile(10, 3), amount=20, dir=Vector(0, 0, 1))
    part = stock - Pos(-13, 0, 0) * tool - Pos(13, 0, 0) * tool

    direct = recognise_round_bottom_blind_slots(part)
    aggregate = build_recognition_result(part)

    assert len(direct) == 2
    assert aggregate.round_bottom_blind_slots == tuple(direct)
    assert aggregate.slots == aggregate.pockets == aggregate.channels == ()
