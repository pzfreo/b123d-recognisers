# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""The shared axis conventions in ``_geometry``.

Epic 0001 finding 4: this module was the least covered file in the package while holding the one
piece of geometry with a documented cross-platform hazard. ``migration/PARITY.md`` records the
dominant-axis tie-break as the single deliberate normalization of the Draftwright extraction —
OCCT perturbs an exact diagonal by a final bit in opposite directions on Windows and Unix, and an
unqualified ``max()`` routed equivalent geometry into different feature inventories.

The tests below are deliberately negative and boundary cases. The happy path is already covered by
every golden fixture; what was not covered is what happens at a tie, at a degenerate vector, and
on the rejection paths that exist to fail closed.
"""

from __future__ import annotations

import math

import pytest

from b123d_recognisers._geometry import (
    _axis_direction_is_aligned,
    _axis_letter_of,
    _canonical_axis_direction,
    _canonical_axis_span,
    _normalised_axis_direction,
    plane_axes,
)


class TestDominantAxisTieBreak:
    """The PARITY.md normalization: a tie resolves to Z, then Y — never by float accident."""

    def test_an_exact_diagonal_resolves_to_z(self):
        assert _axis_letter_of((1.0, 1.0, 1.0)) == "z"

    def test_an_xy_diagonal_resolves_to_y(self):
        assert _axis_letter_of((1.0, 1.0, 0.0)) == "y"

    @pytest.mark.parametrize("noise", [0.0, 1e-13, -1e-13, 2e-13])
    def test_noise_below_the_tie_band_cannot_change_the_answer(self, noise):
        """This is the whole point: a final-bit perturbation must not reroute the feature.

        A bare ``max()`` returns whichever component happens to be larger, so the same model
        recognised on two platforms could land in two different inventories.
        """

        assert _axis_letter_of((1.0 + noise, 1.0, 1.0 - noise)) == "z"

    def test_the_tie_band_is_a_band_and_not_a_blanket(self):
        """The preference applies within ``_DOMINANT_TIE_TOL`` of the peak, not to any near-tie.

        Pinned because it is easy to read the Z-then-Y preference as unconditional. Here the
        spread from the peak to Z is 1e-12 — at the edge, and outside it once the subtraction
        rounds — so Y is the correct answer, not Z. A real difference this size is still a real
        difference; only genuine final-bit noise is normalised away.
        """

        assert _axis_letter_of((1.0 + 5e-13, 1.0, 1.0 - 5e-13)) == "y"
        assert _axis_letter_of((1.0, 1.0 - 1e-9, 1.0 - 1e-9)) == "x"

    def test_a_difference_above_the_band_is_respected(self):
        assert _axis_letter_of((1.0, 0.5, 0.5)) == "x"
        assert _axis_letter_of((0.5, 1.0, 0.5)) == "y"

    def test_sign_does_not_affect_the_letter(self):
        assert _axis_letter_of((-3.0, 1.0, 1.0)) == "x"

    def test_a_vector_that_is_not_three_components_is_rejected(self):
        with pytest.raises(ValueError, match="3-vector"):
            _axis_letter_of((1.0, 0.0))


class TestAxisDirectionValidation:
    """Every rejection path exists so malformed evidence fails closed rather than routing."""

    def test_an_omitted_direction_defaults_to_the_axis_itself(self):
        assert _normalised_axis_direction("y") == (0.0, 1.0, 0.0)

    def test_an_unknown_axis_letter_is_rejected(self):
        with pytest.raises(ValueError, match="must be 'x', 'y', or 'z'"):
            _normalised_axis_direction("w")

    def test_a_multi_character_axis_is_rejected(self):
        with pytest.raises(ValueError, match="must be 'x', 'y', or 'z'"):
            _normalised_axis_direction("xy")

    def test_non_numeric_components_are_rejected(self):
        with pytest.raises(ValueError, match="must be a 3-vector"):
            _normalised_axis_direction("x", ("a", "b", "c"))

    def test_the_wrong_number_of_components_is_rejected(self):
        with pytest.raises(ValueError, match="must be a 3-vector"):
            _normalised_axis_direction("x", (1.0, 0.0))

    @pytest.mark.parametrize("bad", [math.inf, -math.inf, math.nan])
    def test_non_finite_components_are_rejected(self, bad):
        with pytest.raises(ValueError, match="finite"):
            _normalised_axis_direction("x", (bad, 0.0, 0.0))

    def test_a_zero_vector_has_no_direction(self):
        with pytest.raises(ValueError, match="non-zero"):
            _normalised_axis_direction("x", (0.0, 0.0, 0.0))

    def test_a_direction_whose_dominant_component_is_not_the_named_axis_is_rejected(self):
        """A record claiming axis 'x' while pointing along Y is incoherent, not merely odd."""

        with pytest.raises(ValueError, match="dominant component must match"):
            _normalised_axis_direction("x", (0.0, 1.0, 0.0))


class TestCanonicalForms:
    def test_a_direction_is_normalised_and_its_dominant_component_made_positive(self):
        assert _normalised_axis_direction("z", (0.0, 0.0, -2.0)) == (0.0, 0.0, 1.0)

    def test_an_already_unit_direction_is_not_renormalised_into_float_noise(self):
        assert _canonical_axis_direction("x", (1.0, 0.0, 0.0)) == (1.0, 0.0, 0.0)

    def test_a_span_measured_along_a_flipped_direction_is_re_expressed_forwards(self):
        """The canonical direction points +axis, so a span read against -axis must flip with it.

        Without this the same physical stock would report ``(lo, hi)`` reversed and negated
        depending only on which way the source frame happened to point.
        """

        assert _canonical_axis_span("z", (0.0, 0.0, -1.0), (2.0, 5.0)) == (-5.0, -2.0)

    def test_a_span_on_a_forward_direction_is_unchanged(self):
        assert _canonical_axis_span("z", (0.0, 0.0, 1.0), (2.0, 5.0)) == (2.0, 5.0)


class TestAxisAlignment:
    def test_a_principal_direction_is_aligned(self):
        assert _axis_direction_is_aligned("x", (1.0, 0.0, 0.0))

    def test_a_slanted_direction_is_not(self):
        assert not _axis_direction_is_aligned("z", (0.0, 0.3, 0.95))

    def test_a_direction_just_inside_the_band_is_aligned(self):
        assert _axis_direction_is_aligned("z", (0.0, 5e-4, 1.0))

    def test_a_direction_just_outside_the_band_is_not(self):
        assert not _axis_direction_is_aligned("z", (0.0, 5e-3, 1.0))


def test_plane_axes_accepts_a_letter_or_a_vector_and_agrees_with_itself():
    assert plane_axes("z") == plane_axes((0.0, 0.0, 1.0))
    assert plane_axes("z") == ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
