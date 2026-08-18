# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""Prismatic passage recognition: a polygonal void running through the material.

A **passage** is a closed ring of planar walls with nothing capping either end. MFCAD++ splits
them by cross-section -- triangular, rectangular, six-sided -- but the geometry does not: they
are one shape with a side count, and measured over 120 of its models the count is exactly the
polygon's, 3 in 74 of 91 triangular instances, 4 in 40 of 64 rectangular, 6 in 46 of 60
six-sided.

What separates a passage from its neighbours is what is *not* there:

- **from a pocket, the floor.** A pocket's ring is capped at one end by a face perpendicular to
  the run axis and filling the ring's cross-section. A passage's is capped at neither end.
  Distinguishing that cap from the part's own end face matters and is easy to get wrong: at a
  passage mouth the outer face is perpendicular and edge-adjacent too, so the test is whether
  it *fills* the ring or the ring is a hole punched through it.
- **from a polygonal boss, the material.** The same ring bounds a prism when the material is
  inside it and a void when the material is outside, which one solid-classifier probe answers --
  at a point proved to lie inside the cross-section, not at an average that may not.

**A through slot is also a passage, and this module says so.** The two families describe the
same void from different directions, and reconciling them is not this recogniser's job: a
recogniser that dropped a ring because `recognise_slots` had claimed it would be consulting
another family's result during discovery, which ADR 0002 forbids outright ("recognisers do not
call sibling recognisers") and ADR 0003 forbids by name. An earlier draft did exactly that,
comparing a ring's averaged centre against a slot record's XY centre within 1e-6. So this module
reports every ring it finds and records which faces each was built from;
:func:`b123d_recognisers.build_recognition_result` holds the one named rule that resolves the
overlap. `recognise_passages` alone therefore reports *candidates*, and the aggregate reports
the reconciled set -- the two differ by exactly the through slots.

Over 120 MFCAD++ models: 100% precision, 51% instance recall (65 of 128) and 49% of
labelled faces, measured against that corpus's own labels. The corpus is synthetic and the
recall gap is one thing rather than many -- walls whose spans differ, because a passage running
through a stepped region has one wall shorter than the rest, so the ring never forms.

Every gate is topological or a direction comparison. There is no size gate and no tolerance on
a length, so a passage is a passage at any scale -- ``tests/test_scale_invariance.py`` carries
the family with no exclusion.

The face attributes come from :class:`b123d_recognisers._adjacency.FaceGraph`. An earlier draft
built its own index map, neighbour map, planar-normal map and bounding-box map inside this
function -- an ad hoc face graph private to one recogniser, which is what the substrate exists
to stop. Ring-finding is :func:`b123d_recognisers._adjacency.connected_components`, shared with
``polygonal_bosses``, which finds the same ring from outside.
"""

from __future__ import annotations

from dataclasses import dataclass

from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_OUT

from b123d_recognisers._adjacency import (
    FaceEdges,
    FaceGraph,
    FaceNode,
    connected_components,
)
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._geometry import AXIS_ZERO_COS
from b123d_recognisers._record import Record
from b123d_recognisers._typing import Part

#: Two walls belong to one ring when their spans along the run axis agree. A coordinate
#: comparison between two faces of one feature, so ADR 0008 makes it a tolerance rather than a
#: minimum-evidence threshold -- but it compares two derivations of the *same* extrusion, which
#: differ only by kernel noise, so it is a float epsilon and not a length at all.
_SPAN_EPS = 1e-6


@dataclass(frozen=True, order=True)
class Passage(Record):
    """A recognised passage.

    ``axis`` is the direction it runs ("x"/"y"/"z"); ``sides`` is the number of walls, so a
    triangular passage reports 3 and a hexagonal one 6; ``length`` is how far it runs; ``at`` is
    the centre of the void in part space.

    ``section`` is the cross-section: its corners in part coordinates, in the two axes other
    than ``axis`` and in that axis order, walked around the ring. Without it the record could
    not describe the feature it names -- two passages of radically different size, aspect ratio
    and rotation produced the same record apart from centre and length, which is a taxonomy
    label rather than a dimension a consumer can draw from. From the corners a consumer can
    take across-flats, area, aspect and orientation; a single scalar could not, because 63% of
    the corpus's passages are not regular polygons.

    The walk is canonical, not the kernel's: corners run anticlockwise in the two section axes,
    starting at the lexicographically smallest, so equivalent geometry gives an equal record
    however the part was traversed.
    """

    axis: str
    sides: int
    length: float
    at: tuple[float, float, float]
    section: tuple[tuple[float, float], ...]


def recognise_passages(
    part: Part,
    *,
    face_edges: FaceEdges | None = None,
    ledger: ClaimLedger | None = None,
) -> list[Passage]:
    """Recognise the prismatic passages of *part* (see module docstring).

    Returns one :class:`Passage` per closed uncapped ring, sorted deterministically. Empty when
    the part has none. Only passages whose walls all run parallel to one principal axis, share
    one span, and meet their neighbours along a single edge parallel to that axis are recovered;
    a passage whose walls step or taper along its length is not one.

    **A through slot is reported here too** -- it is a closed uncapped ring. The families are
    reconciled in :func:`b123d_recognisers.build_recognition_result` and not here; see the
    module docstring for why that separation is not optional.

    *ledger* records which faces each returned passage was built from: its ring, and nothing
    else. When it is given, its graph is used as the face inventory, so *face_edges* is then the
    memo that graph was built with rather than one taken here.
    """

    graph = FaceGraph(part, face_edges=face_edges) if ledger is None else ledger.graph
    planar = [node for node in graph.nodes if graph.is_planar(node)]
    normal = {node: graph.normal(node) for node in planar}

    found: list[tuple[Passage, tuple[FaceNode, ...]]] = []
    for axis in (0, 1, 2):
        walls = [
            node
            for node in planar
            if normal[node] is not None and abs(normal[node][axis]) <= AXIS_ZERO_COS  # type: ignore[index]
        ]
        adjacent = {node: set(graph.neighbours(node)) for node in walls}

        def shares_a_span(
            a: FaceNode, b: FaceNode, axis: int = axis, adjacent: dict = adjacent
        ) -> bool:
            return (
                b in adjacent[a]
                and abs(graph.bounds(a)[axis][0] - graph.bounds(b)[axis][0]) <= _SPAN_EPS
                and abs(graph.bounds(a)[axis][1] - graph.bounds(b)[axis][1]) <= _SPAN_EPS
            )

        for ring in connected_components(walls, shares_a_span):
            members = set(ring)
            if len(ring) < 3 or any(len(adjacent[node] & members) != 2 for node in ring):
                continue  # a ring closes; a chain of walls does not
            section = _cross_section(graph, ring, members, axis)
            if section is None:
                continue  # the walls do not meet in a simple prismatic polygon
            spans = [graph.bounds(node)[axis] for node in ring]
            low, high = min(a for a, _ in spans), max(b for _, b in spans)
            if _capped(graph, ring, members, axis, low, high):
                continue  # a floor fills the ring: this is a pocket
            if not _is_void(part, section, axis, low, high):
                continue
            others = [a for a in (0, 1, 2) if a != axis]
            middle = _centroid(section)
            at = [0.0, 0.0, 0.0]
            at[axis] = 0.5 * (low + high)
            at[others[0]], at[others[1]] = middle
            found.append(
                (
                    Passage(
                        axis="xyz"[axis],
                        sides=len(ring),
                        length=round(high - low, 3),
                        at=(round(at[0], 3), round(at[1], 3), round(at[2], 3)),
                        section=tuple((round(u, 3), round(v, 3)) for u, v in section),
                    ),
                    tuple(ring),
                )
            )

    found.sort(key=lambda pair: (pair[0].axis, pair[0].at))
    if ledger is not None:
        for passage, ring in found:
            ledger.add_defining(passage, ring)
    return [passage for passage, _ in found]


def _cross_section(
    graph: FaceGraph, ring: tuple[FaceNode, ...], members: set[FaceNode], axis: int
) -> tuple[tuple[float, float], ...] | None:
    """The ring's corners, walked around it, or None when it is not a prismatic polygon.

    Each corner is where two consecutive walls meet, so it is read from the edge they share
    rather than from an average of anything. That edge must be a single one parallel to the run
    axis: two walls meeting along two edges, or along an edge that is not straight down the
    passage, are not the prismatic ring this family recognises, and returning None is how they
    are declined rather than silently mis-measured.
    """

    others = [a for a in (0, 1, 2) if a != axis]
    order = [ring[0]]
    seen = {ring[0]}
    while len(order) < len(ring):
        # Every member has exactly two in-ring neighbours and the component is connected, so
        # the members form one cycle and there is always exactly one unvisited step. A bare
        # `next` rather than a decline: were that invariant ever to break, raising is the
        # honest answer, and a `return None` here would be an untestable branch pretending to
        # handle a case its caller has already ruled out.
        step = next(n for n in graph.neighbours(order[-1]) if n in members and n not in seen)
        seen.add(step)
        order.append(step)

    corners: list[tuple[float, float]] = []
    for at, node in enumerate(order):
        # Two planes both parallel to the run axis meet in one line parallel to it, so every
        # edge two consecutive walls share lies on that line and the whole junction is a single
        # point across the section -- however many segments the kernel split it into, and
        # without needing to check, because the wall filter above is what guarantees it. What
        # is *not* guaranteed is that the corners then form a polygon, and `_canonical` is
        # where that is decided.
        boxes = [
            edge.bounding_box()
            for edge in graph.shared_edges(node, order[(at + 1) % len(order)])
        ]
        across, along = (
            0.5
            * (
                min(getattr(box.min, "XYZ"[a]) for box in boxes)
                + max(getattr(box.max, "XYZ"[a]) for box in boxes)
            )
            for a in others
        )
        corners.append((across, along))
    return _canonical(corners)


def _canonical(corners: list[tuple[float, float]]) -> tuple[tuple[float, float], ...] | None:
    """One walk per shape, whatever order the kernel handed the faces over in.

    Anticlockwise from the lexicographically smallest corner. Without this the record would
    carry the traversal, and `tests/golden/traversal_order` exists because that is exactly the
    kind of thing that leaks into a record unnoticed.
    """

    count = len(corners)
    if len(set(corners)) != count:
        return None  # two walls meeting at one point is not a simple polygon
    twice_area = sum(
        corners[at][0] * corners[(at + 1) % count][1]
        - corners[(at + 1) % count][0] * corners[at][1]
        for at in range(count)
    )
    if abs(twice_area) <= _SPAN_EPS:
        return None  # degenerate: the corners are collinear
    if twice_area < 0:
        corners = corners[::-1]
    start = min(range(count), key=lambda at: corners[at])
    return tuple(corners[start:] + corners[:start])


def _centroid(section: tuple[tuple[float, float], ...]) -> tuple[float, float]:
    """The polygon's area centroid, which is what ``at`` means.

    Not the average of the wall-face centres the first draft used: that is the centroid of the
    *walls*, which for an irregular polygon is a different point, and one nothing downstream
    could reproduce from the record.
    """

    count = len(section)
    twice_area = 0.0
    across = 0.0
    along = 0.0
    for at in range(count):
        u0, v0 = section[at]
        u1, v1 = section[(at + 1) % count]
        cross = u0 * v1 - u1 * v0
        twice_area += cross
        across += (u0 + u1) * cross
        along += (v0 + v1) * cross
    return (across / (3 * twice_area), along / (3 * twice_area))


def _interior_point(section: tuple[tuple[float, float], ...]) -> tuple[float, float]:
    """A point proved to lie inside the cross-section, for the material probe.

    The centroid will not do. It is inside a convex polygon and can be outside a concave one, and
    an L-shaped or star-shaped passage is exactly the case where "is the material inside this
    ring" must still be answered correctly. Probing a point that is not in the cross-section can
    read an unrelated cavity, the material beside the void, or nothing at all.

    The construction is the standard one for a simple polygon: the lowest corner is convex, so
    the triangle it makes with its two neighbours lies wholly inside unless another corner
    intrudes into it, and that triangle's centroid is then interior. When one does intrude, the
    segment from the lowest corner to the intruder farthest from the chord is a diagonal, and
    its midpoint is interior.

    The centroid of the ear and not the midpoint of the chord: for a triangular passage the
    chord *is* the opposite edge, so its midpoint lies on the boundary and the classifier
    answers ``ON`` -- which is how this was caught, the three-sided fixture going missing.
    """

    count = len(section)
    at = min(range(count), key=lambda k: (section[k][1], section[k][0]))
    before, corner, after = section[at - 1], section[at], section[(at + 1) % count]
    intruders = [
        point
        for k, point in enumerate(section)
        if k not in {(at - 1) % count, at, (at + 1) % count}
        and _within(point, before, corner, after)
    ]
    if not intruders:
        return (
            (before[0] + corner[0] + after[0]) / 3,
            (before[1] + corner[1] + after[1]) / 3,
        )
    deepest = max(intruders, key=lambda point: abs(_turn(before, after, point)))
    return (0.5 * (corner[0] + deepest[0]), 0.5 * (corner[1] + deepest[1]))


def _turn(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _within(
    point: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> bool:
    """Is *point* inside or on triangle *a*, *b*, *c*?"""

    turns = (_turn(a, b, point), _turn(b, c, point), _turn(c, a, point))
    return all(turn >= 0 for turn in turns) or all(turn <= 0 for turn in turns)


def _is_void(
    part: Part, section: tuple[tuple[float, float], ...], axis: int, low: float, high: float
) -> bool:
    """Is the ring's interior empty, rather than a prism of material?

    Only ``OUT`` is a passage. The first draft rejected only ``IN``, which let ``ON`` and
    ``UNKNOWN`` through as though they were evidence of a void: ``ON`` says the probe landed on
    a face and ``UNKNOWN`` says the classifier could not decide, and neither is a reason to
    report a through feature. With a point proved interior, both mean something is wrong with
    the ring rather than with the probe, so they fail closed.
    """

    others = [a for a in (0, 1, 2) if a != axis]
    point = [0.0, 0.0, 0.0]
    point[axis] = 0.5 * (low + high)
    point[others[0]], point[others[1]] = _interior_point(section)
    probe = BRepClass3d_SolidClassifier(part.wrapped)
    probe.Perform(gp_Pnt(*point), _SPAN_EPS)
    return bool(probe.State() == TopAbs_OUT)


def _capped(
    graph: FaceGraph,
    ring: tuple[FaceNode, ...],
    members: set[FaceNode],
    axis: int,
    low: float,
    high: float,
) -> bool:
    """Does a face perpendicular to the run axis close either end of *ring*?

    Not merely "is there a perpendicular neighbour at the end" -- at a passage mouth the part's
    own outer face is perpendicular and edge-adjacent, and testing only for its presence
    rejects every passage there is. A floor *fills* the ring's cross-section; an end face
    extends past it, because the ring is a hole punched through that face.
    """

    others = [a for a in (0, 1, 2) if a != axis]
    ring_low = [min(graph.bounds(node)[a][0] for node in ring) for a in others]
    ring_high = [max(graph.bounds(node)[a][1] for node in ring) for a in others]
    for node in ring:
        for other in graph.neighbours(node):
            if other in members:
                continue
            # Any neighbour, not only a planar axis-aligned one. Requiring that let an
            # ordinary filleted or chamfered pocket floor read as a passage: breaking the
            # bottom edge replaces the flat floor's contact with a blend face, and the only
            # cap candidate disappeared. A blend at the bottom of a blind void still closes
            # it, so what matters is whether something sits across the end of the span
            # inside the ring, not what surface type it happens to be.
            # Every ring member's span *is* `low`..`high` -- that is what put them in one ring
            # -- and a neighbour shares an edge with one, so its own span always overlaps.
            # There is nothing to reject on that count, only on where within the span it sits.
            end = graph.bounds(other)
            near_low = abs(end[axis][0] - low) <= _SPAN_EPS or abs(end[axis][1] - low) <= _SPAN_EPS
            near_high = (
                abs(end[axis][0] - high) <= _SPAN_EPS or abs(end[axis][1] - high) <= _SPAN_EPS
            )
            if not (near_low or near_high):
                continue
            if all(
                end[a][0] >= ring_low[k] - _SPAN_EPS and end[a][1] <= ring_high[k] + _SPAN_EPS
                for k, a in enumerate(others)
            ):
                return True
    return False
