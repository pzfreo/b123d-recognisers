# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Which faces established which candidate: run-local, append-only, never read during discovery.

Two recognisers can describe the same physical region, and until now the package could only ask
*where* their records were, not *what they were built from*. `recognise_passages` suppressed a
passage whose XY centre matched a slot's to within 1e-6 — comparing two quantities derived by
different procedures, ignoring the passage's own axis, and making the census depend on the order
its families run in. The question it needed was "do these two claim the same faces?", and nothing
here could answer it.

**The ledger is not the graph.** :class:`b123d_recognisers._adjacency.FaceGraph` holds geometric
fact: a face's bounds, its normal, which faces it meets. Those are true of the solid whoever is
looking. A claim is an *interpretation* — this recogniser believes these faces make a passage —
and a competing recogniser may interpret the same faces differently. Keeping interpretations out
of the graph is what lets the graph stay immutable and shared while each run, or a rerun of one
family, gets a fresh ledger.

**Write-only during discovery.** Recognisers append; nothing reads back until every family has
run. This is the property that keeps discovery independent, and it is why claims do not violate
ADR 0003's separation of discovery from reconciliation: a recogniser that declined a face because
another family had claimed it would make output order-dependent, and that stays forbidden.

**A claim is a role, not a fact of ownership.** A feature's faces do not all relate to it the same
way: a pocket is defined by its floor and walls, while a fillet is defined by the blend face and
merely *consults* the two faces it bridges. Treating every face a recogniser touched as consumed
would manufacture conflicts between features that legitimately share context. Only the
`defining` role exists today, and it is named rather than implied so that adding `boundary` or
`consulted` later is a new method rather than a reinterpretation of this one.

**A claim is an object, not an index into a table.** `add_defining` hands back the claim
itself, so it carries its own claimant and its own defining faces and there is no id to look up
in the wrong ledger. Claims compare by identity, which is what keeps two equal-valued candidates
apart: records compare by value, so a table keyed on the record would have merged them into one
entry covering both their faces, and a reconciler asked which to keep would have found one claim
naming both sets.

**Overlap is not exclusion.** Two claims sharing a defining face is evidence for a reconciler to
weigh, not a verdict. Which of them survives — or whether both do, as a pattern and its members
both legitimately do — is the reconciler's policy under ADR 0003, and is not decided here.
"""

from __future__ import annotations

from collections.abc import Iterable

from b123d_recognisers._adjacency import FaceGraph, FaceNode


class Claim:
    """What one recogniser believes established one candidate.

    Compared by identity, deliberately. Two candidates whose records are equal are still two
    candidates, and a reconciler has to be able to tell them apart.
    """

    __slots__ = ("claimant", "defining")

    def __init__(self, claimant: object, defining: frozenset[FaceNode]) -> None:
        self.claimant = claimant
        self.defining = defining

    def __repr__(self) -> str:
        return f"Claim({self.claimant!r}, defining={len(self.defining)} faces)"


class ClaimLedger:
    """Append-only claims against the nodes of one :class:`FaceGraph`.

    Bound to a graph, and the binding is enforced rather than assumed: a node the graph did not
    issue is refused, so a ledger paired with the wrong graph cannot report overlaps between the
    faces of different solids.
    """

    def __init__(self, graph: FaceGraph) -> None:
        self._graph = graph
        self._claims: list[Claim] = []
        self._by_node: dict[FaceNode, list[Claim]] = {}

    def __len__(self) -> int:
        return len(self._claims)

    def add_defining(self, claimant: object, nodes: Iterable[FaceNode]) -> Claim:
        """Record that *nodes* are what established *claimant*, and return the claim.

        *claimant* is normally the record itself; nothing here interprets it.

        Refuses an empty set. A claim naming no face can never appear in :meth:`claims_of`, so
        it can take no part in reconciliation or in per-face scoring -- the only two things
        claims exist for. A candidate with no defining face belongs outside this ledger until a
        family gives absence an explicit meaning.
        """

        defining = frozenset(nodes)
        if not defining:
            raise ValueError(f"{claimant!r} claims no defining face")
        foreign = [node for node in defining if not self._graph.owns(node)]
        if foreign:
            raise ValueError(f"{sorted(node.index for node in foreign)} are not this graph's nodes")

        claim = Claim(claimant, defining)
        self._claims.append(claim)
        for node in defining:
            self._by_node.setdefault(node, []).append(claim)
        return claim

    @property
    def claims(self) -> tuple[Claim, ...]:
        """Every claim, in the order it was made."""

        return tuple(self._claims)

    def claims_of(self, node: FaceNode) -> tuple[Claim, ...]:
        """Every claim naming *node* as defining, in claim order; empty for an unclaimed node.

        This is the direction both consumers read. A reconciler asks it of a candidate's own
        nodes to find what else claims them, and per-face corpus scoring asks it of every node
        -- which ``docs/capabilities.md`` records as impossible today, attribution there being
        statistical rather than per-face.
        """

        return tuple(self._by_node.get(node, ()))
