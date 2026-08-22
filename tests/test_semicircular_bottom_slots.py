# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Sharp two-leg, semicircular-bottom blind-slot recognition."""

from __future__ import annotations

import pytest
from build123d import (
    Align,
    Box,
    BuildSketch,
    Cylinder,
    GeomType,
    Keep,
    Plane,
    Pos,
    Rectangle,
    Rot,
    Shell,
    Solid,
    Vector,
    export_step,
    extrude,
    fillet,
    import_step,
)

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers.result import build_recognition_result
from b123d_recognisers.round_bottom_slots import (
    SemicircularBottomBlindSlot,
    recognise_round_bottom_blind_slots,
    recognise_semicircular_bottom_blind_slots,
)


def _profile(radius: float = 3, leg_depth: float = 4):
    with BuildSketch() as sketch:
        Rectangle(2 * radius, leg_depth + radius, align=(Align.CENTER, Align.MAX))
        bottom = [
            vertex
            for vertex in sketch.vertices()
            if abs(vertex.Y + leg_depth + radius) < 1e-8
        ]
        fillet(bottom, radius=radius)
    return sketch.sketch


def _slot(scale: float = 1.0):
    stock = Pos(0, -6 * scale, 0) * Box(30 * scale, 12 * scale, 40 * scale)
    tool = extrude(
        _profile(3 * scale, 4 * scale), amount=20 * scale, dir=Vector(0, 0, 1)
    )
    return stock - tool


def _split_faces(part, predicate, plane) -> Solid:
    faces = []
    for face in part.faces():
        if predicate(face):
            first, second = face.split(plane, Keep.BOTH)
            faces.extend((first, second))
        else:
            faces.append(face)
    rebuilt = Solid(Shell(faces))
    assert rebuilt.is_valid
    return rebuilt


def test_semicircular_bottom_blind_slot_has_truthful_dimensions_and_claims():
    part = _slot()
    ledger = ClaimLedger(FaceGraph(part))

    actual = recognise_semicircular_bottom_blind_slots(part, ledger=ledger)
    assert actual == [
        SemicircularBottomBlindSlot(
            axis="z",
            open_sign=1,
            length=20.0,
            width_axis="x",
            depth_axis="y",
            radius=3.0,
            leg_depth=4.0,
            at=(0.0, -3.5, 10.0),
        )
    ]
    assert len(ledger.claims) == 1
    assert len(ledger.claims[0].defining) == 4


@pytest.mark.parametrize(
    ("part", "axis", "sign"),
    [
        (_slot(), "z", 1),
        (Rot(180, 0, 0) * _slot(), "z", -1),
        (Rot(90, 0, 0) * _slot(), "y", -1),
        (Rot(0, 90, 0) * _slot(), "x", 1),
    ],
)
def test_axis_and_open_sign_are_geometric(part, axis, sign):
    (record,) = recognise_semicircular_bottom_blind_slots(part)
    assert (record.axis, record.open_sign) == (axis, sign)


def test_scale_and_sibling_profile_are_stable_and_distinct():
    for scale in (0.001, 1000.0):
        (record,) = recognise_semicircular_bottom_blind_slots(_slot(scale))
        assert record.radius == pytest.approx(3 * scale, abs=max(0.001, scale * 1e-6))
        assert record.leg_depth == pytest.approx(4 * scale, abs=max(0.001, scale * 1e-6))
    assert recognise_round_bottom_blind_slots(_slot()) == []


def test_step_and_defining_surface_subdivisions_preserve_the_feature(tmp_path):
    base = _slot()
    expected = recognise_semicircular_bottom_blind_slots(base)
    path = tmp_path / "semicircular-bottom-slot.step"
    export_step(base, path)
    imported = import_step(path)
    assert recognise_semicircular_bottom_blind_slots(imported) == expected
    assert build_recognition_result(imported).semicircular_bottom_blind_slots == tuple(expected)

    cap_split = _split_faces(
        base,
        lambda face: abs(face.center().Z) < 1e-8 and face.area < 50,
        Plane.YZ,
    )
    side_split = _split_faces(
        base,
        lambda face: (
            face.geom_type == GeomType.CYLINDER
            or (abs(abs(face.center().X) - 3) < 1e-7 and abs(face.center().Z - 10) < 1e-7)
        ),
        Plane.XY.offset(10),
    )
    angular_split = _split_faces(
        base,
        lambda face: face.geom_type == GeomType.CYLINDER,
        Plane.YZ,
    )
    for part in (cap_split, side_split, angular_split):
        ledger = ClaimLedger(FaceGraph(part))
        assert recognise_semicircular_bottom_blind_slots(part, ledger=ledger) == expected
        assert len(ledger.claims[0].defining) > 4
        assert build_recognition_result(part).semicircular_bottom_blind_slots == tuple(expected)


def test_missing_second_cap_and_interrupted_leg_fail_closed():
    stock = Pos(0, -6, 0) * Box(30, 12, 40)
    through = stock - Pos(0, 0, -20) * extrude(
        _profile(), amount=40, dir=Vector(0, 0, 1)
    )
    sealed = stock - Pos(0, 0, -10) * extrude(
        _profile(), amount=20, dir=Vector(0, 0, 1)
    )
    leg_hole = _slot() - Pos(-3, -2, 10) * Rot(90, 0, 0) * Cylinder(0.5, 8)
    leg_notch = _slot() - Pos(-3, -2, 10) * Box(3, 1, 2)

    for part in (through, sealed, leg_hole, leg_notch):
        assert recognise_semicircular_bottom_blind_slots(part) == []


def test_complete_profile_supersedes_rectangular_wall_fragments_in_aggregate():
    result = build_recognition_result(_slot())

    assert len(result.semicircular_bottom_blind_slots) == 1
    assert result.slots == ()
    assert result.pockets == ()
