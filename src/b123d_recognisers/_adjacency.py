# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Internal face adjacency: which faces of a part meet along an edge.

Every recogniser that reasons about a face's surroundings needs this, and none owns it, so
it sits in ADR 0007's base layer — depending on nothing but the kernel and
:mod:`b123d_recognisers._geometry`'s thresholds, depended on by anything.

It was previously answered five separate ways: an edge→faces dict in ``_hole_features``, a
second one inline in ``fillets``, memoised pairwise closures in ``polygonal_bosses``, and
raw ``IsSame`` sweeps in ``chamfers`` and ``flats``. The line count of that duplication was
small; the risk was not, because nothing tested that five implementations of face identity
agreed. ``tests/test_adjacency.py`` now pins the one answer they share.

**Identity is build123d shape equality**, which is ``TShape`` plus ``Location`` and
orientation-insensitive — exactly the ``IsSame`` predicate the pairwise sweeps used, so
routing them through a dict is behaviour-preserving rather than merely equivalent-looking.
That equivalence is measured, not assumed: :func:`tests.test_adjacency` proves both
predicates induce the same partition of the edges *and* the faces of every pinned fixture.
"""

from __future__ import annotations

from collections.abc import Iterable

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane

from b123d_recognisers._geometry import AXIS_ALIGNED_COS
from b123d_recognisers._typing import EdgeLike, FaceLike


class FaceEdges:
    """Per-face edge lists, computed once and shared for the length of one recognition run.

    ``Face.edges()`` is the single most expensive derived query the suite makes — measured at
    24% of a full :func:`b123d_recognisers.census.feature_census` over the pinned corpus, at
    ~107 µs a call — and every recogniser asks it of the same faces of the same part.

    **The sharing has to cross recogniser boundaries to pay.** Memoising within one
    recogniser call is worth about 2% and is a net loss for several of them; sharing one memo
    across a whole census is worth about 20%. That asymmetry is the whole reason this is a
    threaded parameter rather than a detail each recogniser could keep to itself, and it is
    why ``part.faces()`` sharing — the obvious candidate — is not the answer: re-walking the
    part's faces is only 1.9% of a census, because the walk is cheap and the *derivation*
    hanging off each face is not.

    Keyed on the face itself. build123d shape equality is ``TShape`` + ``Location``, i.e.
    ``IsSame``, proven over every fixture in :mod:`tests.test_adjacency` — so two wrappers for
    the same face, from two different ``part.faces()`` calls in two different recognisers, hit
    the same entry. That proof is what makes this safe; without it the memo would silently
    miss and quietly cost more than it saved.

    Scope it to a single run over a single part. It holds its faces alive, and it must not
    outlive geometry that could be rebuilt.

    The returned list is the memo's own, not a copy: **callers must not mutate it.** Every
    call site either iterates it or derives a new list with ``filter_by``/``sorted``.
    """

    def __init__(self) -> None:
        self._of: dict = {}

    def of(self, face: FaceLike) -> list[EdgeLike]:
        """The edges of *face*, computed on first ask and reused thereafter."""

        edges = self._of.get(face)
        if edges is None:
            self._of[face] = edges = face.edges()
        return edges


def edge_face_map(faces: Iterable[FaceLike], *, face_edges: FaceEdges | None = None) -> dict:
    """Map every edge of *faces* to the faces that meet along it.

    One pass. The pairwise alternative — asking every face pair whether any of their edges
    match — is ``O(faces² × edges²)``; ``fillets`` measured that at 3.7M ``IsSame`` calls
    and about six seconds before replacing it.

    Takes the faces rather than the part because every caller already holds them, and
    walking ``part.faces()`` a second time here measured at a tenth of ``recognise_fillets``
    on the pinned corpus — the same reason :func:`~b123d_recognisers._geometry.part_scale`
    takes a bounding box rather than a solid.

    Pass *face_edges* to reuse a :class:`FaceEdges` memo across recognisers; omitted, the map
    is built from a private one, so a lone recogniser call behaves exactly as before.

    An edge normally maps to two faces. A seam edge on a closed surface maps to one, and
    a non-manifold edge to more, so callers must not assume the length.
    """

    memo = face_edges if face_edges is not None else FaceEdges()
    edge_faces: dict = {}
    for face in faces:
        for edge in memo.of(face):
            edge_faces.setdefault(edge, []).append(face)
    return edge_faces


def neighbours(face: FaceLike, edge_faces: dict, *, face_edges: FaceEdges | None = None) -> list:
    """The distinct faces sharing an edge with *face*, excluding *face* itself.

    Order follows *face*'s own edge order, so it inherits the part's traversal order and
    nothing more — a caller that needs a deterministic result must sort or reduce it, as
    :func:`b123d_recognisers.recognise_chamfers` does by keeping the nearest neighbour per
    axis rather than the first one seen.

    *face_edges* reuses a shared :class:`FaceEdges` memo; this is the hottest caller of it,
    since the blend recognisers ask for the neighbours of every face of the part.
    """

    seen = {face}
    out = []
    for edge in (face_edges.of(face) if face_edges is not None else face.edges()):
        for other in edge_faces.get(edge, ()):
            if other in seen:
                continue
            seen.add(other)
            out.append(other)
    return out


def axis_aligned_axis(face_wrapped) -> tuple[int, float] | None:
    """The axis a planar face's normal aligns with and that plane's fixed coordinate along
    it, or None if the face is not planar or not axis-aligned. Sign-agnostic (only alignment
    matters here); the coordinate locates the plane."""

    s = BRepAdaptor_Surface(face_wrapped)
    if s.GetType() != GeomAbs_Plane:
        return None
    d = s.Plane().Axis().Direction()
    comp = (abs(d.X()), abs(d.Y()), abs(d.Z()))
    if max(comp) <= AXIS_ALIGNED_COS:
        return None
    ax = max(range(3), key=lambda i: comp[i])
    loc = s.Plane().Location()
    return ax, (loc.X(), loc.Y(), loc.Z())[ax]


def has_triangular_companion(
    face: FaceLike, edge_faces: dict, *, face_edges: FaceEdges | None = None
) -> bool:
    """Is *face* edge-adjacent to an axis-aligned planar face bounded by exactly three edges?

    The single question that separates an angled blind step from a chamfer. A chamfer strip
    runs the whole length of the edge it breaks, so its neighbours are the two walls it
    bridges. An angled step stops part-way into the part, and a triangular flat is what
    closes the blind end.

    It lives here, rather than in either recogniser, because *both* consult it and they must
    agree: ``recognise_chamfers`` declines a bevel that has such a companion and
    ``recognise_angled_steps`` requires one. Two separate copies that drifted would not
    produce a double-count — they would make the feature disappear from the census, claimed
    by neither, which is far harder to notice.

    Note this asks a purely topological question. Unlike a size gate it says nothing about
    the part around the face, so a step is a step at any scale.
    """

    for other in neighbours(face, edge_faces, face_edges=face_edges):
        if axis_aligned_axis(other.wrapped) is None:
            continue
        edges = face_edges.of(other) if face_edges is not None else other.edges()
        if len(edges) == 3:
            return True
    return False


def nearest_axis_aligned_planes(
    face: FaceLike,
    edge_faces: dict,
    centre: dict[int, float],
    *,
    exclude_axis: int,
    face_edges: FaceEdges | None = None,
) -> dict[int, float]:
    """Per axis, the coordinate of *face*'s nearest axis-aligned neighbour plane.

    The shared "what does this blend bridge" query. ``recognise_chamfers`` and
    ``recognise_fillets`` both need a bevel's or round's two neighbour planes to rebuild the
    virtual sharp corner it replaces, and both previously carried their own copy of this
    filter and its supporting :func:`axis_aligned_axis` — identical code, with each file's
    comment pointing at the other. A caller reads the result twice: an axis missing from it
    means no such neighbour on that axis, which is itself a rejection.

    *exclude_axis* is the axis the feature runs **along**; a plane facing that way is an end
    cap, not one of the two walls the feature bridges.

    The nearest plane per axis is the one forming this local corner. Ties break on the
    coordinate itself rather than on arrival, so the pick cannot depend on the order the
    kernel yields neighbours in — ``slanted_steps`` has a chamfer equidistant from two
    distinct Z planes, where the strict ``<`` this replaces kept whichever came first.
    """

    best: dict[int, tuple[float, float]] = {}  # axis -> (distance, coordinate)
    for other in neighbours(face, edge_faces, face_edges=face_edges):
        aligned = axis_aligned_axis(other.wrapped)
        if aligned is None or aligned[0] == exclude_axis:
            continue
        ax, coord = aligned
        key = (abs(coord - centre[ax]), coord)
        if ax not in best or key < best[ax]:
            best[ax] = key
    return {ax: coord for ax, (_, coord) in best.items()}
