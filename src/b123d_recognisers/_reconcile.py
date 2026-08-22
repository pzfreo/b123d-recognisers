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

**A rule finds a record's evidence by identity**, through `ClaimLedger.defining_of`. Every
rule here once paired its records against the ledger's claims *by position*, which held only
while a recogniser wrote one claim per record in the order it returned them -- a coupling across
two files that nothing checked. `strict=True` catches a count that drifts and cannot catch a
permutation, and a permutation hands every record another record's faces while the counts stay
right. A mutation in the chamfer/angled-step work did exactly that and survived the whole golden
corpus.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import Literal, TypeAlias

from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._recess_records import Pocket, Slot
from b123d_recognisers.angled_steps import AngledStep
from b123d_recognisers.chamfers import Chamfer
from b123d_recognisers.grooves import Groove
from b123d_recognisers.passages import Passage
from b123d_recognisers.prismatic_pockets import PrismaticPocket
from b123d_recognisers.turned import TurnedStep

RecessCandidate: TypeAlias = Slot | Pocket | PrismaticPocket | Passage
RecessOutcome = Literal["accepted", "rejected"]
RecessReason = Literal[
    "accepted",
    "accepted_without_claim",
    "contained_by_passage",
    "contained_by_non_rectangular_prismatic_pocket",
    "rectangular_passage_superseded_by_slot",
    "rectangular_ring_superseded_by_pocket",
    "superseded_by_non_rectangular_passage",
    "superseded_by_pocket",
    "superseded_by_prismatic_pocket",
]


@dataclass(frozen=True, eq=False, slots=True)
class RecessDisposition:
    """One discovery candidate's explicit reconciliation outcome and reason."""

    candidate: RecessCandidate
    outcome: RecessOutcome
    reason: RecessReason


@dataclass(frozen=True, slots=True)
class ReconciledRecesses:
    """Accepted recess inventory plus a complete, identity-preserving decision trace."""

    slots: tuple[Slot, ...]
    pockets: tuple[Pocket, ...]
    prismatic_pockets: tuple[PrismaticPocket, ...]
    passages: tuple[Passage, ...]
    dispositions: tuple[RecessDisposition, ...]


def reconcile_recesses(
    slots: list[Slot],
    pockets: list[Pocket],
    prismatic: list[PrismaticPocket],
    passages: list[Passage],
    ledger: ClaimLedger,
) -> ReconciledRecesses:
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

    dispositions: dict[int, RecessDisposition] = {}

    def decide(candidate: RecessCandidate, outcome: RecessOutcome, reason: RecessReason) -> None:
        """Record exactly one verdict without relying on value equality between records."""

        key = id(candidate)
        if key in dispositions:
            raise AssertionError("a recess candidate received more than one disposition")
        dispositions[key] = RecessDisposition(candidate, outcome, reason)

    accepted_prismatic = []
    pocket_walls = _pocket_wall_claims(pockets, ledger)
    for ring in prismatic:
        rejected = _rectangular_ring_is_superseded(ring, pocket_walls, ledger)
        ring_walls = ledger.defining_of(ring)
        decide(
            ring,
            "rejected" if rejected else "accepted",
            "rectangular_ring_superseded_by_pocket"
            if rejected
            else "accepted"
            if ring_walls
            else "accepted_without_claim",
        )
        if not rejected:
            accepted_prismatic.append(ring)
    non_rectangular_pockets = [pocket for pocket in accepted_prismatic if pocket.sides != 4]
    accepted_pockets = []
    for pocket in pockets:
        defining_walls = ledger.defining_of(pocket)
        inside_passage = bool(defining_walls) and any(
            defining_walls <= ledger.defining_of(passage) for passage in passages
        )
        inside_ring = bool(defining_walls) and any(
            defining_walls <= ledger.defining_of(ring) for ring in non_rectangular_pockets
        )
        reason: RecessReason = (
            "accepted_without_claim"
            if not defining_walls
            else "contained_by_passage"
            if inside_passage
            else "contained_by_non_rectangular_prismatic_pocket"
            if inside_ring
            else "accepted"
        )
        rejected = inside_passage or inside_ring
        decide(pocket, "rejected" if rejected else "accepted", reason)
        if not rejected:
            accepted_pockets.append(pocket)

    non_rectangular_rings: dict[tuple, set] = defaultdict(set)
    for passage in passages:
        if passage.sides != 4:
            non_rectangular_rings[(passage.axis, passage.section)].update(
                ledger.defining_of(passage)
            )

    accepted_slots = []
    for slot in slots:
        walls = ledger.defining_of(slot)
        # Obround slots recovered from their cylindrical caps deliberately have no planar-wall
        # claim. Missing evidence cannot prove containment: the empty set is mathematically a
        # subset of every ring, but semantically it is not an ownership verdict.
        if not walls:
            accepted_slots.append(slot)
            decide(slot, "accepted", "accepted_without_claim")
            continue
        if any(walls <= ledger.defining_of(pocket) for pocket in accepted_pockets):
            decide(slot, "rejected", "superseded_by_pocket")
            continue
        if any(walls <= ledger.defining_of(pocket) for pocket in accepted_prismatic):
            decide(slot, "rejected", "superseded_by_prismatic_pocket")
            continue
        if any(walls <= ring for ring in non_rectangular_rings.values()):
            decide(slot, "rejected", "superseded_by_non_rectangular_passage")
            continue
        accepted_slots.append(slot)
        decide(slot, "accepted", "accepted")

    accepted_passages = []
    for passage in passages:
        passage_walls = ledger.defining_of(passage)
        superseded = passage.sides == 4 and any(
            (slot_walls := ledger.defining_of(slot)) and slot_walls <= passage_walls
            for slot in accepted_slots
        )
        decide(
            passage,
            "rejected" if superseded else "accepted",
            "rectangular_passage_superseded_by_slot"
            if superseded
            else "accepted"
            if passage_walls
            else "accepted_without_claim",
        )
        if not superseded:
            accepted_passages.append(passage)

    discovered = (*slots, *pockets, *prismatic, *passages)
    if len(dispositions) != len(discovered) or set(dispositions) != {id(c) for c in discovered}:
        raise AssertionError(
            "every discovered recess candidate must receive exactly one disposition"
        )

    return ReconciledRecesses(
        tuple(accepted_slots),
        tuple(accepted_pockets),
        tuple(accepted_prismatic),
        tuple(accepted_passages),
        tuple(dispositions[id(candidate)] for candidate in discovered),
    )


def steps_that_are_not_grooves(steps: list[TurnedStep], ledger: ClaimLedger) -> list[TurnedStep]:
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

    floors = [claim.defining for claim in ledger.claims if isinstance(claim.claimant, Groove)]
    return [
        step for step in steps if not any(floor <= ledger.defining_of(step) for floor in floors)
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

    Precedence, like the recess rules above, and for the same reason -- one description subsumes
    the other. Not their containment test, though: there a slot's two
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


def _pocket_wall_claims(
    pockets: Sequence[Pocket], ledger: ClaimLedger
) -> list[AbstractSet[object]]:
    """Return non-empty evidence only for Pocket candidates supplied to this phase."""

    return [walls for pocket in pockets if (walls := ledger.defining_of(pocket))]


def _rectangular_ring_is_superseded(
    ring: PrismaticPocket,
    pocket_walls: Sequence[AbstractSet[object]],
    ledger: ClaimLedger,
) -> bool:
    """Whether a dimensioned rectangular pocket subsumes this less-specific ring record."""

    ring_walls = ledger.defining_of(ring)
    return ring.sides == 4 and any(walls <= ring_walls for walls in pocket_walls)
