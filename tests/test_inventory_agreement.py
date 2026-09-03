# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""`feature_census` and `build_recognition_result` must not answer differently about one part.

The two used to build similar run-local state and apply related reconciliation through separate
code paths. That was a silent-divergence point by construction: nothing forced a rule added to
one to be added to the other, and the symptom was not a crash but a *number* — the same solid
reported as having a feature by one entry point and not by the other.

It was not hypothetical. Measured across all 73 corpus parts, the two disagreed about `plate` on
one of them: `build_recognition_result` suppresses a plate when the shaft's steps form a turned
profile, and the census counted one anyway. A real turned screw, one part in seventy-three, and
nothing in the suite was looking.

They now share one inventory — `_take_inventory` — so a disagreement of that kind can no longer
be written. What remains for this file to guard is the *mapping*: the census names a kind, the
inventory returns a field, and nothing but this checks that the census counts the field it means
to. A key wired to the wrong family, or a family added to one side and not the other, still
produces a wrong number silently. So the property is kept, over the whole corpus, rather than
retired as impossible.

**Two differences are by design and are named rather than asserted away.** They are the reason
this cannot simply compare every key:

- `step` — `steps_that_are_not_grooves` is a *compatibility* rule under ADR 0003. Both records
  survive into the inventory, and only the census's count is corrected, so the census reporting
  fewer steps than the result carries is the rule working.
- pattern families — the census counts hole patterns but has no key for slot or pocket patterns.
  That is a scope decision about what a "distinct machined feature" is, not a divergence, but it
  is worth knowing it is deliberate.
"""

from __future__ import annotations

import dataclasses
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
    "oriented_slot": "oriented_slots",
    "rectangular_blind_slot": "rectangular_blind_slots",
    "round_bottom_blind_slot": "round_bottom_blind_slots",
    "groove": "grooves",
    "channel": "channels",
    "pocket": "pockets",
    "prismatic_pocket": "prismatic_pockets",
    "passage": "section_passages",
    "chamfer": "chamfers",
    "angled_step": "angled_steps",
    "paired_ramp_step": "paired_ramp_steps",
    "through_step": "through_steps",
    "circular_blind_step": "circular_blind_steps",
    "blend": "blends",
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


@pytest.mark.parametrize("fixture", sorted(p.parent.name for p in GOLDEN.glob("*/fixture.py")))
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

    # No skipping. These are checked-in inputs, and swallowing an import failure would quietly
    # remove a part from the evidence -- including the one diagnostic screw this file exists
    # for. A file that stops importing is a finding, not a reason to compare fewer parts.
    unreadable, disagreed = {}, {}
    for path in models:
        try:
            part = import_step(str(path))
        except Exception as failure:  # noqa: BLE001 - reported, never skipped
            unreadable[path.name] = repr(failure)
            continue
        found = _disagreements(part)
        if found:
            disagreed[path.name] = found
    assert unreadable == {}, "a checked-in corpus file stopped importing"
    assert disagreed == {}


#: `RecognitionResult` fields the census deliberately does not count, and why. Written out
#: rather than derived so that adding an aggregate family forces a decision here: is it a
#: machined feature the census should count, or one of these?
RESULT_ONLY = {
    # Substrates and projections: evidence other recognisers consume, not features in their
    # own right. The census docstring excludes these by design.
    "cylinders": "the shared cylinder scan",
    "flats": "substrate for turned features",
    "step_levels": "substrate, and level derivation belongs to the model layer",
    "risers": "substrate for the step ladder",
    "rotational": "a classification, not a record list",
    # A compatibility rule under ADR 0003: both records survive, only the count is corrected.
    "turned_steps": "counted as `step` after `steps_that_are_not_grooves`",
    # Pattern families: the census counts hole patterns and not these. A scope decision about
    # what a distinct machined feature is, and one worth revisiting rather than inheriting.
    "slot_patterns": "census counts hole patterns only",
    "oriented_slot_patterns": "census counts hole patterns only",
    "pocket_patterns": "census counts hole patterns only",
    "passages": "accepted-only compatibility projection; section_passages is counted",
    # Families with no census key at all. Each is a gap rather than a decision, and naming
    # them here is what makes that visible.
    "double_d_bores": "no census key",
    "pads": "no census key",
    "polygonal_bosses": "no census key",
    "polygonal_stock": "no census key",
    "repeating_radial_profiles": "no census key",
}


def test_the_shared_map_still_covers_every_family_the_census_counts():
    """A census key added without updating `SHARED` would be compared against nothing.

    That is the failure mode this file exists to prevent, one level up.
    """

    counted = set(
        feature_census(load_fixture(GOLDEN / "simple_through_hole" / "fixture.py").build_fixture())
    )
    # `step` and `flat` are the documented exceptions: a compatibility rule and a substrate.
    assert counted - set(SHARED) == {"step", "flat"}


def test_the_shared_map_still_covers_every_family_the_aggregate_reports():
    """And the same in the other direction, which the first test cannot see.

    A new `RecognitionResult` family omitted from the census would leave the two inventories
    covering different sets while every comparison here still passed -- exactly the drift this
    file claims to catch. The exclusions are the useful part: they make the current asymmetry
    deliberate, and force a decision each time an aggregate family is added.
    """

    fields = {
        field.name
        for field in dataclasses.fields(
            r.build_recognition_result(
                load_fixture(GOLDEN / "simple_through_hole" / "fixture.py").build_fixture()
            )
        )
    }
    assert fields - set(SHARED.values()) == set(RESULT_ONLY)
