# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""What ``recognise_polygonal_bosses`` and ``recognise_polygonal_stock`` refuse.

Epic 0001 finding 4. ``docs/capabilities.md`` promises a narrow class — an *attached regular
hexagonal Z-axis boss* with six outward side faces, one across-flats value, a support cap and a
top cap — and excludes other side counts, X/Y axes, whole-stock prisms, inward recesses,
incomplete rings and cross-solid assemblies.

Side count and axis are already covered by ``test_capability_claims``. What was not covered is
the evidence *within* a six-sided Z-axis candidate: whether the ring is complete, whether the
polygon is regular, and whether the caps are the flat, correctly-placed faces a boss needs. Those
gates are the difference between "six planar faces" and "a hexagonal boss", and each one below is
a shape that has the former without the latter.
"""

from __future__ import annotations

import math

from build123d import Box, Cylinder, Polygon, Pos, RegularPolygon, Rot, extrude

from b123d_recognisers import recognise_polygonal_bosses, recognise_polygonal_stock

_BASE = Box(100, 80, 10)


def _attached(prism):
    """A prism standing on the shared base plate, which is what makes a boss a boss."""

    return _BASE + Pos(0, 0, 5) * prism


def _irregular_hexagon(radius: float, height: float, *, stretch: float):
    """Six sides, six planar faces, unequal angular gaps — not a regular hexagon."""

    points = []
    for index in range(6):
        angle = 2 * math.pi * index / 6
        scale = stretch if index % 2 == 0 else 1.0
        points.append((radius * scale * math.cos(angle), radius * scale * math.sin(angle)))
    return extrude(Polygon(*points), height)


def test_a_regular_hexagonal_boss_on_a_plate_is_recognised():
    """Positive control: every exclusion below is this shape with one property removed."""

    (boss,) = recognise_polygonal_bosses(_attached(extrude(RegularPolygon(20, 6), 30)))

    assert boss.axis == "z"
    assert boss.side_count == 6


def test_an_irregular_hexagon_is_not_a_hexagonal_boss():
    """Six sides is not six *equal* sides.

    The recogniser reports one across-flats value, so an irregular hexagon would be described by
    a number that is true of only some of it.
    """

    assert recognise_polygonal_bosses(_attached(_irregular_hexagon(20, 30, stretch=1.35))) == []


def test_a_smaller_stud_on_top_leaves_the_hexagon_a_boss():
    """A narrower feature standing on the cap does not consume it, and must not hide the boss.

    Written after the opposite assertion failed. The hexagon's top survives as an annulus around
    the stud, which is still a planar cap at one Z — so recognition is correct here, and the
    interesting case is the one below, where the cap is genuinely gone.
    """

    prism = extrude(RegularPolygon(20, 6), 30) + Pos(0, 0, 30) * Cylinder(14, 8)

    (boss,) = recognise_polygonal_bosses(_attached(prism))
    assert boss.top == 35.0


def test_a_hexagon_swallowed_by_a_wider_crown_has_no_top_cap():
    """With the whole top face consumed there is no cap, and so no boss to report."""

    prism = extrude(RegularPolygon(20, 6), 30) + Pos(0, 0, 32) * Cylinder(25, 4)

    assert recognise_polygonal_bosses(_attached(prism)) == []


def test_a_hexagonal_boss_whose_top_is_not_flat_in_z_is_rejected():
    """A slanted crown is not a cap: its face spans a range of Z rather than sitting at one."""

    prism = extrude(RegularPolygon(20, 6), 30)
    wedge = Pos(0, 0, 32) * (Rot(25, 0, 0) * Box(60, 60, 20))

    assert recognise_polygonal_bosses(_attached(prism - wedge)) == []


def test_an_incomplete_ring_of_sides_is_not_a_boss():
    """Every side must adjoin exactly two others. A gap in the ring is an open shape.

    Slicing one flat off leaves five hexagon sides plus a cut face — still six planar walls, but
    no longer a closed regular ring, and the across-flats value would be a fiction.
    """

    prism = extrude(RegularPolygon(20, 6), 30) - Pos(24, 0, 15) * Box(20, 60, 60)

    assert recognise_polygonal_bosses(_attached(prism)) == []


def test_a_hexagonal_recess_is_not_a_hexagonal_boss():
    """The side faces must point outward. A pocket of the same shape is an inward recess."""

    plate = Box(100, 80, 30) - Pos(0, 0, 20) * extrude(RegularPolygon(20, 6), 20)

    assert recognise_polygonal_bosses(plate) == []


def test_whole_stock_requires_exactly_the_prism_and_nothing_else():
    """``recognise_polygonal_stock`` is fail-closed on face count, not tolerant of extras.

    A hexagonal bar with a cross hole is still hexagonal bar to a person, and deliberately is
    not stock to this recogniser — the promise is *exactly* six sides and two caps.
    """

    bar = extrude(RegularPolygon(20, 6), 30)

    assert recognise_polygonal_stock(bar)
    cross_hole = Pos(0, 0, 15) * (Rot(90, 0, 0) * Cylinder(5, 60))
    assert recognise_polygonal_stock(bar - cross_hole) == []


def test_a_boss_and_its_plate_in_separate_bodies_are_not_one_boss():
    """Cross-solid assembly is an excluded class: a boss must be attached to what supports it."""

    floating = _BASE + Pos(0, 0, 25) * extrude(RegularPolygon(20, 6), 30)

    assert recognise_polygonal_bosses(floating) == []
