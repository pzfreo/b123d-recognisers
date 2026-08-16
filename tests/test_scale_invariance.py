# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""Recognition of the golden corpus rebuilt at other scales.

A recogniser that classifies by absolute millimetres answers differently for the same feature
modelled in metres, inches or on a micro-part. ADR 0008 replaces those gates with proportional
ones family by family; this test pins the families already converted so a later absolute
constant cannot quietly reintroduce the fault.

Every fixture now recognises identically from 0.05x to 100x, across every family. The exclusion
list that tracked the conversion is empty; the test below keeps it that way.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
GOLDEN_ROOT = ROOT / "tests" / "golden"
sys.path.insert(0, str(ROOT))

from b123d_recognisers import feature_census  # noqa: E402
from b123d_recognisers._geometry import clears_threshold  # noqa: E402
from tests.golden._common import load_fixture  # noqa: E402

CASES = sorted(GOLDEN_ROOT.glob("*/fixture.py"))

#: Both extremes plus one interior factor. The interior one earns its place: ``plates`` used to
#: gain a spurious record in ``chamfers_fillets_and_flats`` at 5x and 10x but not at 1x or 100x,
#: which a test visiting only the extremes would have missed entirely.
FACTORS = (0.05, 5.0, 100.0)

#: Empty, and meant to stay that way. It held the families whose gates were still absolute
#: while ADR 0008 was applied one at a time; every one has now been converted. Re-adding a kind
#: means a recogniser has regained a scale-dependent gate, which is the regression this file
#: exists to catch — so it is a deliberate, reviewable act rather than a quiet exemption.
NOT_YET_SCALE_FREE: frozenset[str] = frozenset()


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


def test_no_family_is_exempt_from_scale_invariance():
    """The conversion is finished, so nothing should be excluded from the check above.

    Kept rather than deleted with the last entry: an exemption added later would otherwise
    shrink the test's coverage silently, which is exactly how the original absolute gates
    survived so long.
    """

    assert frozenset() == NOT_YET_SCALE_FREE
