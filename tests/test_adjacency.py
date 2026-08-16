# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""One answer to "which faces meet along this edge", shared by every recogniser.

Five modules used to answer it separately: an edge→faces dict in ``_hole_features``, a second
one inline in ``fillets``, memoised pairwise closures in ``polygonal_bosses``, and raw
``IsSame`` sweeps in ``chamfers`` and ``flats``. The duplicated *source* was about twenty-five
lines. The risk was never the line count — it was that the dict form keys on build123d shape
equality while the sweeps compared with ``TopoDS_Shape.IsSame``, and **nothing tested that
those two notions of face identity agree**.

So the first test here is the one that made the consolidation safe to do at all: it proves the
two predicates induce the same partition of the edges *and* the faces of every pinned fixture.
The rest pin the behaviour the five call sites relied on.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from build123d import Box, Cylinder

from b123d_recognisers._adjacency import edge_face_map, neighbours

GOLDEN_ROOT = Path(__file__).parent / "golden"


def _partition_by_equality(shapes) -> list[list[int]]:
    groups: dict = {}
    for index, shape in enumerate(shapes):
        groups.setdefault(shape, []).append(index)
    return sorted(sorted(members) for members in groups.values())


def _partition_by_is_same(shapes) -> list[list[int]]:
    representatives: list = []
    groups: dict[int, list[int]] = {}
    for index, shape in enumerate(shapes):
        for rep_index, rep in enumerate(representatives):
            if rep.IsSame(shape.wrapped):
                groups[rep_index].append(index)
                break
        else:
            representatives.append(shape.wrapped)
            groups[len(representatives) - 1] = [index]
    return sorted(sorted(members) for members in groups.values())


def test_shape_equality_and_is_same_agree_across_the_whole_corpus():
    """The premise the module rests on, measured rather than assumed.

    build123d shape equality is ``TShape`` + ``Location`` and orientation-insensitive — the
    same predicate ``IsSame`` implements. If that ever stopped being true, keying an
    edge→faces dict would silently stop agreeing with the pairwise comparisons it replaced,
    and face adjacency would change for every recogniser at once with nothing to catch it.

    Checked on every pinned fixture rather than one shape, because the two predicates can
    only diverge on topology that shares a ``TShape`` — seams, split faces, repeated
    sub-shapes — which no single hand-written solid reliably produces.
    """

    checked = 0
    for path in sorted(GOLDEN_ROOT.glob("*/fixture.py")):
        spec = importlib.util.spec_from_file_location(f"fixture_{path.parent.name}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        part = module.build_fixture()
        name = path.parent.name

        edges = [edge for face in part.faces() for edge in face.edges()]
        assert _partition_by_equality(edges) == _partition_by_is_same(edges), f"edges of {name}"

        faces = list(part.faces())
        assert _partition_by_equality(faces) == _partition_by_is_same(faces), f"faces of {name}"
        checked += 1

    assert checked == 17, "the corpus moved; this test must still sweep all of it"


def test_a_manifold_edge_maps_to_the_two_faces_that_meet_along_it():
    """A box has twelve edges, each shared by exactly two of its six faces."""

    edge_faces = edge_face_map(Box(10, 10, 10))

    assert len(edge_faces) == 12
    assert {len(faces) for faces in edge_faces.values()} == {2}


def test_a_seam_edge_maps_to_a_single_face():
    """A closed cylindrical surface carries a seam belonging to one face only.

    ``edge_face_map`` must not promise two faces per edge. A caller that assumed it would
    misread a plain turned shaft, where the seam is an ordinary part of the topology rather
    than a defect.
    """

    edge_faces = edge_face_map(Cylinder(5, 20))

    assert sorted({len(faces) for faces in edge_faces.values()}) == [1, 2]


def test_neighbours_excludes_the_face_itself_and_never_repeats_one():
    """A box face touches the four faces around it — each once, and not itself.

    Both properties are load-bearing. ``recognise_chamfers`` and ``recognise_fillets`` keep
    the nearest neighbour plane per axis, so a face yielded twice would be weighed twice,
    and the face itself appearing as its own neighbour is trivially the nearest of all.
    """

    part = Box(10, 10, 10)
    edge_faces = edge_face_map(part)
    face = part.faces()[0]

    found = neighbours(face, edge_faces)

    assert len(found) == 4
    assert face not in found
    assert len(set(found)) == len(found)


def test_neighbours_is_empty_when_the_map_does_not_cover_the_face():
    """A face absent from the map has no neighbours rather than raising.

    The recognisers all build the map from the same part they query, so this is a contract
    for the helper rather than a path they reach — but it is the difference between a
    mis-paired map returning nothing and it raising ``KeyError`` from inside a recogniser.
    """

    assert neighbours(Box(10, 10, 10).faces()[0], {}) == []
