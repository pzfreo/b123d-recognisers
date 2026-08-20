# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""How the solid turns where two faces meet — the half of an attributed graph this package lacked.

Nodes carried facts about a face. Nothing said what happened *between* two of them, so a
recogniser needing that inferred it at the point of use, or did not ask. `FaceGraph.arc` is that
attribute, and these are the tests that say it is right.

**Symmetry is the assertion that needs no known answer**, and it is the one that caught the two
real errors here. A dihedral is a property of the pair, so `arc(a, b)` and `arc(b, a)` must agree
however the faces are handed in; when they did not, the cause was a sign convention rather than
a hard geometry case, and no amount of counting expected convex edges would have localised it.

The counts below are worth reading carefully, because the obvious expectation is wrong. A blind
pocket has **16** convex arcs and 8 concave, not 12 and 12: its *mouth* edges are convex, because
the material forms a 90-degree wedge where the top face meets a wall, not the 270-degree one the
wall-to-wall and wall-to-floor edges have.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from build123d import Axis, Box, Cone, Cylinder, Pos, Rot, fillet

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._geometry import SMOOTH_ARC_GAP
from tests.golden._common import load_fixture

_CORPUS = Path(__file__).parent / "corpus" / "mfcadpp"


def _arcs(part):
    """Every arc of *part*, counted by classification."""

    graph = FaceGraph(part)
    found: Counter = Counter()
    for a in graph.nodes:
        for b in graph.neighbours(a):
            if b.index > a.index:
                found[graph.arc(a, b)] += 1
    return found


def _plain():
    return Box(20, 20, 20)


def _blind_pocket():
    return Box(40, 40, 20) - Pos(0, 0, 6) * Box(12, 12, 12)


def _through_passage():
    return Box(40, 40, 20) - Box(12, 12, 40)


def _bore():
    return Box(40, 40, 20) - Cylinder(6, 40)


def _countersink():
    return Box(40, 40, 20) - Pos(0, 0, 5) * Cone(9, 4, 12)


def _filleted():
    return fillet(Box(40, 20, 10).edges().filter_by(Axis.Z), radius=3)


@pytest.mark.parametrize(
    "build",
    [_plain, _blind_pocket, _through_passage, _bore, _countersink, _filleted],
)
def test_an_arc_reads_the_same_from_either_face(build):
    """A dihedral belongs to the pair, so the order the faces are handed in cannot matter.

    This is the strongest assertion in the file because it needs no expected answer, and it is
    what localised both real errors during development: flipping the edge direction for a
    ``REVERSED`` face double-corrected what `normal_at` already handled, and it showed up here
    as exactly half a box's edges disagreeing with themselves.
    """

    graph = FaceGraph(build())
    for a in graph.nodes:
        for b in graph.neighbours(a):
            assert graph.arc(a, b) == graph.arc(b, a)


def test_every_edge_of_a_plain_box_is_convex():
    """The sign check. Symmetry alone would survive a global sign error; this will not."""

    assert _arcs(_plain()) == {"convex": 12}


def test_a_pocket_is_concave_where_it_wraps_and_convex_where_it_opens():
    """16 and 8, not 12 and 12 — the mouth edges are convex and the obvious count is wrong.

    Four box verticals, four top perimeter, four bottom perimeter and **four pocket mouths** are
    convex: at a mouth the material is a 90-degree wedge between the top face and the wall. The
    eight concave are the four wall-to-wall verticals and the four wall-to-floor, where the
    material wraps 270 degrees around the edge.
    """

    assert _arcs(_blind_pocket()) == {"convex": 16, "concave": 8}


def test_a_through_void_is_concave_only_along_its_corners():
    """The passage has no floor, so its four concave arcs are the wall-to-wall verticals alone.

    Its two mouths are convex for the same reason a pocket's is, which is why this differs from
    the pocket by exactly the four wall-to-floor arcs.
    """

    assert _arcs(_through_passage()) == {"convex": 20, "concave": 4}


def test_a_curved_face_classifies_and_a_conical_one_does_too():
    """The case a whole-face normal cannot serve, and the reason the attribute reads per point.

    A cone's normal differs everywhere on it, so an arc against one has to be read where the
    faces meet. A groove's conical lead-in is exactly this shape, and it is the geometry
    ADR 0004's amendment is about seeing across.
    """

    assert _arcs(_bore()) == {"convex": 14}
    assert _arcs(_countersink()) == {"convex": 13, "concave": 1}


def test_a_tangential_blend_reads_as_smooth():
    """The half with live consumers: seeing *through* a blend and *across* a split face.

    A fillet meets each neighbour tangentially, so those arcs are neither convex nor concave —
    there is no corner. Four rounded corners, two neighbours each, is eight.

    This is also the assertion that caught the attribute reading normals at the wrong place.
    `normal_at` ignores the point it is handed — asked at 0, 90 and 180 degrees around a
    cylinder it returns one vector three times — so an earlier version read each patch's middle
    and every one of these came back convex, with the tangency invisible.
    """

    assert _arcs(_filleted()) == {"convex": 16, "smooth": 8}


def test_faces_that_do_not_meet_have_no_arc():
    """None, rather than a guess. Two faces with no shared edge have no dihedral to report."""

    graph = FaceGraph(_plain())
    opposite = [
        (a, b)
        for a in graph.nodes
        for b in graph.nodes
        if b.index > a.index and b not in graph.neighbours(a)
    ]
    assert opposite, "a box has opposite faces, or this asserts nothing"
    assert all(graph.arc(a, b) is None for a, b in opposite)


def _slanted_counterbore():
    """A checked-in fixture carrying face pairs that meet along **two** edges.

    Not contrived: swept over the golden corpus, four fixtures have such a pair and this one has
    two, one all-convex and one all-concave. A pair sharing several edges is the case an
    edge-at-a-time classifier answers by accident.
    """

    return load_fixture(
        Path(__file__).parent / "golden" / "slanted_counterbore" / "fixture.py"
    ).build_fixture()


def test_a_pair_meeting_along_several_edges_is_classified_from_all_of_them():
    """The semantic: an arc belongs to the *pair*, and every shared edge has to agree.

    An earlier version read `shared_edges(...)[0]` and so depended on a traversal order
    `neighbours` does not promise. Here the edges do agree, which is why requiring agreement is
    free today -- and why the first pair that disagrees will be loud rather than silently
    order-dependent.
    """

    graph = FaceGraph(_slanted_counterbore())
    multi = [
        (a, b)
        for a in graph.nodes
        for b in graph.neighbours(a)
        if b.index > a.index and len(graph.shared_edges(a, b)) > 1
    ]
    assert multi, "this fixture must still carry a multi-edge pair, or the test proves nothing"

    for a, b in multi:
        per_edge = {graph._classify_at(a, b, edge) for edge in graph.shared_edges(a, b)}
        assert len(per_edge) == 1, "the fixture's edges agree; a disagreement needs its own case"
        assert graph.arc(a, b) == per_edge.pop()


def test_the_answer_does_not_depend_on_the_order_the_shared_edges_come_back_in():
    """Permutation, not just count -- the drift `strict=True` cannot see.

    Classifying every edge and requiring agreement makes this true by construction, which is the
    point: reversing the edge list cannot change a set of size one.
    """

    graph = FaceGraph(_slanted_counterbore())
    for a in graph.nodes:
        for b in graph.neighbours(a):
            edges = graph.shared_edges(a, b)
            if len(edges) < 2:
                continue
            forward = {graph._classify_at(a, b, edge) for edge in edges}
            backward = {graph._classify_at(a, b, edge) for edge in reversed(edges)}
            assert forward == backward


def test_a_shallow_corner_is_not_smooth():
    """The false positive this attribute must not produce, and the reason the gap was measured.

    Seeing *through* a join that is really a shallow step would merge two faces a recogniser
    needs kept apart. The threshold was once 1.8 degrees, chosen on an assumption about kernel
    noise that measurement disproved -- tangencies are *exact*. A one-degree ramp is nowhere near
    smooth and must not read as it.
    """

    ramp = Box(60, 40, 10) - Pos(0, 0, 5) * Rot(0, 1, 0) * Box(80, 60, 10)
    graph = FaceGraph(ramp)
    kinds = {
        graph.arc(a, b)
        for a in graph.nodes
        for b in graph.neighbours(a)
        if b.index > a.index
    }
    assert "smooth" not in kinds

    # And the gap it would have to close is far outside the threshold, by orders of magnitude.
    assert SMOOTH_ARC_GAP < 1e-6, "a shallow corner sits at ~1e-4; the gap must stay well below"


def test_the_classification_is_the_same_at_any_scale():
    """Angles and signs only, so a part a thousand times bigger is the same part to an arc."""

    small = Box(2, 2, 2) - Pos(0, 0, 0.6) * Box(1.2, 1.2, 1.2)
    large = Box(2000, 2000, 2000) - Pos(0, 0, 600) * Box(1200, 1200, 1200)
    assert _arcs(small) == _arcs(large)


@pytest.mark.skipif(
    not (_CORPUS / "MANIFEST.json").is_file(),
    reason="the vendored MFCAD++ subset is excluded from the sdist",
)
def test_imported_step_geometry_classifies_without_unknowns():
    """Generated solids are the easy case; imported B-Rep is what the package is for.

    `unknown` is a real answer and not a failure, but a corpus of ordinary machined parts should
    not need it -- if it starts appearing here, some geometry has stopped being readable and
    that is worth knowing before a recogniser depends on the attribute.
    """

    from build123d import import_step

    models = sorted(_CORPUS.glob("*.step"))[:5]
    assert models, "the vendored corpus must be present for this test to mean anything"
    for path in models:
        graph = FaceGraph(import_step(str(path)))
        for a in graph.nodes:
            for b in graph.neighbours(a):
                assert graph.arc(a, b) in ("convex", "concave", "smooth")


def test_a_repeated_query_does_not_recompute_the_kernel_work():
    """The graph is a run-local memo everywhere else, and an arc is its most expensive fact.

    Surface projection and two first-derivative evaluations per shared edge is not something to
    repeat once several recognisers traverse the same arcs.
    """

    graph = FaceGraph(_plain())
    a = graph.nodes[0]
    b = graph.neighbours(a)[0]

    calls = []
    original = graph._classify_arc
    graph._classify_arc = lambda x, y: (calls.append((x, y)), original(x, y))[1]  # type: ignore[method-assign]

    first = graph.arc(a, b)
    assert len(calls) == 1
    assert graph.arc(a, b) == first
    assert graph.arc(b, a) == first
    assert len(calls) == 1, "the cache must be symmetric, not one entry per ordering"


def test_shared_edges_that_disagree_give_no_single_answer():
    """The rule that makes a multi-edge pair safe, tested as logic rather than hunted as geometry.

    No disagreeing pair has been observed -- a sweep of the checked-in STEP corpus found 49
    pairs sharing two edges and none whose edges classify differently -- so this cannot be
    reached by choosing a fixture. It is still the branch that stops an arc silently depending
    on which edge came back first, which is what the previous implementation did.

    Injecting the disagreement tests the aggregation and nothing else, which is the part that
    was written rather than measured.
    """

    graph = FaceGraph(_plain())
    a = graph.nodes[0]
    b = graph.neighbours(a)[0]
    assert graph.arc(a, b) == "convex", "the real answer, before it is overridden"

    answers = iter(("convex", "concave"))
    graph._arcs.clear()
    graph._classify_at = lambda *_: next(answers)  # type: ignore[method-assign]
    graph.shared_edges = lambda *_: ("first", "second")  # type: ignore[method-assign]

    assert graph.arc(a, b) == "unknown"


def test_a_warm_cache_still_refuses_another_graph_s_nodes():
    """The cache must not become a way past the graph's provenance check.

    `FaceNode` carries only an index, so a node from another graph of an identical part looks
    the same. Every read the graph offers resolves through `owns`, and an arc keyed straight
    off `.index` would have skipped that -- but only on a *hit*, because the miss path validates
    inside `shared_edges`. So the bug appears for the second caller onward and never the first,
    which is why this test warms the cache before it proves anything.

    Answering for the wrong solid is the failure `require_node` and `claims_of` are both written
    to refuse; a cache is not a licence to stop refusing it.
    """

    part, twin = _plain(), _plain()
    graph, other = FaceGraph(part), FaceGraph(twin)
    a = graph.nodes[0]
    b = graph.neighbours(a)[0]

    assert graph.arc(a, b) == "convex", "warm the cache with a pair this graph does own"

    foreign_a = other.nodes[a.index]
    foreign_b = other.nodes[b.index]
    with pytest.raises(ValueError, match="not issued by this graph"):
        graph.arc(foreign_a, foreign_b)
