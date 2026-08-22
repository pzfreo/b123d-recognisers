# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""The named rules that decide between families describing one physical region (ADR 0003).

Candidate discovery and reconciliation are separate stages. A recogniser proposes; the rules
here accept, combine or reject. They live outside every recogniser on purpose: one that declined
a face because another family had already claimed it would make the census depend on which
family ran first, which ADR 0003 forbids and ADR 0002 forbids again by ruling out sibling calls.

The rules are of two kinds, because ADR 0003 says a reconciler "accepts, combines or rejects":

- **precedence** -- the recess families are reconciled from their complete boundary claims, with
  a rectangular paired-wall record winning only where it describes the same four-wall void and
  a non-rectangular ring winning over paired-wall fragments assembled inside it; a chamfer that
  is an angled step's slant is dropped because the step says strictly more;
- **compatibility** -- a turned step whose band is a groove keeps its record, because both
  descriptions are needed, and only the *count* is corrected.

Not a constraint solver. ADR 0003 allows family-specific rules to migrate behind this protocol
one at a time, and these are the rules for which there is measured evidence.

**A rule finds a record's evidence by identity**, through a frozen `EvidenceIndex` on migrated
paths and the temporary `ClaimLedger` adapter elsewhere. Every rule here once paired its records
against the ledger's claims *by position*, which held only
while a recogniser wrote one claim per record in the order it returned them -- a coupling across
two files that nothing checked. `strict=True` catches a count that drifts and cannot catch a
permutation, and a permutation hands every record another record's faces while the counts stay
right. A mutation in the chamfer/angled-step work did exactly that and survived the whole golden
corpus.
"""

from __future__ import annotations

from collections import defaultdict

from b123d_recognisers._candidates import EvidenceIndex, FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._recess_records import Pocket, Slot
from b123d_recognisers.angled_steps import AngledStep
from b123d_recognisers.chamfers import Chamfer
from b123d_recognisers.grooves import Groove
from b123d_recognisers.passages import Passage
from b123d_recognisers.prismatic_pockets import PrismaticPocket
from b123d_recognisers.turned import TurnedStep


def passages_that_are_not_slots(
    passages: list[Passage], evidence: EvidenceIndex
) -> list[Passage]:
    """Drop four-sided Passage candidates already dimensioned as Slots.

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

    slot_walls = [
        evidence.defining_of(candidate)
        for candidate in evidence.candidate_set(FamilyId.LEGACY).candidates
        if isinstance(candidate.record, Slot)
    ]
    return [
        passage
        for passage in passages
        # A four-wall ring is the rectangular void a Slot measures more directly. A ring with
        # any other side count is not made a slot merely because one opposed pair happens to
        # sit inside it; that is the false candidate exposed on triangular,
        # hexagonal and interrupted passage sections.
        if passage.sides != 4
        or not any(walls <= evidence.defining_of(passage) for walls in slot_walls)
    ]


def reconcile_recesses(
    slots: list[Slot],
    pockets: list[Pocket],
    prismatic: list[PrismaticPocket],
    passages: list[Passage],
    evidence: EvidenceIndex,
) -> tuple[list[Slot], list[Pocket], list[PrismaticPocket], list[Passage]]:
    """Apply the recess-family precedence rules after every family has proposed.

    A shared face is only evidence.  The verdicts here require containment by a more complete
    description of the same boundary:

    - a verified through ring defeats paired-wall pocket fragments inside it;
    - a verified floored pocket defeats a slot built from the same walls;
    - a non-rectangular passage or prismatic-pocket ring defeats a slot assembled from a
      subset of its walls;
    - a four-wall passage still yields to the Slot that dimensions that rectangular void.

    Interrupted rings may be returned as several records with the same section. Their claims
    are pooled only within that exact ``(axis, section)`` identity before testing containment,
    matching the way slot reduction pools collinear wall arms into one record.
    """

    accepted_prismatic = prismatic_pockets_that_are_not_pockets(
        prismatic,
        pockets,
        evidence,
    )
    non_rectangular_pockets = [
        pocket for pocket in accepted_prismatic if pocket.sides != 4
    ]
    accepted_pockets = [
        pocket
        for pocket in pockets
        if not any(
            evidence.defining_of(pocket) <= evidence.defining_of(passage)
            for passage in passages
        )
        and not any(
            evidence.defining_of(pocket) <= evidence.defining_of(ring)
            for ring in non_rectangular_pockets
        )
    ]

    non_rectangular_rings: dict[tuple, set] = defaultdict(set)
    for passage in passages:
        if passage.sides != 4:
            non_rectangular_rings[(passage.axis, passage.section)].update(
                evidence.defining_of(passage)
            )

    accepted_slots = []
    for slot in slots:
        walls = evidence.defining_of(slot)
        # Obround slots recovered from their cylindrical caps deliberately have no planar-wall
        # claim. Missing evidence cannot prove containment: the empty set is mathematically a
        # subset of every ring, but semantically it is not an ownership verdict.
        if not walls:
            accepted_slots.append(slot)
            continue
        if any(walls <= evidence.defining_of(pocket) for pocket in accepted_pockets):
            continue
        if any(walls <= evidence.defining_of(pocket) for pocket in accepted_prismatic):
            continue
        if any(walls <= ring for ring in non_rectangular_rings.values()):
            continue
        accepted_slots.append(slot)

    accepted_passages = [
        passage
        for passage in passages
        if passage.sides != 4
        or not any(
            evidence.defining_of(slot) <= evidence.defining_of(passage)
            for slot in accepted_slots
        )
    ]
    return accepted_slots, accepted_pockets, accepted_prismatic, accepted_passages


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

    # Takes completed records, as the migrated recess rule now does. The full ladder is needed by
    # `build_recognition_result` as well, so owning discovery here would scan the shaft twice to
    # throw one result away; the later phase extraction removes this remaining ledger adapter.
    floors = [claim.defining for claim in ledger.claims if isinstance(claim.claimant, Groove)]
    return [
        step
        for step in steps
        if not any(floor <= ledger.defining_of(step) for floor in floors)
    ]


def chamfers_that_are_not_angled_steps(
    chamfers: list[Chamfer], ledger: ClaimLedger
) -> list[Chamfer]:
    """The chamfers that are not the slant of an angled blind step, dropped where they are.

    A blind step's slant is an oblique planar bevel bridging two perpendicular axis-aligned
    walls at a convex corner, which is a chamfer's entire signature. `recognise_chamfers`
    therefore proposes it, correctly on its own evidence, and `recognise_angled_steps` claims
    it as well. **Both families claim exactly one face -- the slant itself -- so a contested
    face is not two features overlapping but one face described twice**, and the step record
    wins: it says everything the chamfer says and adds `length`, the distance the slant runs
    before the triangular flat closes it. That flat is what the step found and the chamfer
    could not see.

    Precedence, like `passages_that_are_not_slots`, and for the same reason -- one description
    subsumes the other. Not the containment test that rule uses, though: there a slot's two
    walls sit *inside* a passage's whole ring, so the direction of the subset carries the
    verdict. Here the two claims are the same single face, so overlap and containment are the
    same question and the honest way to write it is that they name the same face at all.

    **This is what `_adjacency.has_triangular_companion` used to do, and did not generalise.**
    Both recognisers consulted it, one requiring the flat and one refusing it, so the split was
    kept by two call sites agreeing about a helper rather than by anyone deciding. The comment
    on it recorded the risk that made it fragile: two copies that drifted would not double-count
    but would make the feature *vanish*, claimed by neither. The discriminator is now private to
    `angled_steps`, which is the family it defines, and the ownership question is answered where
    ADR 0003 puts it -- from the claims, after discovery, by a named rule that a third family
    reading bevels could join without either recogniser learning about it.

    A consequence a caller sees: `recognise_chamfers` called on its own now reports a blind
    step's slant, as it did before `recognise_angled_steps` existed. `feature_census` and
    `build_recognition_result` both apply this rule, so the reconciled answer is unchanged.
    """

    slants = {
        node
        for claim in ledger.claims
        if isinstance(claim.claimant, AngledStep)
        for node in claim.defining
    }
    return [chamfer for chamfer in chamfers if ledger.defining_of(chamfer).isdisjoint(slants)]


def prismatic_pockets_that_are_not_pockets(
    prismatic: list[PrismaticPocket],
    pockets: list[Pocket],
    evidence: EvidenceIndex,
) -> list[PrismaticPocket]:
    """The prismatic pockets no rectangular `Pocket` already describes, dropped where they are.

    Two families reach a rectangular recess and neither is wrong. `recognise_pockets` pairs two
    facing walls; `recognise_prismatic_pockets` walks the closed ring those walls sit in. On the
    geometry alone both are true, and which record a caller wants is not a question either
    recogniser can answer about itself.

    **For a four-sided ring, the rectangular record wins**, and the direction is not arbitrary.
    `Pocket` measures
    `width` and `length` on named axes -- the numbers a drawing calls out -- where the prismatic
    record carries a four-corner section that says the same thing less directly. For a shape the
    older family can express, it expresses it better. For every shape it cannot, nothing here
    fires and the prismatic record is the only one there is.

    Containment, like `passages_that_are_not_slots`, and for the same reason: a `Pocket` claims
    the two walls it was paired from, and those walls are members of the ring, so the subset runs
    one way and never the other. Mere overlap would be too weak -- two recesses sharing a wall
    are two recesses, which is what ADR 0003 means by overlapping claims being evidence rather
    than a verdict.
    """

    walls = tuple(
        defining
        for pocket in pockets
        if (defining := evidence.defining_of(pocket))
    )
    return [
        pocket
        for pocket in prismatic
        if pocket.sides != 4
        or not any(paired <= evidence.defining_of(pocket) for paired in walls)
    ]
