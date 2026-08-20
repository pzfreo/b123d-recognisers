# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""`feature_census` and `build_recognition_result` must not answer differently about one part.

The two build similar run-local state and apply related reconciliation through separate code
paths. That is a silent-divergence point by construction: nothing forces a rule added to one to
be added to the other, and the symptom is not a crash but a *number* — the same solid reported
as having a feature by one entry point and not by the other.

It is not hypothetical. Measured across all 73 corpus parts, the two disagreed about `plate` on
one of them: `build_recognition_result` suppresses a plate when the shaft's steps form a turned
profile, and the census counted one anyway. A real turned screw, one part in seventy-three, and
nothing in the suite was looking.

This file is the guard, and it is deliberately a *property* over the whole corpus rather than a
pinned number: a new family added to one inventory and forgotten in the other fails here on
whichever part first carries it.

**Two differences are by design and are named rather than asserted away.** They are the reason
this cannot simply compare every key:

- `step` — `steps_that_are_not_grooves` is a *compatibility* rule under ADR 0003. Both records
  survive into the result, and only the count is corrected, so the census reporting fewer steps
  than the result carries is the rule working.
- pattern families — the census counts hole patterns but has no key for slot or pocket patterns.
  That is a scope decision about what a "distinct machined feature" is, not a divergence, but it
  is worth knowing it is deliberate.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from build123d import import_step

import b123d_recognisers as r
from b123d_recognisers.census import feature_census
from tests.golden._common import load_fixture

GOLDEN = Path(__file__).parent / "golden"
CORPUS = Path(__file__).parent / "corpus"

#: Census key -> result field, for every family both inventories report. `step` is absent
#: deliberately; see the module docstring.
SHARED = {
    "hole": "holes",
    "hole_pattern": "hole_patterns",
    "boss": "bosses",
    "slot": "slots",
    "groove": "grooves",
    "channel": "channels",
    "pocket": "pockets",
    "prismatic_pocket": "prismatic_pockets",
    "passage": "passages",
    "chamfer": "chamfers",
    "angled_step": "angled_steps",
    "fillet": "fillets",
    "countersink": "countersinks",
    "plate": "plates",
}


def _disagreements(part):
    counts = feature_census(part)
    result = r.build_recognition_result(part)
    return {
        key: (counts[key], len(getattr(result, field)))
        for key, field in SHARED.items()
        if counts[key] != len(getattr(result, field))
    }


@pytest.mark.parametrize(
    "fixture", sorted(p.parent.name for p in GOLDEN.glob("*/fixture.py"))
)
def test_the_two_inventories_agree_on_every_golden(fixture):
    """Every synthetic part, one family at a time, so a failure names the family."""

    part = load_fixture(GOLDEN / fixture / "fixture.py").build_fixture()
    assert _disagreements(part) == {}


@pytest.mark.skipif(
    not (CORPUS / "mfcadpp" / "MANIFEST.json").is_file(),
    reason="the vendored corpora are excluded from the sdist",
)
def test_the_two_inventories_agree_on_imported_parts():
    """Where the one real disagreement was, and the only part in 73 that had it.

    Goldens are built to exercise one family at a time; the divergence that motivated this file
    needed a real turned screw whose steps form a ladder. Imported geometry is where an
    inventory that has quietly drifted shows up.
    """

    models = sorted(CORPUS.glob("*/*.st*p"))
    assert models, "the vendored corpora must be present for this to mean anything"

    disagreed = {}
    for path in models:
        try:
            part = import_step(str(path))
        except Exception:  # noqa: BLE001 - an unreadable file is the corpus's problem, not this test's
            continue
        found = _disagreements(part)
        if found:
            disagreed[path.name] = found
    assert disagreed == {}


def test_the_shared_map_still_covers_every_family_the_census_counts():
    """So a family added to the census cannot quietly escape this check.

    A new key that nobody adds here would be compared against nothing, which is the failure mode
    this file exists to prevent, one level up.
    """

    counted = set(feature_census(load_fixture(
        GOLDEN / "simple_through_hole" / "fixture.py"
    ).build_fixture()))
    # `step` and `flat` are the documented exceptions: a compatibility rule and a substrate.
    assert counted - set(SHARED) == {"step", "flat"}
