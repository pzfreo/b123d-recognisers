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

**Overlap is not exclusion.** Two claims sharing a defining face is evidence for a reconciler to
weigh, not a verdict. Which of them survives — or whether both do, as a pattern and its members
both legitimately do — is the reconciler's policy under ADR 0003, and is not decided here.
"""

from __future__ import annotations

from collections.abc import Iterable

from b123d_recognisers._adjacency import FaceGraph


class ClaimLedger:
    """Append-only claims against the nodes of one :class:`FaceGraph`.

    Bound to a graph so that a node id from a different part cannot be recorded silently. Node
    ids mean nothing outside the graph that issued them, and a mis-paired ledger would otherwise
    produce overlaps between faces of different solids.
    """

    def __init__(self, graph: FaceGraph) -> None:
        self._graph = graph
        self._claimants: list[object] = []
        self._defining: list[frozenset[int]] = []
        self._by_node: dict[int, list[int]] = {}

    def __len__(self) -> int:
        return len(self._claimants)

    def add_defining(self, claimant: object, nodes: Iterable[int]) -> int:
        """Record that *nodes* are what established *claimant*, and return the claim's id.

        **An id rather than the claimant as the key**, because records compare by value: two
        equal-valued candidates are distinguishable to a reconciler only if the ledger keeps
        them apart, and a dict keyed on the record would have merged them into one claim
        covering both their faces.

        *claimant* is normally the record itself; nothing here interprets it.
        """

        valid = self._graph.nodes
        claimed = frozenset(nodes)
        outside = sorted(node for node in claimed if node not in valid)
        if outside:
            raise ValueError(f"nodes {outside} are not in this ledger's graph")

        claim = len(self._claimants)
        self._claimants.append(claimant)
        self._defining.append(claimed)
        for node in claimed:
            self._by_node.setdefault(node, []).append(claim)
        return claim

    @property
    def claims(self) -> range:
        """Every claim id, in the order they were made."""

        return range(len(self._claimants))

    def claimant(self, claim: int) -> object:
        """What the claim was made on behalf of."""

        return self._claimants[claim]

    def defining(self, claim: int) -> frozenset[int]:
        """The nodes that established *claim*."""

        return self._defining[claim]

    def claims_of(self, node: int) -> tuple[int, ...]:
        """Every claim naming *node* as defining, in claim order; empty for an unclaimed node.

        This is the direction both consumers read. A reconciler asks it of a candidate's own
        nodes to find what else claims them, and per-face corpus scoring asks it of every node
        — which `docs/capabilities.md` records as impossible today, attribution there being
        statistical rather than per-face.
        """

        return tuple(self._by_node.get(node, ()))
