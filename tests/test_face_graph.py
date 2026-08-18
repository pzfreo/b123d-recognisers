# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""One node per face: the attributes seven modules derive privately, and who claimed what.

Two properties carry this class, and neither is a golden.

The first is that it is the *same* answer the free functions already give. ``FaceGraph`` is
only worth having if a recogniser can move onto it without its output moving, so the
attribute and adjacency tests here compare it against the derivation it replaces on a part
carrying real features, rather than against a captured expectation.

The second is that the graph is geometric fact and nothing else. It carries no ownership: who
claimed which face is an interpretation, and lives in the separate ledger tested in
:mod:`tests.test_claims`.
"""

from __future__ import annotations

from build123d import Axis, Box, Cylinder, Pos, chamfer, fillet

from b123d_recognisers._adjacency import FaceEdges, FaceGraph, edge_face_map, neighbours


def featured_part():
    """A part with a hole, a slot, a chamfer and a fillet, so no node is a bare box face."""

    part = Box(60, 40, 12) - Pos(-18, 0, 0) * Cylinder(4, 12) - Pos(15, 0, 0) * Box(24, 8, 12)
    part = chamfer(part.edges().filter_by(Axis.Z).group_by(Axis.X)[0], 1.5)
    return fillet(part.edges().filter_by(Axis.Z).group_by(Axis.X)[-1], 2.0)


def test_a_face_from_a_second_walk_resolves_to_the_same_node():
    """The property the whole graph rests on, stated directly.

    Every consumer reaches the graph holding faces it got from its own ``part.faces()`` call,
    so if a second walk produced faces the index did not recognise, every lookup would return
    None and the graph would silently do nothing. Asserting the count first stops a part that
    yielded nothing from passing this vacuously.
    """

    part = featured_part()
    graph = FaceGraph(part)
    second = part.faces()

    assert len(second) == len(graph) > 10
    assert sorted(graph.node_of(face) for face in second) == list(graph.nodes)


def test_a_face_of_another_part_has_no_node():
    """None rather than KeyError, so a caller reconciling across parts gets an answer."""

    assert FaceGraph(Box(10, 10, 10)).node_of(Box(4, 4, 4).faces()[0]) is None


def test_attributes_agree_with_the_derivations_they_replace():
    """Every node's attributes match the direct kernel call the seven modules make today.

    This is the migration safety property: a recogniser that swaps ``face.bounding_box()`` for
    ``graph.bounds(node)`` must not change its own answer.
    """

    part = featured_part()
    graph = FaceGraph(part)

    for node in graph.nodes:
        face = graph.face(node)
        box = face.bounding_box()
        assert graph.bounds(node) == (
            (box.min.X, box.max.X),
            (box.min.Y, box.max.Y),
            (box.min.Z, box.max.Z),
        )
        assert graph.is_planar(node) == (face.geom_type.name == "PLANE")

        unit = face.normal_at()
        assert graph.normal(node) == (unit.X, unit.Y, unit.Z)
        assert set(graph.edges(node)) == set(face.edges())
        assert len(graph.edges(node)) == len(face.edges())

    assert any(not graph.is_planar(node) for node in graph.nodes), "no curved face to check"


def test_adjacency_agrees_with_the_free_function():
    """The graph's neighbours are the existing helper's neighbours, node for node."""

    part = featured_part()
    graph = FaceGraph(part)
    faces = part.faces()
    by_edge = edge_face_map(faces)

    for node in graph.nodes:
        expected = {graph.node_of(face) for face in neighbours(graph.face(node), by_edge)}
        assert set(graph.neighbours(node)) == expected
        assert len(graph.neighbours(node)) == len(expected), "a neighbour was reported twice"

    assert any(graph.neighbours(node) for node in graph.nodes)


def test_shared_edges_are_non_empty_exactly_for_neighbours():
    """Adjacency and the edges that cause it are one answer, not two that could disagree."""

    graph = FaceGraph(featured_part())
    checked = 0
    for node in graph.nodes:
        for other in graph.nodes:
            if other == node:
                continue
            shared = graph.shared_edges(node, other)
            assert bool(shared) == (other in graph.neighbours(node))
            checked += bool(shared)
    assert checked


def test_attributes_are_not_derived_until_asked():
    """Laziness is the documented reason this costs nothing to construct.

    Measured, sharing the walk over ``part.faces()`` is worth 1.9% of a census while the
    derivations hanging off it are worth far more — so a graph built by a recogniser that only
    wants adjacency must not pay for normals, surfaces or bounds.
    """

    graph = FaceGraph(featured_part())
    assert (graph._normal, graph._surface, graph._bounds, graph._edges) == ({}, {}, {}, {})

    graph.normal(0)
    assert graph._normal and not graph._surface and not graph._bounds


def test_an_injected_face_edges_memo_is_the_one_actually_used():
    """ADR 0002's rule: prove the injected dependency is used by making it answer differently.

    A graph that quietly built its own memo would still pass every other test here while
    paying the ``Face.edges()`` cost a second time across a census, which is the whole reason
    the memo is threaded.
    """

    class Truncating(FaceEdges):
        def of(self, face):
            return super().of(face)[:1]

    part = featured_part()
    assert all(len(FaceGraph(part).edges(node)) > 1 for node in FaceGraph(part).nodes)

    injected = FaceGraph(part, face_edges=Truncating())
    assert all(len(injected.edges(node)) == 1 for node in injected.nodes)
