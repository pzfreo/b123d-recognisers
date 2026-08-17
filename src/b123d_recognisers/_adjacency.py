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
from b123d_recognisers._typing import FaceLike


def edge_face_map(faces: Iterable[FaceLike]) -> dict:
    """Map every edge of *faces* to the faces that meet along it.

    One pass. The pairwise alternative — asking every face pair whether any of their edges
    match — is ``O(faces² × edges²)``; ``fillets`` measured that at 3.7M ``IsSame`` calls
    and about six seconds before replacing it.

    Takes the faces rather than the part because every caller already holds them, and
    walking ``part.faces()`` a second time here measured at a tenth of ``recognise_fillets``
    on the pinned corpus — the same reason :func:`~b123d_recognisers._geometry.part_scale`
    takes a bounding box rather than a solid.

    An edge normally maps to two faces. A seam edge on a closed surface maps to one, and
    a non-manifold edge to more, so callers must not assume the length.
    """

    edge_faces: dict = {}
    for face in faces:
        for edge in face.edges():
            edge_faces.setdefault(edge, []).append(face)
    return edge_faces


def neighbours(face: FaceLike, edge_faces: dict) -> list:
    """The distinct faces sharing an edge with *face*, excluding *face* itself.

    Order follows *face*'s own edge order, so it inherits the part's traversal order and
    nothing more — a caller that needs a deterministic result must sort or reduce it, as
    :func:`b123d_recognisers.recognise_chamfers` does by keeping the nearest neighbour per
    axis rather than the first one seen.
    """

    seen = {face}
    out = []
    for edge in face.edges():
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


def nearest_axis_aligned_planes(
    face: FaceLike, edge_faces: dict, centre: dict[int, float], *, exclude_axis: int
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
    for other in neighbours(face, edge_faces):
        aligned = axis_aligned_axis(other.wrapped)
        if aligned is None or aligned[0] == exclude_axis:
            continue
        ax, coord = aligned
        key = (abs(coord - centre[ax]), coord)
        if ax not in best or key < best[ax]:
            best[ax] = key
    return {ax: coord for ax, (_, coord) in best.items()}
