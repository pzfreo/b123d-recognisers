# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""Recognition of the golden corpus rebuilt at other scales.

A recogniser that classifies by absolute millimetres answers differently for the same feature
modelled in metres, inches or on a micro-part. ADR 0008 replaces those gates with proportional
ones family by family; this test pins the families already converted so a later absolute
constant cannot quietly reintroduce the fault.

The excluded kinds below are not passing by luck — they are the families whose gates are still
absolute, tracked as epic 0001 finding 2c. Each one moves out of ``NOT_YET_SCALE_FREE`` when its
recogniser is converted, and this file is the checklist for that work.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
GOLDEN_ROOT = ROOT / "tests" / "golden"
sys.path.insert(0, str(ROOT))

from b123d_recognisers import feature_census  # noqa: E402
from tests.golden._common import load_fixture  # noqa: E402

CASES = sorted(GOLDEN_ROOT.glob("*/fixture.py"))

#: Both extremes plus one interior factor. The interior one matters: ``plates`` gains a spurious
#: record in ``chamfers_fillets_and_flats`` at 5x and 10x but not at 1x or 100x, because that
#: fixture has a face whose area is exactly the gate's 40% threshold and rounding decides it.
#: A test that only visited the extremes would call that family scale-free when it is not.
FACTORS = (0.05, 5.0, 100.0)

#: Feature kinds whose recognisers still gate on absolute millimetres, per ADR 0008's
#: part-relative list. ``plate`` and ``pocket`` lose records on a part modelled 20x small;
#: ``chamfer`` and ``fillet`` gate on absolute leg and radius sizes. Converting those is finding
#: 2c — delete the entry, do not add to it.
NOT_YET_SCALE_FREE = frozenset({"plate", "pocket", "chamfer", "fillet"})


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


def test_the_exclusion_list_is_a_debt_record_not_a_permanent_carve_out():
    """Guard the guard: an excluded kind must still be a kind the census can report.

    A typo here would silently excuse a family that is in fact tested, making the exclusion
    list look smaller than the remaining work.
    """

    reported = set(feature_census(load_fixture(CASES[0]).build_fixture()))

    assert reported.issuperset(NOT_YET_SCALE_FREE)
