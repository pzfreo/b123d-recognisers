# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Quarter-sector circular blind-step recognition and ownership."""

from __future__ import annotations

import pytest
from build123d import (
    Align,
    Box,
    Cylinder,
    GeomType,
    Keep,
    Plane,
    Pos,
    Rot,
    Shell,
    Solid,
    export_step,
    import_step,
)

from b123d_recognisers import (
    CircularBlindStep,
    build_recognition_result,
    recognise_circular_blind_steps,
    recognise_fillets,
)
from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._reconcile import fillets_that_are_not_circular_blind_steps
from b123d_recognisers.fillets import Fillet


def _step(scale: float = 1.0):
    stock = Box(40 * scale, 30 * scale, 20 * scale)
    cutter = Pos(20 * scale, 15 * scale, 0) * Cylinder(
        6 * scale,
        10 * scale,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )
    return stock - cutter


def _split_faces(part, predicate, plane) -> Solid:
    faces = []
    for face in part.faces():
        if predicate(face):
            split = face.split(plane, Keep.BOTH)
            assert len(split) == 2
            faces.extend(split)
        else:
            faces.append(face)
    rebuilt = Solid(Shell(faces))
    assert rebuilt.is_valid
    return rebuilt


def test_circular_blind_step_has_truthful_dimensions_claims_and_precedence():
    part = _step()
    ledger = ClaimLedger(FaceGraph(part))

    actual = recognise_circular_blind_steps(part, ledger=ledger)
    assert actual == [
        CircularBlindStep(
            axis="z",
            open_sign=1,
            length=10.0,
            section_axes=("x", "y"),
            section_signs=(-1, -1),
            radius=6.0,
            at=(20.0, 15.0, 5.0),
        )
    ]
    assert len(ledger.claims) == 1
    assert len(ledger.claims[0].defining) == 2

    # Direct Fillet recognition remains backward compatible. The aggregate owns the more
    # specific interpretation and removes only this claimed curved patch.
    assert len(recognise_fillets(part)) == 1
    result = build_recognition_result(part)
    assert result.circular_blind_steps == tuple(actual)
    assert result.fillets == ()


@pytest.mark.parametrize(
    ("part", "axis", "open_sign", "section_axes", "section_signs"),
    [
        (_step(), "z", 1, ("x", "y"), (-1, -1)),
        (Rot(180, 0, 0) * _step(), "z", -1, ("x", "y"), (-1, 1)),
        (Rot(90, 0, 0) * _step(), "y", -1, ("x", "z"), (-1, -1)),
        (Rot(0, 90, 0) * _step(), "x", 1, ("y", "z"), (-1, 1)),
        (Rot(0, 180, 0) * _step(), "z", -1, ("x", "y"), (1, -1)),
        (Rot(0, 0, 90) * _step(), "z", 1, ("x", "y"), (1, -1)),
        (Rot(0, 0, -90) * _step(), "z", 1, ("x", "y"), (-1, 1)),
    ],
)
def test_axis_open_end_and_quadrant_are_geometric(
    part, axis, open_sign, section_axes, section_signs
):
    (record,) = recognise_circular_blind_steps(part)
    assert (record.axis, record.open_sign, record.section_axes, record.section_signs) == (
        axis,
        open_sign,
        section_axes,
        section_signs,
    )


def test_scale_and_step_round_trip_are_stable(tmp_path):
    for scale in (0.001, 1000.0):
        (record,) = recognise_circular_blind_steps(_step(scale))
        assert record.radius == pytest.approx(6 * scale, abs=max(0.001, scale * 1e-6))
        assert record.length == pytest.approx(10 * scale, abs=max(0.001, scale * 1e-6))

    expected = recognise_circular_blind_steps(_step())
    path = tmp_path / "circular-blind-step.step"
    export_step(_step(), path)
    imported = import_step(path)
    assert recognise_circular_blind_steps(imported) == expected
    assert build_recognition_result(imported).circular_blind_steps == tuple(expected)


def test_cap_and_cylinder_subdivisions_preserve_record_and_all_claims():
    base = _step()
    expected = recognise_circular_blind_steps(base)
    cap_split = _split_faces(
        base,
        lambda face: (
            face.geom_type == GeomType.PLANE
            and abs(face.center().Z) < 1e-8
            and face.area < 40
        ),
        Plane.YZ.offset(17),
    )
    run_split = _split_faces(
        base,
        lambda face: face.geom_type == GeomType.CYLINDER,
        Plane.XY.offset(5),
    )
    angular_split = _split_faces(
        base,
        lambda face: face.geom_type == GeomType.CYLINDER,
        Plane.YZ.offset(17),
    )
    run_and_angular_split = _split_faces(
        run_split,
        lambda face: face.geom_type == GeomType.CYLINDER,
        Plane.YZ.offset(17),
    )

    for part in (cap_split, run_split, angular_split, run_and_angular_split):
        ledger = ClaimLedger(FaceGraph(part))
        assert recognise_circular_blind_steps(part, ledger=ledger) == expected
        assert len(ledger.claims[0].defining) > 2
        aggregate = build_recognition_result(part)
        assert aggregate.circular_blind_steps == tuple(expected)
        assert aggregate.fillets == ()


def test_absent_second_or_wrong_cap_and_interrupted_surfaces_fail_closed():
    stock = Box(40, 30, 20)
    through = stock - Pos(20, 15, -10) * Cylinder(
        6, 40, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    sealed = stock - Pos(20, 15, -5) * Cylinder(
        6, 10, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    cylinder_notch = _step() - Pos(15, 15, 5) * Box(2, 4, 2)
    cap_hole = _step() - Pos(17, 12, -1) * Cylinder(
        0.5, 2, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )

    for part in (through, sealed, cylinder_notch, cap_hole):
        assert recognise_circular_blind_steps(part) == []


def test_partial_cap_radial_and_opening_contexts_fail_closed():
    # Each extra removal replaces only part of a required topological boundary with a new face.
    # Merely finding some surviving convex context is insufficient: the whole seam/generator/arc
    # must belong to the one normalized context region.
    partial_cap_seam = _step() - Pos(17, 12, -1) * Box(2, 2, 3)
    partial_radial_context = _step() - Pos(19, 8.5, 5) * Box(4, 3, 3)
    partial_opening_context = _step() - Pos(14.8, 9.8, 10) * Box(3, 3, 4)

    for part in (partial_cap_seam, partial_radial_context, partial_opening_context):
        assert recognise_circular_blind_steps(part) == []


def test_half_full_and_material_bearing_sectors_fail_closed():
    stock = Box(40, 30, 20)
    # Centring the same cutter on only one stock boundary exposes a half cylinder; centring it
    # internally exposes a full cylindrical cavity. Neither is the quarter-sector record.
    half = stock - Pos(0, 15, 0) * Cylinder(
        6, 10, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    full = stock - Pos(0, 0, 0) * Cylinder(
        6, 10, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    # Remove a box from the cutter before subtraction, leaving same-solid material within the
    # nominal sweep. Boundary topology and exact occupancy independently make this fail closed.
    cutter = Pos(20, 15, 0) * Cylinder(
        6, 10, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    cutter -= Pos(14, 12, 5) * Box(4, 1, 4)
    bridge = stock - cutter

    for part in (half, full, bridge):
        assert recognise_circular_blind_steps(part) == []


def test_ordinary_edge_fillet_is_not_a_circular_blind_step():
    part = Box(20, 20, 20)
    rounded = part.fillet(2, part.edges().filter_by(GeomType.LINE)[0:1])

    assert recognise_circular_blind_steps(rounded) == []
    assert recognise_fillets(rounded)
    assert build_recognition_result(rounded).fillets


def test_reconciliation_requires_nonempty_identity_subset_claims():
    graph = FaceGraph(_step())
    nodes = graph.nodes
    assert len(nodes) >= 2
    ledger = ClaimLedger(graph)
    step = CircularBlindStep("z", 1, 10, ("x", "y"), (-1, -1), 6, (20, 15, 5))
    fillet = Fillet("z", 6, (15.757, 10.757, 5))
    ledger.add_defining(step, {nodes[0], nodes[1]})
    ledger.add_defining(fillet, {nodes[0]})
    assert fillets_that_are_not_circular_blind_steps([fillet], [step], ledger) == []

    unclaimed = Fillet("z", 6, fillet.at)
    assert unclaimed == fillet and unclaimed is not fillet
    assert fillets_that_are_not_circular_blind_steps([unclaimed], [step], ledger) == [unclaimed]
