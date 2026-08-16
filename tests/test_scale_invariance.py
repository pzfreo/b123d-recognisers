# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""Recognition of the golden corpus rebuilt at other scales.

A recogniser that classifies by absolute millimetres answers differently for the same feature
modelled in metres, inches or on a micro-part. ADR 0008 replaces those gates with proportional
ones family by family; this test pins the families already converted so a later absolute
constant cannot quietly reintroduce the fault.

Coverage is partial and deliberately so. Families gated by a *minimum-evidence threshold* —
"is this big enough to be a feature?" — are excluded, because 0.2.4 makes those thresholds
absolute again after 0.2.3 scaled them and erased small features on large parts (issue #72).

That exclusion is not a defect being deferred. A 1 mm chamfer shrunk to 0.05 mm genuinely is a
deburr, and whether it is worth reporting is consumer policy under ADR 0001. What must not happen
is the *surrounding part* deciding it, which is what 0.2.3 did and what
``tests/test_large_part_small_features.py`` now pins.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
GOLDEN_ROOT = ROOT / "tests" / "golden"
sys.path.insert(0, str(ROOT))

from build123d import Box, Pos  # noqa: E402

from b123d_recognisers import feature_census, recognise_risers, step_level_zs  # noqa: E402
from b123d_recognisers._geometry import clears_threshold  # noqa: E402
from tests.golden._common import load_fixture  # noqa: E402

CASES = sorted(GOLDEN_ROOT.glob("*/fixture.py"))

#: Both extremes plus one interior factor. The interior one earns its place: ``plates`` used to
#: gain a spurious record in ``chamfers_fillets_and_flats`` at 5x and 10x but not at 1x or 100x,
#: which a test visiting only the extremes would have missed entirely.
FACTORS = (0.05, 5.0, 100.0)

#: Kinds whose recogniser applies an absolute *minimum-evidence threshold*, so shrinking a part
#: far enough legitimately takes the feature below it. These are excluded by design, not pending
#: conversion — see ADR 0008 on why a threshold must not scale with the part.
NOT_YET_SCALE_FREE = frozenset({"chamfer", "fillet", "flat", "plate", "pocket", "channel"})


def _scale_free_census(part) -> dict[str, int]:
    return {
        kind: count
        for kind, count in feature_census(part).items()
        if count and kind not in NOT_YET_SCALE_FREE
    }


@pytest.mark.parametrize("factor", FACTORS)
@pytest.mark.parametrize("fixture_path", CASES, ids=lambda path: path.parent.name)
def test_converted_families_recognise_the_same_features_at_any_scale(fixture_path, factor):
    """The same solid, modelled *factor* times larger, is the same set of features."""

    fixture = load_fixture(fixture_path)
    expected = _scale_free_census(fixture.build_fixture())

    actual = _scale_free_census(fixture.build_fixture().scale(factor))

    assert actual == expected, f"{fixture_path.parent.name} at {factor}x"


def test_a_magnitude_exactly_on_its_threshold_is_decided_the_same_way_at_every_scale():
    """An area gate compared at exact equality is settled by rounding, not by the part.

    ``chamfers_fillets_and_flats`` has a face whose area is exactly ``min_area_frac`` of the
    cross-section. ``area - threshold`` came out ``-1.7e-13`` at 1x, exactly ``0.0`` at 5x and
    10x, and ``-9.3e-10`` at 100x, so ``recognise_plates`` returned a record at two scales and
    not the others — the same geometry classified two ways.
    """

    assert not clears_threshold(480.0, 480.0), "an exact tie must not admit a feature"
    assert not clears_threshold(479.9999999999999, 480.00000000000006)
    assert clears_threshold(480.1, 480.0), "a real margin must still clear it"

    fixture = load_fixture(GOLDEN_ROOT / "chamfers_fillets_and_flats" / "fixture.py")
    counts = {
        factor: feature_census(fixture.build_fixture().scale(factor)).get("plate", 0)
        for factor in (0.2, 5.0, 10.0, 100.0)
    }

    assert set(counts.values()) == {0}, counts


def test_an_explicit_tolerance_keeps_its_literal_millimetre_meaning():
    """``tol=None`` resolves from the part; a float passed in must not be re-scaled.

    This is the compatibility half of ADR 0008 and the reason the change is safe for a caller
    who has already calibrated against their own geometry. ``RiserEvidence.tol`` reports what
    the scan actually used, so it can be read back directly rather than inferred from counts.
    """

    part = Box(60, 60, 10) + Pos(0, 0, 7.5) * Box(30, 60, 5)

    explicit = {riser.tol for riser in recognise_risers(part, tol=0.25)}

    assert explicit == {0.25}
    assert {riser.tol for riser in recognise_risers(part.scale(10), tol=0.25)} == {0.25}

    # The default no longer follows the part, which is the 0.2.4 correction: a riser's existence
    # must not depend on how large the plate around it is.
    assert {riser.tol for riser in recognise_risers(part)} == {
        riser.tol for riser in recognise_risers(part.scale(10))
    }


def test_an_explicit_end_margin_is_also_honoured_literally():
    """The step-ladder inset takes the same ``None``-resolves/float-is-literal contract."""

    part = Box(40, 40, 20) + Pos(0, 0, 12.5) * Box(20, 40, 5)

    assert step_level_zs(part, tol=0.1) == step_level_zs(part, tol=0.1)
    assert step_level_zs(part) == step_level_zs(part)


