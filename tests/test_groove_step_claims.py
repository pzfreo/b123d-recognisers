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

The rule waited on a defect upstream of the count — while `recognise_turned_steps`
reported the groove's rung at the shaft's OD on a part modelled small, wiring it would have
traded one wrong count for a scale-dependent one. That is fixed, so the count is pinned here
at three scales.
"""

from __future__ import annotations

import pytest
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
    """What the reconciliation removes, proved on the pair rather than through the count."""

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


def test_a_ledger_built_from_another_shaft_is_refused_rather_than_left_empty():
    """The provenance check, on both families, with a twin that is equal by value.

    A graph built from a different part resolves nothing, so the ledger comes back empty — and
    empty reads downstream as "these families claim nothing" rather than as "you paired the
    wrong graph", which is the reading a reconciler turns into a duplicate feature. The twin is
    the same shaft by value, so this proves provenance rather than geometry.
    """

    part = _grooved_shaft()
    twin = _grooved_shaft()
    assert r.recognise_grooves(twin) == r.recognise_grooves(part), "the twin is this shaft"

    for recognise in (r.recognise_grooves, r.recognise_turned_steps):
        foreign = ClaimLedger(FaceGraph(twin))
        try:
            recognise(part, ledger=foreign)
        except ValueError as refusal:
            assert "built from a different part" in str(refusal)
        else:
            raise AssertionError(f"{recognise.__name__} accepted another part's graph")


@pytest.mark.parametrize("factor", (1.0, 0.05, 100.0))
def test_the_census_counts_one_band_once_though_two_families_describe_it(factor):
    """The count, at three scales, with the contrast that shows the rule is not just subtracting.

    A groove adds two shoulders to the shaft and therefore two rungs to the ladder, one of which
    is the groove itself. Counting *features*, that is one more than the plain shaft has, not
    two — and it is the same answer however large the shaft is modelled, which it was not while
    the rung reported its neighbour's diameter.
    """

    grooved, plain = _grooved_shaft(), _plain_shaft()
    if factor != 1.0:
        grooved, plain = grooved.scale(factor), plain.scale(factor)

    grooved_census = r.feature_census(grooved)
    plain_census = r.feature_census(plain)

    assert grooved_census["groove"] == 1
    assert plain_census["groove"] == 0
    assert grooved_census["step"] == plain_census["step"] + 1
