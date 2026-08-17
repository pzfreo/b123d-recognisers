# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Internal face adjacency: which faces of a part meet along an edge.

Every recogniser that reasons about a face's surroundings needs this, and none owns it, so
it sits beside :mod:`b123d_recognisers._geometry` in the same base layer of ADR 0007 —
depending on nothing but the kernel, depended on by anything.

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
