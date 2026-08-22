# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""Angled blind step recognition for prismatic parts.

An **angled blind step** is a wedge taken out of an edge of the part: one oblique planar
wall, stopping part-way along the edge, with a triangular flat closing the blind end. Milled
as an angled shoulder or a lead-in ramp, it is the feature MFCAD++ calls a *triangular blind
step*.

Geometrically it is the same read as a chamfer — an oblique planar face bridging two
mutually-perpendicular axis-aligned faces at a convex corner — and that is exactly why it
needs recognising. Before this module existed ``recognise_chamfers`` reported these slants
as chamfers, because nothing distinguished them. Measured over 60 MFCAD++ models, **9 of
the 10 models carrying one had their step's slant reported as their only chamfer**, while
the genuine chamfers on the same parts were rejected.

The distinction is **not** size. That was the tempting answer and it does not survive
measurement: the legs of the two populations overlap on every part-relative and
neighbour-relative ratio tried, and a threshold that separated them on one corpus would be
fitted to that corpus. The distinction is topological — **a chamfer runs the full length of
the edge it breaks; an angled step stops, and something has to close the end.** That
something is a triangular flat, and :func:`_closed_by_a_triangular_flat` is the whole
discriminator. It says nothing about the part around the face, so a step is a step at any
scale, which a size gate could never promise.

**That test is this family's own, and no longer shared.** It lived in ``_adjacency`` while
``recognise_chamfers`` consulted it too — to *decline* a bevel this family would claim — and the
comment on it said the two must agree or the feature would vanish from the census, claimed by
neither. Agreement by shared helper is a hand-rolled ownership device: it worked for two
contestants and generalised to no third. The chamfer family no longer asks the
question at all. It proposes every bevel it sees, this family claims the ones with a blind end,
and :func:`b123d_recognisers._reconcile.chamfers_that_are_not_angled_steps` reads the claims and
drops the duplicates — so there is exactly one implementation of the discriminator, owned by the
family it defines, and nothing left for a second copy to drift from.

Five gates, the first three shared with :func:`b123d_recognisers.recognise_chamfers` so the
two cannot disagree about what they are looking at:

- **an oblique bevel** — :func:`b123d_recognisers.classify_bevel`, so the slant is a planar
  face running along exactly one principal axis;
- **bridges two axis-aligned faces on distinct in-plane axes** — this is what excludes a
  *pocket* wall, and it does nearly all the work. A triangular pocket whose plan is not
  axis-aligned otherwise matches the signature exactly: its walls are oblique planes and its
  floor is a triangle. Prototyped without this gate, pockets outnumbered steps three to one
  (precision 21%); over 120 MFCAD++ models it stops all 109 of them, and the convex probe
  stops none;
- **convex** — :func:`b123d_recognisers.chamfers.convex_bevel`, and it carries real weight:
  of the 85 faces that reach it over 120 MFCAD++ models it rejects 24. What it catches is
  a slant with material *behind* it rather than below — a gusset filling a concave corner,
  whose hypotenuse bridges two perpendicular walls and whose ends are triangles, so it
  satisfies every other gate here and the material is the only thing that differs;
- **no material beyond the corner** — :func:`b123d_recognisers._bevel.material_beyond_corner`,
  which finishes the job the second gate was doing alone. That gate excludes a pocket wall by
  asking what the slant bridges, and a triangular pocket whose *other two* walls happen to be
  axis-aligned answers correctly and is a pocket anyway. The held-out corpus contained one and
  the design corpus did not, which is the whole argument for holding a corpus out. The corner
  a step replaces is a corner of the stock, with free space behind it; the corner a recess wall
  replaces is where two walls of that recess meet, with the material they were cut from behind
  it. Convexity cannot see the difference — both have vacuum on the bevel side;
- **a triangular companion** — the blind end.

No size gate and no fitted geometric fraction: every gate here is a shared geometric
classification, a solid-classifier probe or a statement about the end region's actual boundary.

**The old edge count cost recall.** A blind end whose triangle was subdivided read as four or
five edges and the step disappeared. Across 120 MFCAD++ models carrying the feature, historical
instance recall was 70% (114 of 163), and 24 of the 49 misses had no bare triangular face
anywhere on them. That measurement predates both the outer-wire fix and the normalized-region
read here, and was taken over a set larger than the one vendored here, so it remains historical
evidence rather than being restated as a new score.

Relaxing the count is not the fix: a chamfer strip's rectangular end cap also has four edges.
The family now asks the gAAG for the smooth-connected patches on the terminal plane, cancels
their internal subdivision edges, ignores inner loops, and reduces consecutive collinear outer
edges to straight runs. Exactly three runs is geometric triangularity. It recovers both a bolt
hole through the interior and harmless face/edge subdivision while still rejecting a rectangle,
a curved bite or a genuinely notched side. The only numerical allowances are the shared kernel
coordinate floor for sewing coincident boundary edges and the measured dimensionless smooth/
collinear direction tolerance; neither admits an almost-triangle by size.

Depends on ``chamfers`` for the bevel read and the convexity probe rather than copying
either, so a change to what counts as a bevel reaches both recognisers at once.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from build123d import Face, GeomType, Wire

from b123d_recognisers._adjacency import (
    FaceEdges,
    FaceGraph,
    FaceNode,
    axis_aligned_axis,
    edge_face_map,
    nearest_axis_aligned_planes,
)
from b123d_recognisers._bevel import (
    BevelReject,
    classify_bevel,
    convex_bevel,
    material_beyond_corner,
)
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._geometry import COORD_FLOOR, SMOOTH_ARC_GAP
from b123d_recognisers._record import Record
from b123d_recognisers._typing import EdgeLike, FaceLike, Part


@dataclass(frozen=True, order=True)
class AngledStep(Record):
    """A recognised angled blind step. ``axis`` is the direction the slant runs along
    ("x"/"y"/"z"); ``leg1``/``leg2`` are the cut depths into the two adjacent faces
    (``leg1`` the larger); ``angle`` is the slant angle in degrees (45 for equal-leg);
    ``length`` is how far the step runs before its blind end; ``at`` is the slant face
    centre in part space (the callout leader's tip).

    The fields mirror :class:`b123d_recognisers.Chamfer` because the geometry is the same
    read — ``length`` is the addition, and it is the field a chamfer has no use for: a
    chamfer runs the whole edge, so its length is not a chosen dimension.
    """

    axis: str
    leg1: float
    leg2: float
    angle: float
    length: float
    at: tuple[float, float, float]


def _same_axis_plane(graph: FaceGraph, node: FaceNode, plane: tuple[int, float]) -> bool:
    """Whether *node* is a planar patch on the same principal plane as *plane*."""

    aligned = axis_aligned_axis(graph.face(node).wrapped)
    return (
        aligned is not None
        and aligned[0] == plane[0]
        and math.isclose(aligned[1], plane[1], rel_tol=0.0, abs_tol=COORD_FLOOR)
    )


def _coplanar_region(graph: FaceGraph, seed: FaceNode) -> frozenset[FaceNode]:
    """The seed's smooth-connected planar patches, without crossing a curved blend.

    A tangent fillet can put two planes in one maximal smooth component, so this family asks
    the narrower gAAG question directly: traverse only smooth arcs between patches on the
    seed's own plane.  That both prevents a fillet escape and avoids classifying unrelated
    curved arcs around a large stock face.
    """

    plane = axis_aligned_axis(graph.face(seed).wrapped)
    if plane is None:
        return frozenset()
    found = {seed}
    pending = [seed]
    while pending:
        current = pending.pop()
        for other in graph.neighbours(current):
            if (
                other in found
                or not _same_axis_plane(graph, other, plane)
                or graph.arc(current, other) != "smooth"
            ):
                continue
            found.add(other)
            pending.append(other)
    return frozenset(found)


def _region_boundary(graph: FaceGraph, region: frozenset[FaceNode]) -> list[EdgeLike]:
    """Edges on the boundary of *region*, cancelling its internal subdivision edges."""

    uses: dict[EdgeLike, int] = {}
    for node in region:
        for edge in graph.edges(node):
            uses[edge] = uses.get(edge, 0) + 1
    if any(count > 2 for count in uses.values()):
        return []  # non-manifold evidence: no unambiguous planar-region boundary
    return [edge for edge, count in uses.items() if count == 1]


def _three_straight_runs(wire: Wire) -> bool:
    """Whether the actual loop, without a convex-hull approximation, is a triangle."""

    edges = list(wire.edges())
    if len(edges) < 3 or any(edge.geom_type != GeomType.LINE for edge in edges):
        return False
    directions = [edge.tangent_at() for edge in edges]
    turns = sum(
        1
        for before, after in zip(directions, directions[1:] + directions[:1], strict=True)
        if 1.0 - before.dot(after) > SMOOTH_ARC_GAP
    )
    return turns == 3


def _face_exterior_is_geometrically_triangular(face: FaceLike) -> bool:
    """The common one-face case, without paying for a regional boundary reconstruction."""

    if not face.is_valid:
        return False
    try:
        exterior = face.outer_wire()
    except Exception:  # malformed source topology is unsupported evidence
        return False
    return exterior.is_closed and _three_straight_runs(exterior)


def _region_is_geometrically_triangular(
    graph: FaceGraph, region: frozenset[FaceNode]
) -> bool:
    """Whether one coplanar region has a triangular exterior boundary.

    Internal subdivision edges are cancelled and inner loops are ignored, preserving a
    triangle drilled through its interior.  Curved, open, branched or otherwise ambiguous
    boundaries fail closed.  The largest closed planar loop is necessarily the exterior;
    every hole it contains has smaller area.
    """

    if not region or any(not graph.face(node).is_valid for node in region):
        return False
    boundary = _region_boundary(graph, region)
    if not boundary:
        return False
    wires = list(Wire.combine(boundary, tol=COORD_FLOOR))
    if not wires or any(not wire.is_closed for wire in wires):
        return False
    try:
        faces = [(wire, Face(wire)) for wire in wires]
    except Exception:  # a non-simple or non-planar boundary is unsupported evidence
        return False
    if any(not face.is_valid for _wire, face in faces):
        return False
    exterior = max(faces, key=lambda pair: pair[1].area)[0]
    return _three_straight_runs(exterior)


def _geometrically_triangular_region(graph: FaceGraph, seed: FaceNode) -> bool:
    """Whether the seed's coplanar smooth region is geometrically triangular."""

    return _region_is_geometrically_triangular(graph, _coplanar_region(graph, seed))


def _closed_by_a_triangular_flat(face: FaceLike, edge_axis: int, graph: FaceGraph) -> bool:
    """Is *face* adjacent to a geometrically triangular planar terminal region?

    The blind end, and the whole discriminator (see the module docstring). A chamfer strip runs
    the length of the edge it breaks, so its neighbours are the two walls it bridges; a slant
    that stops part-way into the part needs a flat to close it, and that flat is a triangle.

    The terminal may be split into coplanar faces or have collinear vertices inserted along a
    side.  Those are representation changes, so the gAAG region is reduced to its actual outer
    boundary and consecutive collinear edges count as one straight run.  A notch, curved bite
    or four-sided end remains different geometry and is rejected.

    Private, and that is the point. It was ``_adjacency``'s shared
    ``has_triangular_companion`` while ``recognise_chamfers`` consulted it as well; it consults
    nothing now, so the one caller keeps it.
    """

    slant = graph.require_node(face)
    regions: set[frozenset[FaceNode]] = set()
    for other in graph.neighbours(slant):
        terminal = graph.face(other)
        aligned = axis_aligned_axis(terminal.wrapped)
        if aligned is None or aligned[0] != edge_axis:
            continue
        region = _coplanar_region(graph, other)
        if len(region) == 1:
            if _face_exterior_is_geometrically_triangular(terminal):
                return True
        else:
            regions.add(region)
    return any(_region_is_geometrically_triangular(graph, region) for region in regions)


def recognise_angled_steps(
    part: Part,
    *,
    face_edges: FaceEdges | None = None,
    ledger: ClaimLedger | None = None,
) -> list[AngledStep]:
    """Recognise the angled blind steps of *part* (see module docstring). Returns one
    :class:`AngledStep` per qualifying slant face, sorted deterministically. Empty when the
    part has none. Only single-axis slants (running along one principal axis) are recovered;
    a step whose blind end is closed by anything other than a triangular flat is not one —
    that end is what makes the feature blind, and without it the slant is a chamfer or a
    through step.

    *ledger* records the face a step was **established by**: its slant, and only that. Every
    number on the record is read off that one face — both legs from its in-plane extents,
    ``length`` from its span along the edge, ``at`` from its centre. The triangular flat that
    closes the blind end is *consulted*, not consumed, for the same reason a groove does not
    claim the shaft either side of it: it belongs to whatever feature owns it, and claiming it
    would have every step contest its own end cap.

    ``recognise_chamfers`` reads the same slant as a bevel and proposes it too, because on the
    face alone it is one. Which of the two survives is
    :func:`b123d_recognisers._reconcile.chamfers_that_are_not_angled_steps`, decided from these
    claims rather than by each family second-guessing the other."""

    all_faces = list(part.faces())
    memo = face_edges if face_edges is not None else FaceEdges()
    graph = ledger.graph if ledger is not None else FaceGraph(part, face_edges=memo)
    edge_faces = edge_face_map(all_faces, face_edges=memo)

    out: list[tuple[AngledStep, FaceLike]] = []
    for f in all_faces:
        try:
            edge_i, _nv, span, leg_hi, leg_lo = classify_bevel(f)
        except BevelReject:
            continue
        oi = [j for j in (0, 1, 2) if j != edge_i]
        fc = {i: 0.5 * (span[i][0] + span[i][1]) for i in (0, 1, 2)}  # face centre
        neigh_coord = nearest_axis_aligned_planes(
            f, edge_faces, fc, exclude_axis=edge_i, face_edges=memo
        )
        if oi[0] not in neigh_coord or oi[1] not in neigh_coord:
            continue
        if not convex_bevel(part, fc, edge_i, neigh_coord):
            continue  # concave — a pocket or passage wall, not a step
        if material_beyond_corner(part, fc, edge_i, neigh_coord):
            continue  # the corner two recess walls meet at, not a corner of the part
        # Last, though it is the gate this family is named for — the three above it are the
        # shared bevel read, and this is the one thing that is only about a step. Keep the local
        # gAAG traversal after the cheap classification and material-side gates: most oblique
        # faces are not candidates, so their surrounding smooth regions need never be built.
        if not _closed_by_a_triangular_flat(f, edge_i, graph):
            continue  # runs edge to edge — a chamfer, and the reconciler leaves it to them
        fctr = f.center()
        out.append(
            (
                AngledStep(
                    axis="xyz"[edge_i],
                    leg1=round(leg_hi, 3),
                    leg2=round(leg_lo, 3),
                    angle=round(math.degrees(math.atan2(leg_lo, leg_hi)), 2),
                    length=round(span[edge_i][1] - span[edge_i][0], 3),
                    at=(round(fctr.X, 3), round(fctr.Y, 3), round(fctr.Z, 3)),
                ),
                f,
            )
        )
    out.sort(key=lambda pair: (pair[0].axis, pair[0].at))
    if ledger is not None:
        for step, face in out:
            ledger.add_defining(step, [ledger.graph.require_node(face)])
    return [step for step, _ in out]
