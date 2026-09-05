# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""The shared length-tolerance form of ADR 0008.

These are the properties recognisers rely on when they replace an absolute millimetre gate with a
derived one — not merely that the arithmetic is `rel * n + floor`, but that the result is monotone,
continuous and floored, so a converted gate cannot become stricter than the constant it replaced.
"""

from __future__ import annotations

import math

import pytest
from build123d import Box, Cylinder

from quiddity._geometry import length_tol, part_scale
from quiddity._pattern_geometry import _PATTERN_ABS_TOL, _PATTERN_REL_TOL, _pattern_tol


def test_the_floor_is_the_tolerance_of_a_degenerate_nominal():
    assert length_tol(0.0, rel=0.02, floor=0.1) == 0.1


def test_a_converted_gate_is_never_stricter_than_the_constant_it_replaces():
    """The floor is the whole point: scaling must only ever loosen, never tighten."""

    for nominal in (0.0, 0.001, 1.0, 50.0, 5000.0):
        assert length_tol(nominal, rel=0.02, floor=0.5) >= 0.5


def test_the_tolerance_grows_with_the_thing_being_measured():
    assert length_tol(200.0, rel=0.02, floor=0.1) > length_tol(20.0, rel=0.02, floor=0.1)


def test_a_part_modelled_ten_times_larger_gets_ten_times_the_proportional_allowance():
    """The floor is unaffected by scale; only the proportional term follows the model."""

    small = length_tol(30.0, rel=0.02, floor=0.1)
    large = length_tol(300.0, rel=0.02, floor=0.1)

    assert large - 0.1 == pytest.approx(10 * (small - 0.1))


def test_the_floor_never_swallows_the_proportional_term():
    """ADR 0008 chooses `rel * n + floor` over `max(floor, rel * n)`.

    Both are continuous, so smoothness is not the distinction. The distinction is that a maximum
    *discards* one term below `floor / rel`: every feature under that size gets exactly the floor
    and its own size stops mattering. The additive form keeps both contributions everywhere, so
    the result is strictly increasing across the whole range rather than flat and then sloped.
    """

    crossover = 0.5 / 0.02
    below = [length_tol(n, rel=0.02, floor=0.5) for n in (0.1, 1.0, crossover / 2)]

    assert below == sorted(below) and below[0] != below[-1], "a maximum would be flat here"
    assert all(value > 0.5 for value in below)


def test_a_negative_nominal_is_rejected_rather_than_silently_tightening_the_gate():
    with pytest.raises(ValueError, match="non-negative"):
        length_tol(-1.0, rel=0.02, floor=0.1)


def test_malformed_geometry_fails_closed_rather_than_raising():
    """A NaN nominal must propagate, so the candidate is refused, not the traversal aborted."""

    tol = length_tol(math.nan, rel=0.02, floor=0.1)

    assert math.isnan(tol)
    assert not (tol >= 0.05), "a gate written `deviation <= tol` must refuse, not admit"


def test_the_pattern_tolerance_is_the_shared_form():
    """`_pattern_tol` was the idiom ADR 0008 generalised; it must stay the same function."""

    assert _pattern_tol(37.5) == length_tol(37.5, rel=_PATTERN_REL_TOL, floor=_PATTERN_ABS_TOL)


def test_part_scale_is_the_largest_envelope_extent():
    assert part_scale(Box(10, 40, 25).bounding_box()) == pytest.approx(40.0)


def test_part_scale_is_proportional_to_the_model_it_measures():
    small = part_scale(Cylinder(3, 12).bounding_box())
    large = part_scale((Cylinder(3, 12).scale(7)).bounding_box())

    assert large == pytest.approx(7 * small)
