# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""The ring predicates behind polygonal boss recognition, tested directly.

In finding 4 I reported these branches as reachable only by constructing deliberately malformed
B-Rep, and left them uncovered on that basis. Decomposing ``_recognise_one`` in finding 6 made
that judgement obsolete: ``_regular_ring_order`` and ``_ring_profile`` are pure functions of
normals and centres, so the cases can be stated as arithmetic instead of modelled as solids.

That is the argument for the decomposition beyond line count — a predicate buried in a 231-line
function can only be reached through everything in front of it.
"""

from __future__ import annotations

import math

import pytest
from build123d import Vector

from b123d_recognisers.polygonal_bosses import _regular_ring_order, _ring_profile

ANGLE_TOL = math.radians(2)
TOL = 0.2


def _hexagon_normals(*, headings_deg=None):
    """Outward unit normals for a hexagon, optionally with the headings overridden."""

    headings = headings_deg if headings_deg is not None else [60 * i for i in range(6)]
    return {
        index: (math.cos(math.radians(deg)), math.sin(math.radians(deg)), 0.0)
        for index, deg in enumerate(headings)
    }


def _centres(normals, order, *, across_flats, centre=(0.0, 0.0)):
    """Face centres for a regular hexagon, in the same order ``_ring_profile`` expects."""

    support = across_flats / 2
    return [
        Vector(centre[0] + normals[i][0] * support, centre[1] + normals[i][1] * support, 0.0)
        for i in order
    ]


class TestRegularRingOrder:
    def test_evenly_spaced_opposed_normals_are_a_ring(self):
        order = _regular_ring_order(tuple(range(6)), _hexagon_normals(), ANGLE_TOL)

        assert order is not None
        assert sorted(order) == list(range(6))

    def test_the_order_follows_heading_not_input_order(self):
        normals = _hexagon_normals()
        shuffled = (3, 0, 5, 1, 4, 2)

        assert _regular_ring_order(shuffled, normals, ANGLE_TOL) == _regular_ring_order(
            tuple(range(6)), normals, ANGLE_TOL
        )

    def test_unevenly_spaced_sides_are_not_a_regular_polygon(self):
        skewed = _hexagon_normals(headings_deg=[0, 60, 120, 200, 240, 300])

        assert _regular_ring_order(tuple(range(6)), skewed, ANGLE_TOL) is None

    def test_sides_that_are_evenly_spaced_but_not_opposed_are_rejected(self):
        """Even spacing is not sufficient on its own — the second proof has to bite.

        These six headings are 60 degrees apart in sorted order, so the gap test passes, but
        the pair three apart is not antiparallel, so this is not a closed convex ring.
        """

        spiral = _hexagon_normals(headings_deg=[0, 60, 120, 180, 240, 305])

        assert _regular_ring_order(tuple(range(6)), spiral, ANGLE_TOL) is None

    def test_a_small_deviation_inside_the_angle_tolerance_is_still_a_ring(self):
        nudged = _hexagon_normals(headings_deg=[0, 60.5, 120, 180, 240, 300])

        assert _regular_ring_order(tuple(range(6)), nudged, math.radians(3)) is not None


class TestRingProfile:
    def test_a_centred_hexagon_reports_its_axis_and_across_flats(self):
        normals = _hexagon_normals()
        order = _regular_ring_order(tuple(range(6)), normals, ANGLE_TOL)

        centres = _centres(normals, order, across_flats=34.0)

        cx, cy, across = _ring_profile(order, normals, centres, TOL)

        assert (cx, cy) == pytest.approx((0.0, 0.0), abs=1e-9)
        assert across == pytest.approx(34.0)

    def test_an_offset_hexagon_reports_where_it_actually_is(self):
        normals = _hexagon_normals()
        order = _regular_ring_order(tuple(range(6)), normals, ANGLE_TOL)
        centres = _centres(normals, order, across_flats=20.0, centre=(7.5, -3.25))

        cx, cy, across = _ring_profile(order, normals, centres, TOL)

        assert (cx, cy) == pytest.approx((7.5, -3.25), abs=1e-9)
        assert across == pytest.approx(20.0)

    def test_inward_facing_walls_are_a_recess_rather_than_a_boss(self):
        """Negative support means the material is outside the ring, not within it."""

        normals = _hexagon_normals()
        order = _regular_ring_order(tuple(range(6)), normals, ANGLE_TOL)
        inward = [Vector(-p.X, -p.Y, 0.0) for p in _centres(normals, order, across_flats=34.0)]

        assert _ring_profile(order, normals, inward, TOL) is None

    def test_opposed_pairs_at_different_widths_are_not_one_prism(self):
        """A hexagon stretched on one axis has no single across-flats to report."""

        normals = _hexagon_normals()
        order = _regular_ring_order(tuple(range(6)), normals, ANGLE_TOL)
        centres = _centres(normals, order, across_flats=34.0)
        centres[0] = Vector(centres[0].X * 1.5, centres[0].Y * 1.5, 0.0)

        assert _ring_profile(order, normals, centres, TOL) is None

    def test_the_axis_is_a_least_squares_fit_not_one_opposed_pair(self):
        """One perturbed face must move the reported centre by much less than its own error.

        Six midplanes over-determine the axis. Solving from a single pair would hand that face's
        full error straight to the answer; fitting across all three keeps it proportionate.
        """

        normals = _hexagon_normals()
        order = _regular_ring_order(tuple(range(6)), normals, ANGLE_TOL)
        centres = _centres(normals, order, across_flats=34.0)
        centres[0] = Vector(centres[0].X + 0.15, centres[0].Y, 0.0)

        cx, cy, _across = _ring_profile(order, normals, centres, TOL)

        assert abs(cx) < 0.08
        assert abs(cy) < 0.08
