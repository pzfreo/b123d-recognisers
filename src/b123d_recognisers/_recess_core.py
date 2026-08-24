# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""What a slot, a pocket and a channel each are, given the faces and the reductions.

The three families' own logic, and the top of the recess stack. Each `_recognise_*_one`
function is one solid's worth of one family: read the faces
(:mod:`b123d_recognisers._recess_faces`), propose candidates from wall pairs, recover the ones
whose walls do not pair (:mod:`b123d_recognisers._recess_obround`), and reduce what is left to
features (:mod:`b123d_recognisers._recess_reduce`). :mod:`b123d_recognisers._recess_features`
wraps them in the public recognisers.

The candidate predicates are here rather than below because they are where the three families
actually differ. `_candidate` is a through-void between two walls; `_floored_candidate` is the
same read with a floor found, which is what makes a pocket a pocket and a channel a channel;
`_recognise_corner_notches` is the case none of them covers, a void open on two adjacent sides
with only one wall to find it by.

This module was 1,200 lines carrying all four responsibilities. The split is by responsibility
rather than by family, because the families share almost everything below the predicates and
share nothing above them.
"""

from __future__ import annotations

from dataclasses import dataclass

from b123d_recognisers._adjacency import (
    FaceEdges,
    FaceGraph,
    FaceNode,
    is_opposed_nonsmooth,
    same_arc_kind,
)
from b123d_recognisers._geometry import COORD_FLOOR
from b123d_recognisers._recess_faces import (
    _AXES,
    _FLOOR_TOL,
    _MERGE_TOL,
    _center,
    _end_capped,
    _Face,
    _has_floor,
    _overlap_len,
    _planar_faces,
)
from b123d_recognisers._recess_obround import (
    _extend_obround_ends,
    _recognise_obround_from_ends,
)
from b123d_recognisers._recess_records import Channel, Pocket, Slot
from b123d_recognisers._recess_reduce import (
    _Claims,
    _collapse_collinear,
    _merge,
    _prism_is_empty,
)
from b123d_recognisers._typing import Part

_LENGTH_TIE_FRAC = 0.05

_SLOT_MAX_SPAN_FRAC = 0.9


def _concave_boundary_regions(wall: FaceNode, graph: FaceGraph) -> set[frozenset[FaceNode]]:
    """Distinct closing regions reached concavely from one proposed wall.

    One physical end or floor may arrive from STEP as several tangent face patches. A gAAG
    collapses those patches into one region; :meth:`FaceGraph.smooth_region` asks the same
    question without mutating this graph. Convex arcs are excluded because they lead onto outer
    stock or added material, neither of which closes the removed region.
    """

    return {
        graph.smooth_region(node)
        for node in graph.neighbours(wall)
        if graph.arc(wall, node) == "concave"
    }


def _shared_concave_boundaries(fa: _Face, fb: _Face, graph: FaceGraph) -> set[frozenset[FaceNode]]:
    if fa.node is None or fb.node is None:
        raise ValueError("recess walls require graph nodes")
    return _concave_boundary_regions(fa.node, graph) & _concave_boundary_regions(fb.node, graph)


def _uninterrupted_long_span(
    long_axis: str,
    long_span: tuple[float, float],
    fa: _Face,
    fb: _Face,
    graph: FaceGraph,
) -> tuple[float, float] | None:
    """The record span after graph-proved curved interruptions at its ends.

    A coaxial post can replace a slot's planar end entirely. It is common to both walls, curved,
    and the material turns oppositely at its two contacts; that is explicit AAG evidence of added
    material interrupting the end rather than of the void ending there. Remove exactly its
    bounding interval from the occupancy probe. Interior material is not trimmed: the simple
    rectangular record has no way to represent it.
    """

    if fa.node is None or fb.node is None:
        raise ValueError("recess walls require graph nodes")
    lo, hi = long_span
    common = set(graph.neighbours(fa.node)) & set(graph.neighbours(fb.node))
    for node in common:
        if graph.is_planar(node):
            continue
        if is_opposed_nonsmooth(graph.arc(fa.node, node), graph.arc(fb.node, node)):
            bounds = graph.bounds(node)[_AXES[long_axis]]
            if bounds[0] <= lo + COORD_FLOOR:
                lo = max(lo, bounds[1])
            if bounds[1] >= hi - COORD_FLOOR:
                hi = min(hi, bounds[0])
    return (lo, hi) if hi - lo > COORD_FLOOR else None


def _candidate_has_void_evidence(
    spans: dict[str, tuple[float, float]],
    long_axis: str,
    fa: _Face,
    fb: _Face,
    graph: FaceGraph,
    part: Part,
) -> bool:
    """Whether the record's uninterrupted, unrounded rectangular prism is empty.

    A complete outer AAG boundary still does not prove this record: a ring-shaped removal around
    a large rectangular island has two shared concave ends but is not a simple rectangular slot.
    The graph instead proves only which curved end interruptions are added material that may be
    trimmed from the claimed run. Everything left in the record's prism must be void.

    Candidate existence has no volume allowance: even a thin continuous membrane keeps two
    recesses distinct. ``COORD_FLOOR`` is only a kernel-coordinate inset which avoids asking an
    OCCT Boolean about coincident boundary faces; any barrier thicker than twice that supported
    numerical floor remains inside the probe. The separate collinear-arm policy deliberately has
    a much larger allowance and does not leak into this decision.
    """
    long_span = _uninterrupted_long_span(long_axis, spans[long_axis], fa, fb, graph)
    if long_span is None:
        return False
    probe = dict(spans)
    probe[long_axis] = long_span
    return _prism_is_empty(probe, part, inset=COORD_FLOOR)


def _bounds_one_void(fa: _Face, fb: _Face, graph: FaceGraph) -> bool:
    """Whether two opposed walls participate in one coherent recess boundary.

    Facing bounding boxes are not enough: walls of neighbouring features can overlap by a
    sliver and manufacture a candidate spanning the space between them. Two separate slots cut
    into the same plate make the stronger counterexample: their outer walls share the plate's
    top and bottom with matching *convex* arcs, but no concave boundary region joins them across
    the solid rib.

    Where the walls share a boundary face, both arcs must agree. Planar common neighbours are
    preferred because an added coaxial post contributes a cylindrical neighbour with opposite
    turns but interrupts rather than defines the slot. Agreement is only a prerequisite: after
    the candidate has exact bounds, :func:`_candidate_has_void_evidence` additionally requires
    an empty uninterrupted prism.
    """

    if fa.node is None or fb.node is None:
        raise ValueError("recess walls require graph nodes")
    common = set(graph.neighbours(fa.node)) & set(graph.neighbours(fb.node))
    if common:
        # Prefer the planar boundary shared by these planar walls. A convex cylindrical post at
        # a slot end is also adjacent to both walls, with one convex and one concave arc, but is
        # added material inside the boundary rather than evidence that the walls bound different
        # voids. Keep curved neighbours as the fallback for boundaries with no planar member.
        boundary = {neighbour for neighbour in common if graph.is_planar(neighbour)} or common
        return all(
            same_arc_kind(graph.arc(fa.node, neighbour), graph.arc(fb.node, neighbour))
            for neighbour in boundary
        )

    # With no common neighbour, a fragmented boundary must still join the walls through one
    # concave region or the wall faces themselves must be smooth subdivisions of one region.
    if _shared_concave_boundaries(fa, fb, graph):
        return True
    return fb.node in graph.smooth_region(fa.node)


def _candidate(
    fa: _Face,
    fb: _Face,
    part: Part,
    part_ext: dict[str, float],
    axis: str,
    graph: FaceGraph,
) -> Slot | None:
    """Build a :class:`Slot` from two facing rectangular walls, or None if the
    pair is not a slot (not facing, not overlapping, wider than long, or
    spanning the full part).  Geometry only — the through/blind test is applied
    by the caller, which needs the whole face set."""
    # *axis* is the bucket both walls came from, passed rather than re-read off `fa`: it is
    # established once where the oblique walls are declined, so nothing downstream needs a
    # branch for a wall that cannot reach here.
    k = _AXES[axis]
    bb_a, bb_b = fa.bb, fb.bb
    # Anti-parallel outward normals.
    if fa.normal[k] * fb.normal[k] >= 0:
        return None
    c_a, c_b = _center(bb_a, k), _center(bb_b, k)
    # Facing each other: A's outward normal points towards B.  Outer faces of
    # the stock fail this (their normals point apart).
    if (c_b - c_a) * fa.normal[k] <= 0:
        return None
    if not _bounds_one_void(fa, fb, graph):
        return None
    # The walls must genuinely overlap in both perpendicular axes, otherwise
    # they are unrelated faces that merely happen to be parallel and facing.
    others = [a for a in "xyz" if a != axis]
    ov = [_overlap_len(bb_a, bb_b, a) for a in others]
    if min(ov) <= 0:
        return None
    width = abs(c_b - c_a)
    # The longer shared extent is the slot length; the shorter is depth.  When
    # the two are near-equal (a near-square slot) the choice is ambiguous, so
    # break the tie towards the part's longer axis — a slot on a bar runs along
    # the bar.
    (ax0, ov0), (ax1, ov1) = sorted(zip(others, ov, strict=False), key=lambda t: t[1], reverse=True)
    if (ov0 - ov1) <= _LENGTH_TIE_FRAC * ov0 and part_ext[ax1] > part_ext[ax0]:
        (long_axis, length), depth_axis = (ax1, ov1), ax0
    else:
        (long_axis, length), depth_axis = (ax0, ov0), ax1
    # A slot is elongated: its width (the wall separation) is not its largest
    # dimension.  A wider-than-long pair is a step/pocket or a sliver of two
    # incidental parallel faces.
    if width > length:
        return None
    # Reject open / full-span features along the length (see _SLOT_MAX_SPAN_FRAC).
    if length >= _SLOT_MAX_SPAN_FRAC * part_ext[long_axis]:
        return None
    lc = "XYZ"[_AXES[long_axis]]
    lo = max(getattr(bb_a.min, lc), getattr(bb_b.min, lc))
    hi = min(getattr(bb_a.max, lc), getattr(bb_b.max, lc))
    dc = "XYZ"[_AXES[depth_axis]]
    d_lo = max(getattr(bb_a.min, dc), getattr(bb_b.min, dc))
    d_hi = min(getattr(bb_a.max, dc), getattr(bb_b.max, dc))
    spans = {
        axis: tuple(sorted((c_a, c_b))),
        long_axis: (lo, hi),
        depth_axis: (d_lo, d_hi),
    }
    if not _candidate_has_void_evidence(spans, long_axis, fa, fb, graph, part):
        return None
    return Slot(
        width_axis=axis,
        long_axis=long_axis,
        width=round(width, 2),
        length=round(hi - lo, 2),
        w_center=round((c_a + c_b) / 2, 2),
        lo=round(lo, 2),
        hi=round(hi, 2),
        d_lo=round(d_lo, 2),
        d_hi=round(d_hi, 2),
    )


def _recognise_slots_one(
    part: Part,
    face_edges: FaceEdges | None = None,
    graph: FaceGraph | None = None,
    claims: _Claims | None = None,
) -> list[Slot]:
    """Recognise slots using one solid's faces and bounds.

    *graph* and *claims* travel together: without the graph no face resolves to a node, so a
    caller passing only *claims* would silently claim nothing. Nothing enforces that here
    because the family's own claim tests do -- they assert the walls a slot names, which an
    unpaired call cannot produce.
    """

    owner = FaceGraph(part, face_edges=face_edges) if graph is None else graph
    faces = _planar_faces(part, face_edges, owner)
    pbb = part.bounding_box()
    part_ext = {a: getattr(pbb.size, "XYZ"[_AXES[a]]) for a in "xyz"}
    # Only straight-walled faces can be slot walls; bucket them by axis so the
    # O(n^2) pairing runs within each axis instead of across all planar faces.
    by_axis: dict[str, list[_Face]] = {}
    for f in faces:
        # An oblique wall is declined here, by this family, rather than filtered out of the
        # shared reduction on three families' behalf (ADR 0009). This recogniser pairs walls
        # that share a normal axis, so a wall with no axis has nothing here to pair with --
        # that is a real limit of the pairing strategy and it is now visible as one.
        if f.wall and f.axis is not None:
            by_axis.setdefault(f.axis, []).append(f)
    candidates: list[Slot] = []
    for axis, walls in by_axis.items():
        for i in range(len(walls)):
            for j in range(i + 1, len(walls)):
                s = _candidate(walls[i], walls[j], part, part_ext, axis, owner)
                # Keep only through-slots: a blind pocket (or the floored gap
                # between bosses) is capped by a floor and is out of scope.
                if s is not None and not _has_floor(faces, s):
                    candidates.append(s)
                    # The two walls are what established this slot. Nothing else here is
                    # defining: the floor test consults other faces without being bounded by
                    # them, and treating consultation as consumption would have this slot
                    # contest every feature it merely looked at.
                    if claims is not None:
                        # `is not None` narrows the field's type; it is not tolerance. With a
                        # graph every face resolves or `_planar_faces` has already raised.
                        claims.setdefault(s, set()).update(
                            node for node in (walls[i].node, walls[j].node) if node is not None
                        )
    # Stubby obround through-slots (straight section < width) have no pairable flat walls, so
    # recover them from their end caps. Emitted at the straight-wall junctions like the
    # flat-wall path, so `_merge` folds any duplicate an elongated obround also produced.
    candidates.extend(_recognise_obround_from_ends(part, faces))
    # Recombine arms of a crossing channel split by the intersection, then extend any
    # radiused-end (obround) slot to its overall length.
    return _extend_obround_ends(
        _collapse_collinear(_merge(candidates, claims), part, claims), part, claims
    )


def _floored_candidate(
    fa,
    fb,
    part,
    faces,
    part_ext,
    axis: str,
    graph: FaceGraph,
    *,
    channel_bounds: dict[str, tuple[float, float]] | None = None,
) -> Pocket | Channel | None:
    """Build a floored opposed-wall recess, with open-vs-enclosed semantics explicit.

    ``channel_bounds=None`` asks for an enclosed :class:`Pocket` and preserves the
    historical full-span rejection.  Bounds ask for a :class:`Channel`: its shared
    longitudinal wall range must meet both envelope ends, proving the feature is open
    there rather than merely a large pocket.

    Unlike :func:`_candidate` (which splits the two non-width axes into long/depth by
    *size*), the depth axis is read from the geometry: it is capped on exactly one end
    (the floor) and open on the other.  This keeps a recess deeper than it is long from
    having its floor mistaken for an end wall.
    """
    k = _AXES[axis]  # *axis* is the width axis: the bucket both walls came from
    if fa.normal[k] * fb.normal[k] >= 0:
        return None  # not anti-parallel — not a facing pair
    c_a, c_b = _center(fa.bb, k), _center(fb.bb, k)
    if (c_b - c_a) * fa.normal[k] <= 0:
        return None  # normals face away from each other (outer faces), not a cavity
    if not _bounds_one_void(fa, fb, graph):
        return None
    width = abs(c_b - c_a)
    others = [a for a in "xyz" if a != axis]
    ranges = {}  # per non-width axis: (lo, hi) overlap of the two walls
    for a in others:
        c = "XYZ"[_AXES[a]]
        lo = max(getattr(fa.bb.min, c), getattr(fb.bb.min, c))
        hi = min(getattr(fa.bb.max, c), getattr(fb.bb.max, c))
        if hi - lo <= 0:
            return None  # walls do not overlap on this axis — not a slot
        ranges[a] = (lo, hi)
    w_range = (c_a + c_b) / 2 - width / 2, (c_a + c_b) / 2 + width / 2
    # The depth axis is the non-width axis capped on exactly one end (floor + opening).
    for depth_axis in others:
        (long_axis,) = [a for a in others if a != depth_axis]
        d_lo, d_hi = ranges[depth_axis]
        l_lo, l_hi = ranges[long_axis]
        foot = {axis: w_range, long_axis: (l_lo, l_hi)}
        foot_area = width * (l_hi - l_lo)
        cap_lo = _end_capped(faces, foot, foot_area, depth_axis, d_lo, 1.0)
        cap_hi = _end_capped(faces, foot, foot_area, depth_axis, d_hi, -1.0)
        if int(cap_lo) + int(cap_hi) != 1:
            continue  # 0 = through on this axis; 2 = an enclosed end-cap pair, not a floor
        length = l_hi - l_lo
        if width > length and channel_bounds is None:
            return None  # width is the smaller footprint dim (the wrong wall pair)
        if channel_bounds is None:
            if length >= _SLOT_MAX_SPAN_FRAC * part_ext[long_axis]:
                return None  # footprint spans the part — an open feature, not a pocket
            spans = {
                axis: tuple(sorted((c_a, c_b))),
                long_axis: (l_lo, l_hi),
                depth_axis: (d_lo, d_hi),
            }
            if not _candidate_has_void_evidence(spans, long_axis, fa, fb, graph, part):
                return None
            return Pocket(
                width_axis=axis,
                long_axis=long_axis,
                width=round(width, 2),
                length=round(length, 2),
                depth=round(d_hi - d_lo, 2),
                w_center=round((c_a + c_b) / 2, 2),
                lo=round(l_lo, 2),
                hi=round(l_hi, 2),
                d_lo=round(d_lo, 2),
                d_hi=round(d_hi, 2),
                open_sign=1 if cap_lo else -1,
            )
        part_lo, part_hi = channel_bounds[long_axis]
        if abs(l_lo - part_lo) > _FLOOR_TOL or abs(l_hi - part_hi) > _FLOOR_TOL:
            continue  # not open at both longitudinal envelope ends
        spans = {axis: tuple(sorted((c_a, c_b))), long_axis: (l_lo, l_hi), depth_axis: (d_lo, d_hi)}
        if not _candidate_has_void_evidence(spans, long_axis, fa, fb, graph, part):
            return None
        return Channel(
            width_axis=axis,
            long_axis=long_axis,
            width=round(width, 2),
            w_center=round((c_a + c_b) / 2, 2),
            lo=round(l_lo, 2),
            hi=round(l_hi, 2),
            d_lo=round(d_lo, 2),
            d_hi=round(d_hi, 2),
            open_sign=1 if cap_lo else -1,
        )
    return None


def _pocket_candidate(
    fa: _Face,
    fb: _Face,
    part: Part,
    faces: list[_Face],
    part_ext: dict[str, float],
    axis: str,
    graph: FaceGraph,
) -> Pocket | None:
    candidate = _floored_candidate(fa, fb, part, faces, part_ext, axis, graph)
    return candidate if isinstance(candidate, Pocket) else None


def _channel_candidate(
    fa: _Face,
    fb: _Face,
    part: Part,
    faces: list[_Face],
    part_ext: dict[str, float],
    part_bounds,
    axis: str,
    graph: FaceGraph,
) -> Channel | None:
    candidate = _floored_candidate(
        fa, fb, part, faces, part_ext, axis, graph, channel_bounds=part_bounds
    )
    return candidate if isinstance(candidate, Channel) else None


def _channel_sort_key(channel: Channel) -> tuple:
    """Geometry-only order, including depth to break cross-solid traversal ties."""
    return (
        channel.long_axis,
        channel.width_axis,
        channel.lo,
        channel.hi,
        channel.w_center,
        channel.width,
        channel.d_lo,
        channel.d_hi,
        channel.open_sign,
    )


@dataclass(frozen=True, slots=True)
class _ChannelProposal:
    """One exact Channel occurrence and its ordered original side walls."""

    record: Channel
    low_wall: FaceNode
    high_wall: FaceNode


def _recognise_pockets_one(
    part: Part,
    face_edges: FaceEdges | None = None,
    graph: FaceGraph | None = None,
    claims: _Claims | None = None,
) -> list[Pocket]:
    """Recognise pockets using one solid's faces and bounds.

    *graph* and *claims* travel together exactly as they do in
    :func:`_recognise_slots_one`, and the two paths below claim differently on purpose:

    - **From opposed walls**, the two walls are defining and the floor is not. The floor
      reaches this candidate through :func:`_end_capped`, which asks whether *something* caps
      the footprint; the pocket's own depth is the walls' overlap on the depth axis, not the
      floor's position. Same line the through-slot draws, for the same reason: consultation is
      not consumption, and claiming it would have every pocket contest whatever owns its floor.
    - **From a corner notch**, the floor *is* defining. That path iterates floors and reads the
      notch's whole footprint off the one it finds, so the floor established the record as
      literally as the two walls did.
    """

    owner = FaceGraph(part, face_edges=face_edges) if graph is None else graph
    faces = _planar_faces(part, face_edges, owner)
    pbb = part.bounding_box()
    part_ext = {a: getattr(pbb.size, "XYZ"[_AXES[a]]) for a in "xyz"}
    by_axis: dict[str, list[_Face]] = {}
    for f in faces:
        if f.wall and f.axis is not None:
            by_axis.setdefault(f.axis, []).append(f)  # oblique declined here -- see slots
    candidates: list[Pocket] = []
    for axis, walls in by_axis.items():
        for i in range(len(walls)):
            for j in range(i + 1, len(walls)):
                p = _pocket_candidate(walls[i], walls[j], part, faces, part_ext, axis, owner)
                if p is not None:
                    candidates.append(p)
                    if claims is not None:
                        claims.setdefault(p, set()).update(
                            node for node in (walls[i].node, walls[j].node) if node is not None
                        )
    candidates.extend(_recognise_corner_notches(faces, pbb, claims))
    # Stubby blind obround pockets (straight section < width) have no pairable flat walls, so
    # recover them from their end caps — the blind counterpart of the through-slot path, and
    # claiming nothing for the same reason: its evidence is two cylindrical caps, which
    # `_planar_faces` never yielded and which no consumer reconciling planar walls can want.
    candidates.extend(_recognise_obround_from_ends(part, faces, blind=True))
    return _extend_obround_ends(_merge(candidates, claims), part, claims)


def _recognise_channels_one(
    part: Part, face_edges: FaceEdges | None = None, graph: FaceGraph | None = None
) -> list[Channel]:
    """Recognise channels using one solid's faces and bounds."""
    return sorted(
        {proposal.record for proposal in _channel_proposals_one(part, face_edges, graph)},
        key=_channel_sort_key,
    )


def _channel_proposals_one(
    part: Part, face_edges: FaceEdges | None = None, graph: FaceGraph | None = None
) -> list[_ChannelProposal]:
    """Discover one solid's Channels while retaining exact ordered wall identity."""

    owner = FaceGraph(part, face_edges=face_edges) if graph is None else graph
    faces = _planar_faces(part, face_edges, owner)
    pbb = part.bounding_box()
    part_ext = {a: getattr(pbb.size, "XYZ"[_AXES[a]]) for a in "xyz"}
    part_bounds = {
        a: (
            getattr(pbb.min, "XYZ"[_AXES[a]]),
            getattr(pbb.max, "XYZ"[_AXES[a]]),
        )
        for a in "xyz"
    }
    by_axis: dict[str, list[_Face]] = {}
    for face in faces:
        if face.wall and face.axis is not None:
            by_axis.setdefault(face.axis, []).append(face)  # oblique declined here -- see slots
    proposals: list[_ChannelProposal] = []
    for axis, walls in by_axis.items():
        for i in range(len(walls)):
            for j in range(i + 1, len(walls)):
                channel = _channel_candidate(
                    walls[i], walls[j], part, faces, part_ext, part_bounds, axis, owner
                )
                if channel is not None:
                    first, second = walls[i], walls[j]
                    if first.node is None or second.node is None:
                        raise ValueError("Channel walls require graph nodes")
                    first_node, second_node = first.node, second.node
                    k = _AXES[axis]
                    low_node, high_node = (
                        (first_node, second_node)
                        if _center(first.bb, k) <= _center(second.bb, k)
                        else (second_node, first_node)
                    )
                    proposals.append(_ChannelProposal(channel, low_node, high_node))
    return proposals


def _recognise_corner_notches(
    faces: list[_Face], pbb, claims: _Claims | None = None
) -> list[Pocket]:
    """Recognise an axis-aligned rectangular blind interruption open at two
    adjacent envelope edges.

    A conventional pocket has opposed wall pairs.  A corner notch deliberately
    has only one X wall and one Y wall, so the pair-based pocket recogniser
    cannot see it.  Its three interior faces still form an unambiguous box:
    an X wall, a Y wall, and a horizontal floor.  Reuse ``Pocket`` as the
    rectangular-recess record so the existing W×L×D callout/coverage pipeline
    owns the dimensions; edge contact makes its X/Y location implicit.
    """
    tol = _MERGE_TOL

    def limits(bb, axis) -> tuple[float, float]:
        c = "XYZ"[_AXES[axis]]
        return getattr(bb.min, c), getattr(bb.max, c)

    out: list[Pocket] = []
    bx = (pbb.min.X, pbb.max.X)
    by = (pbb.min.Y, pbb.max.Y)
    bz = (pbb.min.Z, pbb.max.Z)
    for floor in (f for f in faces if f.axis == "z" and f.wall):
        x0, x1 = limits(floor.bb, "x")
        y0, y1 = limits(floor.bb, "y")
        z0, z1 = limits(floor.bb, "z")
        if x1 - x0 <= tol or y1 - y0 <= tol or abs(z1 - z0) > tol:
            continue
        if (x1 - x0) >= _SLOT_MAX_SPAN_FRAC * (bx[1] - bx[0]) or (
            y1 - y0
        ) >= _SLOT_MAX_SPAN_FRAC * (by[1] - by[0]):
            continue  # a full-span step floor, not a bounded interruption
        x_edge = abs(x0 - bx[0]) <= tol or abs(x1 - bx[1]) <= tol
        y_edge = abs(y0 - by[0]) <= tol or abs(y1 - by[1]) <= tol
        if not (x_edge and y_edge) or min(abs(z0 - z) for z in bz) <= tol:
            continue
        x_inner = x1 if abs(x0 - bx[0]) <= tol else x0
        y_inner = y1 if abs(y0 - by[0]) <= tol else y0

        xwall = next(
            (
                f
                for f in faces
                if f.axis == "x"
                and abs(_center(f.bb, _AXES["x"]) - x_inner) <= tol
                and _overlap_len(f.bb, floor.bb, "y") >= y1 - y0 - tol
            ),
            None,
        )
        ywall = next(
            (
                f
                for f in faces
                if f.axis == "y"
                and abs(_center(f.bb, _AXES["y"]) - y_inner) <= tol
                and _overlap_len(f.bb, floor.bb, "x") >= x1 - x0 - tol
            ),
            None,
        )
        if xwall is None or ywall is None:
            continue
        wz0, wz1 = limits(xwall.bb, "z")
        vz0, vz1 = limits(ywall.bb, "z")
        d_lo, d_hi = max(wz0, vz0), min(wz1, vz1)
        if d_hi - d_lo <= tol or not (d_lo - tol <= z0 <= d_hi + tol):
            continue

        sx, sy = x1 - x0, y1 - y0
        if sx <= sy:
            width_axis, long_axis = "x", "y"
            width, length, w_center, lo, hi = sx, sy, (x0 + x1) / 2, y0, y1
        else:
            width_axis, long_axis = "y", "x"
            width, length, w_center, lo, hi = sy, sx, (y0 + y1) / 2, x0, x1
        out.append(
            Pocket(
                width_axis=width_axis,
                long_axis=long_axis,
                width=round(width, 2),
                length=round(length, 2),
                depth=round(d_hi - d_lo, 2),
                w_center=round(w_center, 2),
                lo=round(lo, 2),
                hi=round(hi, 2),
                d_lo=round(d_lo, 2),
                d_hi=round(d_hi, 2),
                open_sign=1 if floor.normal[2] > 0 else -1,
                edge_anchored=True,
            )
        )
        if claims is not None:
            # The floor belongs here, unlike the opposed-wall path above: this loop is *over*
            # floors, and the notch's footprint is read straight off this one's bounding box.
            claims.setdefault(out[-1], set()).update(
                node for node in (floor.node, xwall.node, ywall.node) if node is not None
            )
    return out
