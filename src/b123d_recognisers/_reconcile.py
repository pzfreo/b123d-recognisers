# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""The named rules that decide between families describing one physical region (ADR 0003).

Candidate discovery and reconciliation are separate stages. A recogniser proposes; the rules
here accept, combine or reject. They live outside every recogniser on purpose: one that declined
a face because another family had already claimed it would make the census depend on which
family ran first, which ADR 0003 forbids and ADR 0002 forbids again by ruling out sibling calls.

One rule so far. It is deliberately not a constraint solver -- ADR 0003 allows family-specific
rules to migrate behind this protocol one at a time, and this is the first to have had to.
"""

from __future__ import annotations

from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._recess_records import Slot
from b123d_recognisers._typing import Part
from b123d_recognisers.passages import Passage, recognise_passages


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
