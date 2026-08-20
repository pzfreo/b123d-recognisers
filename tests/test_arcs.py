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

import pytest
from build123d import Axis, Box, Cone, Cylinder, Pos, fillet

from b123d_recognisers._adjacency import FaceGraph


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
