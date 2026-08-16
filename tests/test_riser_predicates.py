# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""The riser classification and ramp test, exercised directly.

Extracting these from ``recognise_risers`` made their rejection paths reachable without building
a solid that exhibits them — the same effect the polygonal decomposition had. Both are decisions
about a single face, so they are stated here as the arithmetic they are.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from b123d_recognisers.levels import _ramp_positions, _riser_orientation

EXT = {"x": 100.0, "y": 80.0, "z": 40.0}


def _normal(x, y, z):
    return SimpleNamespace(X=x, Y=y, Z=z)


def _bbox(*, xlo, xhi, ylo, yhi, zlo, zhi):
    return SimpleNamespace(
        min=SimpleNamespace(X=xlo, Y=ylo, Z=zlo),
        max=SimpleNamespace(X=xhi, Y=yhi, Z=zhi),
    )


class TestRiserOrientation:
    def test_a_square_wall_facing_x_is_a_vertical_riser(self):
        assert _riser_orientation(_normal(1.0, 0.0, 0.0)) == (True, "x")

    def test_a_square_wall_facing_y_is_a_vertical_riser(self):
        assert _riser_orientation(_normal(0.0, -1.0, 0.0)) == (True, "y")

    def test_a_slanted_wall_keeps_its_axis_but_is_not_vertical(self):
        assert _riser_orientation(_normal(0.7, 0.0, 0.7)) == (False, "x")

    def test_a_horizontal_face_is_not_a_riser_at_all(self):
        """A floor or a cap has no in-plane axis, so there is nothing for it to rise along."""

        assert _riser_orientation(_normal(0.0, 0.0, 1.0)) is None

    def test_a_face_with_a_foot_on_both_in_plane_axes_is_a_corner_treatment(self):
        """Not a step: a corner bevel faces two ways at once and locates no single shoulder."""

        assert _riser_orientation(_normal(0.7, 0.7, 0.0)) is None


class TestRampPositions:
    def test_a_full_span_ramp_contributes_only_its_axis_stations(self):
        fb = _bbox(xlo=10.0, xhi=30.0, ylo=0.0, yhi=80.0, zlo=0.0, zhi=20.0)

        positions, other = _ramp_positions(fb, "x", "y", EXT, full_span=True, flo=0.0, fhi=80.0)

        assert positions == pytest.approx((10.0, 30.0))
        assert other == ()

    def test_a_bounded_ramp_also_contributes_its_width(self):
        """Its extrusion endpoints are what define the ramp's extent across the part."""

        fb = _bbox(xlo=10.0, xhi=30.0, ylo=20.0, yhi=60.0, zlo=0.0, zhi=20.0)

        positions, other = _ramp_positions(fb, "x", "y", EXT, full_span=False, flo=20.0, fhi=60.0)

        assert positions == pytest.approx((10.0, 30.0))
        assert other == pytest.approx((20.0, 60.0))

    def test_a_bounded_face_too_narrow_across_the_part_is_an_edge_break(self):
        fb = _bbox(xlo=10.0, xhi=30.0, ylo=40.0, yhi=44.0, zlo=0.0, zhi=20.0)

        assert _ramp_positions(fb, "x", "y", EXT, full_span=False, flo=40.0, fhi=44.0) is None

    def test_a_bounded_face_too_short_along_its_own_axis_is_an_edge_break(self):
        fb = _bbox(xlo=10.0, xhi=14.0, ylo=20.0, yhi=60.0, zlo=0.0, zhi=20.0)

        assert _ramp_positions(fb, "x", "y", EXT, full_span=False, flo=20.0, fhi=60.0) is None

    def test_a_bounded_face_too_shallow_in_z_is_an_edge_break(self):
        """A chamfer is bounded exactly like a ramp — height is what separates them."""

        fb = _bbox(xlo=10.0, xhi=30.0, ylo=20.0, yhi=60.0, zlo=0.0, zhi=2.0)

        assert _ramp_positions(fb, "x", "y", EXT, full_span=False, flo=20.0, fhi=60.0) is None
