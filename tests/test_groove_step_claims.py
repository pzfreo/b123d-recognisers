# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""One band, two true records, and a metric that counts it once (#95).

A groove is an external band whose OD is a local minimum. The turned-step ladder describes the
same shaft, and that band is one of its rungs — so `recognise_grooves` and
`recognise_turned_steps` both report it, both correctly. It was counted twice.

The fix is not to drop either record, and these tests pin that: the ladder keeps its rung,
because `TurnedProfile` reads an interior end as a real end face and a ladder with a gap in it
describes a shaft with two faces where the groove is. Only `feature_census`, which counts
distinct machined features rather than describing them, should treat the band as one.

**The rule is not wired into the census yet, and these tests say so.** Writing the claims
uncovered a defect upstream of the count: at 0.05x the pinned `turned_steps_and_grooves`
fixture, `recognise_turned_steps` reports every rung at the shaft OD and describes a plain
shaft, so the reconciliation finds nothing and the census stops being scale-free. Wiring it
before that is fixed would trade one wrong count for a scale-dependent one.
"""

from __future__ import annotations

from build123d import Cylinder, Pos

import b123d_recognisers as r
from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._reconcile import steps_that_are_not_grooves


def _grooved_shaft():
    """A two-diameter shaft with an annular groove cut into the larger band."""

    shaft = Cylinder(20, 60) + Pos(0, 0, 40) * Cylinder(14, 20)
    return shaft - Pos(0, 0, 10) * (Cylinder(20, 6) - Cylinder(16, 6))


def _plain_shaft():
    """The same shaft with no groove: the contrast case for the count."""

    return Cylinder(20, 60) + Pos(0, 0, 40) * Cylinder(14, 20)


def _claimed(part):
    """Both families against one ledger, proved to return what they return without it."""

    ledger = ClaimLedger(FaceGraph(part))
    cyls = r.analyse_cylinders(part)
    grooves = r.recognise_grooves(part, cyls=cyls, ledger=ledger)
    steps = r.recognise_turned_steps(part, cyls=cyls, ledger=ledger)

    assert grooves == r.recognise_grooves(part), "claiming changed what was recognised"
    assert steps == r.recognise_turned_steps(part), "claiming changed what was recognised"
    return ledger, grooves, steps


def test_a_groove_claims_its_floor_band_and_not_the_shaft_either_side():
    """The walls make the band a local minimum; they do not bound the groove.

    Claiming them would have every groove contest the two steps it sits between, which is the
    conflict this reconciliation exists to resolve rather than to manufacture.
    """

    part = _grooved_shaft()
    ledger, grooves, _ = _claimed(part)
    (groove,) = grooves

    claim = next(c for c in ledger.claims if c.claimant is groove)
    (node,) = claim.defining
    lo, hi = ledger.graph.bounds(node)[2]
    assert hi - lo == groove.width, "the claimed face spans exactly the groove's width"
    radius = max(abs(edge) for edge in ledger.graph.bounds(node)[0])
    assert 2 * radius == groove.diameter, "and it is the floor band, not a wall"


def test_a_turned_step_claims_the_bands_that_set_its_diameter():
    """The shoulder planes come from the neighbouring steps' faces, so they are not claimed."""

    part = _grooved_shaft()
    ledger, _, steps = _claimed(part)

    for step in steps:
        claim = next(c for c in ledger.claims if c.claimant is step)
        assert claim.defining, "every rung rests on a band"
        for node in claim.defining:
            radius = max(abs(edge) for edge in ledger.graph.bounds(node)[0])
            assert 2 * round(radius, 3) == step.diameter


def test_the_rule_finds_the_rung_the_groove_is():
    """What the reconciliation would remove, proved on the pair, before it is wired anywhere.

    Not yet used by `feature_census`, which still counts this band twice (#95): at small scale
    `recognise_turned_steps` reports the groove's rung at the shaft's OD, so the rule finds
    nothing and the count stops being scale-free. The defect is upstream and is fixed first.
    """

    ledger, grooves, steps = _claimed(_grooved_shaft())
    (groove,) = grooves

    kept = steps_that_are_not_grooves(steps, ledger)
    assert len(kept) == len(steps) - 1
    assert [step for step in steps if step not in kept][0].diameter == groove.diameter

    plain_ledger, plain_grooves, plain_steps = _claimed(_plain_shaft())
    assert plain_grooves == []
    assert steps_that_are_not_grooves(plain_steps, plain_ledger) == plain_steps


def test_the_ladder_keeps_the_rung_the_groove_is():
    """Both records survive in the result: a profile with a hole in it is a different shaft."""

    part = _grooved_shaft()
    result = r.build_recognition_result(part)

    (groove,) = result.grooves
    rungs = [step for step in result.turned_steps if step.diameter == groove.diameter]
    assert rungs, "the ladder still has a rung at the groove's diameter"

    ladder = sorted(result.turned_steps, key=lambda step: step.lo)
    for lower, upper in zip(ladder, ladder[1:], strict=False):
        assert lower.hi == upper.lo, "and it is still contiguous"


def test_the_rule_refuses_a_step_list_that_is_not_the_one_that_was_claimed():
    """Paired by position, so a filtered list is a caller error rather than a wrong answer."""

    part = _grooved_shaft()
    ledger, _, steps = _claimed(part)

    assert len(steps_that_are_not_grooves(steps, ledger)) == len(steps) - 1

    try:
        steps_that_are_not_grooves(steps[:-1], ledger)
    except ValueError:
        return
    raise AssertionError("a short list must not be reconciled against another list's claims")
