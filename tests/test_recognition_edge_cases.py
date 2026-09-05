# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle


from dataclasses import replace

import build123d.topology.shape_core as shape_core
from build123d import Align, Axis, Box, Cylinder, GeomType, Pos, fillet

from quiddity import (
    Slot,
    SlotArray,
    SlotGrid,
    recognise_fillets,
    recognise_flats,
    recognise_slot_patterns,
    recognise_slots,
)
from tools._legacy_recognition import (
    Pocket,
    PocketArray,
    PocketGrid,
    recognise_pocket_patterns,
    recognise_pockets,
)

_CENTRE = (Align.CENTER, Align.CENTER, Align.CENTER)


def _filleted_plate():
    plate = fillet(Box(90, 60, 20).edges().filter_by(Axis.Z), 6)
    for i in range(3):
        plate -= Pos(-25 + i * 25, 0, 0) * Cylinder(4, 20)
    return plate


def test_fillet_neighbour_search_uses_hashed_edge_adjacency(monkeypatch):
    calls = 0
    real_eq = shape_core.Shape.__eq__

    def counting_eq(self, other):
        nonlocal calls
        calls += 1
        return real_eq(self, other)

    monkeypatch.setattr(shape_core.Shape, "__eq__", counting_eq)
    found = recognise_fillets(_filleted_plate())

    assert len(found) == 4
    assert 0 < calls <= 500


def _lone_d(radius: float, offset: float, z: float):
    beyond = 40 if offset >= 0 else -40
    cutter = Pos(offset + beyond, 0, 0) * Box(80, 80, 60, align=_CENTRE)
    return Pos(0, 0, z) * (Cylinder(radius, 40) - cutter)


def test_lone_flats_on_separate_coaxial_stock_are_not_opposed():
    part = _lone_d(20, 10, -30) + Cylinder(5, 60) + _lone_d(12, -8, 60)
    flats = recognise_flats(part)
    assert len(flats) == 2
    assert sorted(flat.across for flat in flats) == [20.0, 30.0]


def test_genuine_double_d_faces_remain_opposed():
    flats = recognise_flats(Cylinder(20, 40) & Box(25, 60, 60, align=_CENTRE))
    assert len(flats) == 2
    assert {flat.across for flat in flats} == {25.0}


def _pocket_row(n=4, pitch=30.0):
    part = Box(30, pitch * (n + 1), 20)
    for i in range(n):
        part -= Pos(0, (i - (n - 1) / 2) * pitch, 7) * Box(10, 12, 6)
    return part


def _pocket_grid(nx=2, ny=3, px=40.0, py=30.0):
    part = Box(px * (nx + 2), py * (ny + 1), 20)
    for i in range(nx):
        for j in range(ny):
            part -= Pos((i - (nx - 1) / 2) * px, (j - (ny - 1) / 2) * py, 7) * Box(8, 10, 6)
    return part


def test_linear_pocket_array_and_rectangular_grid_are_recognised():
    row = recognise_pocket_patterns(recognise_pockets(_pocket_row()))
    grid = recognise_pocket_patterns(recognise_pockets(_pocket_grid()))
    assert len(row) == 1 and isinstance(row[0], PocketArray) and row[0].pitch == 30.0
    assert len(grid) == 1 and isinstance(grid[0], PocketGrid)
    assert {grid[0].rows, grid[0].cols} == {2, 3}


def test_pocket_patterns_do_not_merge_different_planes_or_opening_faces():
    def pocket(cy, d_lo=0.0, sign=1):
        return Pocket("x", "y", 10.0, 12.0, 6.0, 0.0, cy - 6, cy + 6, d_lo, d_lo + 6, sign)

    staggered = [pocket(-30, 0), pocket(0, 5), pocket(30, 10)]
    opposed = [pocket(-30, 5, 1), pocket(0, 5, -1), pocket(30, 5, 1)]
    assert recognise_pocket_patterns(staggered) == []
    assert recognise_pocket_patterns(opposed) == []
    assert len(recognise_pocket_patterns([pocket(-30), pocket(0), pocket(30)])) == 1


def test_pocket_patterns_do_not_merge_edge_anchored_and_interior_members():
    base = Pocket("x", "y", 10.0, 12.0, 6.0, 0.0, -36.0, -24.0, 5.0, 11.0)
    mixed = (
        base,
        replace(base, lo=-6.0, hi=6.0, edge_anchored=True),
        replace(base, lo=24.0, hi=36.0),
    )
    assert recognise_pocket_patterns(mixed) == []


def _slot_row(n=4, pitch=30.0):
    part = Box(60, pitch * (n + 2), 20)
    for i in range(n):
        part -= Pos(0, (i - (n - 1) / 2) * pitch, 0) * Box(30, 8, 20)
    return part


def _slot_grid(nx=2, ny=3, px=44.0, py=34.0):
    part = Box(px * (nx + 2), py * (ny + 1), 20)
    for i in range(nx):
        for j in range(ny):
            part -= Pos((i - (nx - 1) / 2) * px, (j - (ny - 1) / 2) * py, 0) * Box(24, 8, 20)
    return part


def test_linear_slot_array_and_rectangular_grid_are_recognised():
    row = recognise_slot_patterns(recognise_slots(_slot_row()))
    grid = recognise_slot_patterns(recognise_slots(_slot_grid()))
    assert len(row) == 1 and isinstance(row[0], SlotArray) and row[0].pitch == 30.0
    assert len(grid) == 1 and isinstance(grid[0], SlotGrid)
    assert {grid[0].rows, grid[0].cols} == {2, 3}


def test_slot_patterns_do_not_merge_different_through_planes():
    def slot(cy, d_lo):
        return Slot("y", "x", 8.0, 30.0, cy, -15.0, 15.0, d_lo, d_lo + 20)

    assert recognise_slot_patterns([slot(-30, 0), slot(0, 5), slot(30, 10)]) == []
    assert len(recognise_slot_patterns([slot(-30, 0), slot(0, 0), slot(30, 0)])) == 1


def test_pairs_and_mixed_sizes_are_not_patterns():
    assert recognise_pocket_patterns(recognise_pockets(_pocket_row(n=2))) == []
    assert recognise_slot_patterns(recognise_slots(_slot_row(n=2))) == []

    pockets = [
        Pocket("x", "y", width, 12.0, 6.0, 0.0, cy - 6, cy + 6, 5.0, 11.0)
        for width, cy in [(10.0, -30), (14.0, 0), (10.0, 30)]
    ]
    assert recognise_pocket_patterns(pockets) == []


def test_a_chord_with_no_vertices_reaches_no_od():
    """``_both_chord_ends_reach_od`` is reachable only with vertices through the recogniser.

    Its no-vertices guard used to be implicit — the function tested one end for ``None`` and
    compared the other unguarded, which was correct only because both are assigned in the same
    loop iterations. Stating the guard made it explicit and made it uncoverable from geometry,
    so it is covered here directly, which is also the only place the answer is written down.
    """

    from quiddity.flats import _both_chord_ends_reach_od

    assert not _both_chord_ends_reach_od(
        [], (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), 10.0
    )


def test_a_trimmed_cylinder_does_not_crash_the_countersink_bore_search():
    """Issue #74. ``Face.radius`` is ``None`` for a ``Geom_RectangularTrimmedSurface``.

    ``nist_ftc_06`` carries 30 such faces among its 58 cylinders and raised ``TypeError`` on
    the bore-match subtraction. The angled cut below trims the boss the same way, and the cone
    has no bore beneath it so the search exhausts every cylinder rather than short-circuiting
    on an earlier match — which is what it takes to reach the ``None``.
    """

    from build123d import Cone, Rot

    from quiddity import recognise_countersinks

    part = Box(60, 40, 12) + Pos(20, 0, 16) * Cylinder(5, 20)
    part -= Pos(20, 0, 30) * Rot(0, 45, 0) * Box(40, 40, 30)
    part -= Pos(0, 0, 3) * Cone(6, 3, 6)

    assert any(f.radius is None for f in part.faces().filter_by(GeomType.CYLINDER))
    assert recognise_countersinks(part) == []
