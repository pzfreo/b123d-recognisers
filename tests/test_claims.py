# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""What a recogniser built a candidate from, so overlap stops being answered by coordinates.

The defect this exists for is concrete: `recognise_passages` suppressed a passage whose XY
centre matched a slot's, comparing two numbers derived by different procedures and ignoring
the passage's own axis. The last test here builds the geometry that defeats that answer — a
bore and a channel whose XY centres are *identical* to the last bit, sharing no face at all.

The rest pin the three properties the design rests on: claims are separable from the graph's
geometric facts, two equal-valued records stay distinguishable, and nothing a recogniser
writes can be read back in a way that changes what another recogniser sees.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import pytest
from build123d import Box, Cylinder, Pos

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._claims import ClaimLedger


@dataclass(frozen=True)
class Candidate:
    """A stand-in with record semantics: frozen, hashable, and equal by value."""

    kind: str


def test_two_equal_valued_claimants_stay_distinguishable():
    """The reason a claim is an object compared by identity, not a lookup keyed on the record.

    Records compare by value, so a table keyed on the claimant would have merged two
    equal-valued candidates into one entry covering the union of their faces — and a
    reconciler asked which of them to keep would have found a single claim naming both sets.
    """

    graph = FaceGraph(Box(10, 10, 10))
    ledger = ClaimLedger(graph)
    first = ledger.add_defining(Candidate("slot"), graph.nodes[:2])
    second = ledger.add_defining(Candidate("slot"), graph.nodes[2:4])

    assert first.claimant == second.claimant
    assert first is not second and first != second
    assert first.defining == frozenset(graph.nodes[:2])
    assert second.defining == frozenset(graph.nodes[2:4])
    assert len(ledger) == 2
    assert ledger.claims == (first, second)


def test_a_node_reports_every_claim_naming_it():
    """Both consumers read this direction: reconciliation, and per-face corpus scoring."""

    graph = FaceGraph(Box(10, 10, 10))
    ledger = ClaimLedger(graph)
    passage = ledger.add_defining(Candidate("passage"), graph.nodes[:3])
    slot = ledger.add_defining(Candidate("slot"), graph.nodes[2:4])

    assert ledger.claims_of(graph.nodes[0]) == (passage,)
    assert ledger.claims_of(graph.nodes[2]) == (passage, slot)
    assert ledger.claims_of(graph.nodes[5]) == ()


def test_a_node_of_another_graph_is_refused():
    """A ledger paired with the wrong graph would report overlaps between different solids.

    The foreign node here is genuinely valid — it is in range for the local graph too — which
    is exactly the case a bounds check cannot distinguish and identity can.
    """

    graph = FaceGraph(Box(10, 10, 10))
    other = FaceGraph(Box(4, 4, 4))
    ledger = ClaimLedger(graph)

    with pytest.raises(ValueError, match=r"\[1\]"):
        ledger.add_defining(Candidate("slot"), [graph.nodes[0], other.nodes[1]])

    assert len(ledger) == 0, "a refused claim must not be half-recorded"
    assert ledger.claims_of(graph.nodes[0]) == ()


def test_reading_claims_for_a_foreign_node_is_refused_rather_than_answered():
    """The one error shape the write-side check cannot catch.

    Answering ``()`` would let a reconciler read "this node belongs to another graph" as "this
    face is unclaimed" — a silent false negative in the ownership logic this layer exists to
    protect. The foreign node here is in range locally, and the local node at that index is
    genuinely claimed, so a bounds check would have answered wrongly rather than not at all.
    """

    graph = FaceGraph(Box(10, 10, 10))
    other = FaceGraph(Box(4, 4, 4))
    ledger = ClaimLedger(graph)
    ledger.add_defining(Candidate("slot"), [graph.nodes[1]])

    assert ledger.claims_of(graph.nodes[1]), "the local node at this index must be claimed"
    with pytest.raises(ValueError, match="not this graph's node"):
        ledger.claims_of(other.nodes[1])


def test_a_registered_claim_cannot_be_rewritten():
    """Append-only in fact, not in name.

    The ledger indexes each claim under the nodes it named, so a writable ``defining`` would
    let the claim and ``claims_of`` contradict each other about the same ledger.
    """

    graph = FaceGraph(Box(10, 10, 10))
    ledger = ClaimLedger(graph)
    claim = ledger.add_defining(Candidate("slot"), [graph.nodes[0]])

    with pytest.raises(dataclasses.FrozenInstanceError):
        claim.defining = frozenset({graph.nodes[1]})
    with pytest.raises(dataclasses.FrozenInstanceError):
        claim.claimant = Candidate("pocket")

    assert claim.defining == frozenset({graph.nodes[0]})
    assert ledger.claims_of(graph.nodes[0]) == (claim,)
    assert ledger.claims_of(graph.nodes[1]) == ()


def test_a_claim_with_no_defining_face_is_refused():
    """It could never appear in ``claims_of``, so it can take part in neither consumer.

    Rejecting it keeps absence from being expressed by accident: a family that means something
    by "no defining face" has to say so deliberately.
    """

    ledger = ClaimLedger(FaceGraph(Box(10, 10, 10)))
    with pytest.raises(ValueError, match="claims no defining face"):
        ledger.add_defining(Candidate("slot"), [])

    assert len(ledger) == 0


def test_write_only_evidence_adapter_refuses_an_empty_defining_claim():
    """Aggregate discovery cannot bypass the ledger's non-vacuous claim invariant."""

    ledger = ClaimLedger(FaceGraph(Box(10, 10, 10)))

    with pytest.raises(ValueError, match="claims no defining face"):
        ledger.writer.add_defining(Candidate("slot"), [])

    assert ledger.claims == ()


def test_claiming_changes_nothing_the_graph_answers():
    """Write-only, stated as a property of the pair rather than asserted in prose.

    If any geometric answer moved once a claim was made, a recogniser running second would see
    a different graph from one running first — precisely the order dependence that keeping
    claims out of the graph avoids.
    """

    graph = FaceGraph(featured_part())
    ledger = ClaimLedger(graph)
    snapshot = [
        (graph.neighbours(node), graph.bounds(node), graph.normal(node), graph.is_planar(node))
        for node in graph.nodes
    ]

    for node in graph.nodes:
        ledger.add_defining(Candidate(f"candidate-{node.index}"), [node])

    assert snapshot == [
        (graph.neighbours(node), graph.bounds(node), graph.normal(node), graph.is_planar(node))
        for node in graph.nodes
    ]
    assert not hasattr(graph, "_claims"), "ownership must not have leaked back onto the graph"


def featured_part():
    return Box(60, 40, 12) - Pos(-18, 0, 0) * Cylinder(4, 12) - Pos(15, 0, 0) * Box(24, 8, 12)


def test_claimed_faces_separate_features_that_share_an_xy_centre():
    """The case the coordinate heuristic gets wrong, on real geometry.

    A Z bore and an X-running channel through the same part have *exactly* the same XY centre,
    so suppressing one because the other's centre matched within a tolerance would delete a
    genuine feature. They share no defining face, and the ledger says so.
    """

    part = Box(60, 40, 20) - Cylinder(3, 20) - Pos(0, 0, 6) * Box(60, 8, 4)
    graph = FaceGraph(part)
    ledger = ClaimLedger(graph)

    bore = [node for node in graph.nodes if not graph.is_planar(node)]
    channel = [
        node
        for node in graph.nodes
        if graph.is_planar(node)
        and abs((graph.normal(node) or (0, 0, 0))[1]) > 0.99
        and max(abs(edge) for edge in graph.bounds(node)[1]) < 10.0
    ]
    # Pinned so a fixture change cannot quietly reduce either side to nothing and leave the
    # disjointness assertion below passing for the wrong reason: the channel splits the bore
    # into two cylindrical bands, and the channel contributes its two side walls.
    assert (len(bore), len(channel)) == (2, 2)

    bore_claim = ledger.add_defining(Candidate("bore"), bore)
    channel_claim = ledger.add_defining(Candidate("channel"), channel)

    assert _xy_centre(graph, bore) == pytest.approx(_xy_centre(graph, channel), abs=1e-9)
    assert bore_claim.defining & channel_claim.defining == frozenset()
    assert all(ledger.claims_of(node) == (bore_claim,) for node in bore)
    assert all(ledger.claims_of(node) == (channel_claim,) for node in channel)


def _xy_centre(graph, nodes):
    spans = [graph.bounds(node) for node in nodes]
    return (
        sum(lo + hi for (lo, hi), _, _ in spans) / (2 * len(spans)),
        sum(lo + hi for _, (lo, hi), _ in spans) / (2 * len(spans)),
    )
