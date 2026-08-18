# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""Which faces a slot was built from, so a second family can ask instead of guessing.

`recognise_slots` reduces every face to a normal, an axis, a bounding box and a wall flag
before it decides anything, and that reduction dropped the face itself — so nothing downstream
could say which faces a slot was made of. `recognise_passages` needed exactly that and had to
compare record coordinates instead.

The pipeline is what makes this non-trivial: a slot's record is rebuilt three times after the
walls that established it are gone. `_merge` keeps one candidate of a co-located group,
`_collapse_collinear` spans several arms into one channel, `_extend_obround_ends` and the
body-key pass both `replace` fields. A claim attached to any intermediate would never reach the
caller, so each path has a fixture here that reaches it — verified by measuring how many faces
the surviving slot claims, which is 2, 4 and 4 respectively.

The claim is checked against the geometry it asserts, not against a captured number: every
claimed face is proved to be one of that slot's two walls.
"""

from __future__ import annotations

import pytest
from build123d import Box, Cylinder, Pos

import b123d_recognisers as r
from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._claims import ClaimLedger

_AXES = {"x": 0, "y": 1, "z": 2}


def claimed(part):
    """Recognise with a ledger, and prove doing so changed nothing about the result."""

    ledger = ClaimLedger(FaceGraph(part))
    with_ledger = r.recognise_slots(part, ledger=ledger)
    assert with_ledger == r.recognise_slots(part), "claiming changed what was recognised"
    return ledger, with_ledger


def obround(length, width, height):
    end = Cylinder(width / 2, height)
    return Box(length, width, height) + Pos(-length / 2, 0, 0) * end + Pos(length / 2, 0, 0) * end


def test_every_claimed_face_is_one_of_that_slots_walls():
    """The claim is its evidence, not an arbitrary pair of faces.

    A slot's walls are planar, normal to the width axis, and sit half a width either side of
    ``w_center``. Checking that is what distinguishes a real claim from one that happens to
    have the right *number* of faces.
    """

    part = Box(120, 60, 20) - Pos(-30, 0, 0) * Box(40, 10, 20) - Pos(30, 0, 0) * Box(30, 16, 20)
    ledger, slots = claimed(part)
    assert len(slots) == 2
    assert len(ledger) == 2

    for claim in ledger.claims:
        slot = claim.claimant
        axis = _AXES[slot.width_axis]
        assert len(claim.defining) == 2
        offsets = set()
        for node in claim.defining:
            assert ledger.graph.is_planar(node)
            normal = ledger.graph.normal(node)
            assert abs(normal[axis]) == pytest.approx(1.0, abs=1e-6)
            lo, hi = ledger.graph.bounds(node)[axis]
            assert lo == pytest.approx(hi, abs=1e-6), "a wall has no thickness along its normal"
            offsets.add(round(lo - slot.w_center, 6))
        assert sorted(offsets) == pytest.approx([-slot.width / 2, slot.width / 2], abs=1e-6)


def test_a_candidate_merged_away_gives_up_its_walls():
    """`_merge` keeps one candidate of a co-located pair; both pairs are the slot's walls.

    A square through void is bounded by two wall pairs that both survive the elongation gate,
    so the recogniser sees the same feature twice and keeps one. Four faces rather than two is
    the observable difference between absorbing the dropped candidate's walls and discarding
    them — a rectangular void cannot show it, because its second pair is rejected for being
    wider than it is long before it ever reaches the merge.
    """

    ledger, slots = claimed(Box(120, 60, 20) - Box(20, 20, 20))
    assert len(slots) == 1
    (claim,) = ledger.claims
    assert len(claim.defining) == 4

    ledger_rect, _ = claimed(Box(120, 60, 20) - Box(21, 20, 20))
    assert [len(c.defining) for c in ledger_rect.claims] == [2], "the contrast case"


def test_arms_collapsed_into_one_channel_pool_their_walls():
    """`_collapse_collinear` spans several arms into one record, which the arms' walls bound.

    A crossing pair of channels removes the middle of each other's walls, so each channel is
    found as two collinear arms and rebuilt as one slot. The rebuilt record is a new object;
    without the transfer it would reach the caller claiming nothing.
    """

    part = Box(120, 120, 20) - Box(60, 14, 20) - Box(14, 60, 20)
    ledger, slots = claimed(part)
    assert len(slots) == 2
    assert sorted(len(claim.defining) for claim in ledger.claims) == [4, 4]


def test_a_slot_recovered_from_its_end_caps_claims_nothing():
    """Documented absence rather than a claim over faces that are not walls.

    A stubby obround has no pairable flat walls, so it is recovered from its two semicircular
    caps. Those are cylindrical, and a caller reconciling a ring of planar faces against slots
    cannot be looking at this one — so the slot is simply absent from the ledger, and the
    ledger's refusal of an empty claim is what keeps that explicit.
    """

    ledger, slots = claimed(Box(100, 60, 20) - obround(3, 12, 20))
    assert len(slots) == 1
    assert len(ledger) == 0


def test_a_compound_does_not_pool_claims_across_its_solids():
    """The map is keyed by record value and cleared between solids, so this cannot leak.

    Two solids far apart produce slots whose records differ, but the guarantee has to hold
    without relying on that: each claim is proved to name only faces of its own solid.
    """

    part = (Box(80, 60, 20) - Box(30, 10, 20)) + Pos(200, 0, 0) * (
        Box(80, 60, 20) - Box(30, 10, 20)
    )
    ledger, slots = claimed(part)
    assert len(slots) == 2
    assert len(ledger) == 2

    for claim in ledger.claims:
        spread = [ledger.graph.bounds(node)[0] for node in claim.defining]
        near = all(lo < 100 for lo, _ in spread)
        far = all(lo > 100 for lo, _ in spread)
        assert near or far, "a claim named faces of both solids"


def test_the_ledger_is_written_and_never_read():
    """Slot recognition is identical with a ledger, an empty ledger, and none at all.

    A recogniser that consulted claims would make the census depend on which family ran first;
    this is the property that keeps it from being able to.
    """

    part = Box(120, 60, 20) - Box(30, 10, 20)
    graph = FaceGraph(part)
    prefilled = ClaimLedger(graph)
    prefilled.add_defining("something else entirely", graph.nodes[:4])

    assert r.recognise_slots(part) == r.recognise_slots(part, ledger=ClaimLedger(FaceGraph(part)))
    assert r.recognise_slots(part) == r.recognise_slots(part, ledger=prefilled)
