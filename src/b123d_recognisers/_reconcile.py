# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""The named rules that decide between families describing one physical region (ADR 0003).

Candidate discovery and reconciliation are separate stages. A recogniser proposes; the rules
here accept, combine or reject. They live outside every recogniser on purpose: one that declined
a face because another family had already claimed it would make the census depend on which
family ran first, which ADR 0003 forbids and ADR 0002 forbids again by ruling out sibling calls.

Two rules so far, and they are deliberately different in kind, because ADR 0003 says a
reconciler "accepts, combines or rejects":

- **precedence** -- a passage that is a slot is dropped, because the slot says strictly more;
- **compatibility** -- a turned step whose band is a groove keeps its record, because both
  descriptions are needed, and only the *count* is corrected.

Not a constraint solver. ADR 0003 allows family-specific rules to migrate behind this protocol
one at a time, and these are the two that have had to.
"""

from __future__ import annotations

from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._recess_records import Slot
from b123d_recognisers._typing import Part
from b123d_recognisers.grooves import Groove
from b123d_recognisers.passages import Passage, recognise_passages
from b123d_recognisers.turned import TurnedStep


def passages_that_are_not_slots(part: Part, ledger: ClaimLedger) -> list[Passage]:
    """Recognise passages against a ledger the slots have already been written into, and drop
    the ones that are those slots.

    A through slot *is* a closed uncapped ring, so `recognise_passages` reports it too. Both
    families record the faces they were built from, so "are these the same void" is asked of
    those faces: **a passage whose ring contains both walls a slot was established by is that
    slot, seen from inside.** The slot record wins, because it dimensions the void -- width,
    length and the extent on the third axis -- where the passage would only count its sides.

    Containment, and directional, rather than overlap. A slot claims its two opposed walls; the
    ring is every wall, so the slot's claim sits inside the passage's and never the reverse.
    Mere overlap would be too weak to be a verdict, which is what ADR 0003 means by overlapping
    claims being evidence and not one: two records sharing a face may both be real, as a
    pattern and its members are.

    The heuristic this replaced compared a ring's averaged centre with a slot record's centre in
    X and Y within 1e-6. It ignored the run axis and Z, so an X-running passage and an unrelated
    Z slot at the same XY were the same feature to it; the two centres were also derived by
    different procedures, one averaging wall-face centres and the other reading slot extents.
    """

    passages = recognise_passages(part, ledger=ledger)
    slot_walls = [claim.defining for claim in ledger.claims if isinstance(claim.claimant, Slot)]
    # Paired by position rather than by looking each passage up: `recognise_passages` writes one
    # claim per record it returns, in the order it returns them, and `strict=True` is what makes
    # that an assertion instead of an assumption. Keying on the record would be wrong for the
    # reason the ledger itself is not keyed that way -- two equal-valued records can be two
    # features.
    rings = [claim.defining for claim in ledger.claims if isinstance(claim.claimant, Passage)]
    return [
        passage
        for passage, ring in zip(passages, rings, strict=True)
        if not any(walls <= ring for walls in slot_walls)
    ]


def steps_that_are_not_grooves(
    steps: list[TurnedStep], ledger: ClaimLedger
) -> list[TurnedStep]:
    """The turned steps that are a distinct machined feature, for counting purposes only.

    A groove *is* a rung of the step ladder: an external band whose OD is a local minimum is
    both "the band between these two shoulders" and "the annular channel cut into the shaft".
    Measured on the pinned `turned_steps_and_grooves` golden, the O24 band from 15.5 to 20.5 is
    reported by both families, and `feature_census` counted it once under each -- one machined
    feature, two features in the metric.

    **Both records survive**, unlike the passage a slot already describes. That is not
    inconsistency, it is the difference ADR 0003 draws between rejecting and combining:

    - The two are not competing descriptions of one void, one of which says more. They are a
      *feature* and a *profile*, and a consumer dimensioning the shaft needs both -- the groove
      to call out a width that excludes the lead-in chamfers, the ladder to place every
      shoulder.
    - Deleting the rung would not simplify the ladder, it would falsify it.
      `TurnedProfile.from_steps` takes contiguity as a caller precondition, and `shoulders`
      treats an interior `hi` with no following `lo` as "a real end face, not a shared
      shoulder". A ladder with the groove removed therefore describes a shaft with two end
      faces where the groove is -- a different shaft.

    So `build_recognition_result` carries both, and this belongs to `feature_census` alone --
    the one place that claims to count *distinct machined features* rather than to describe
    them. That the two deliberately disagree is the point, and is why this is a named function
    rather than a subtraction written inline at the call site.

    It waited on a defect upstream of the count. While it was unwired, `recognise_turned_steps`
    reported the groove's rung at the shaft's OD on a part modelled small, so there was no
    groove rung to reconcile and the count stopped being scale-free -- one wrong count being
    better than a scale-dependent one. That is fixed, and `test_scale_invariance` now runs the
    census over the turned-step golden at a twentieth and a hundred times size. Not over the
    vendored corpus, which cannot check it: all 50 NIST and MFCAD++ parts are milled prismatic
    and report no turned steps at all.
    """

    # Takes the records where `passages_that_are_not_slots` takes the part and runs the
    # recogniser itself. Not an oversight: that one owns the call so the pairing below cannot
    # be wrong, but the full ladder is needed by `build_recognition_result` as well, and owning
    # the call here would mean scanning the shaft twice to throw one of the results away.
    floors = [claim.defining for claim in ledger.claims if isinstance(claim.claimant, Groove)]
    # Paired by position, as above: *steps* must be what `recognise_turned_steps` returned
    # against this ledger, which writes one claim per step in return order. `strict=True` says
    # so loudly if a caller ever passes a filtered list.
    rungs = [claim.defining for claim in ledger.claims if isinstance(claim.claimant, TurnedStep)]
    return [
        step
        for step, band in zip(steps, rungs, strict=True)
        if not any(floor <= band for floor in floors)
    ]
