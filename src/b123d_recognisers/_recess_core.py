# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Shared wall-and-floor geometry substrate for recess recognisers."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, replace
from types import SimpleNamespace
from typing import Literal, TypeVar, cast, overload

from build123d import Box, GeomType, Pos
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane

from b123d_recognisers._adjacency import FaceEdges, FaceGraph, FaceNode, frame_points_outward
from b123d_recognisers._geometry import length_tol
from b123d_recognisers._recess_records import Channel, Pocket, Slot
from b123d_recognisers._typing import Bounds, Part

_AXES = {"x": 0, "y": 1, "z": 2}
_R = TypeVar("_R", Slot, Pocket)

#: Which faces a record was built from, while it is being built. Keyed by the record's *value*,
#: which is safe here and nowhere else: this map lives inside one recognition of one part, and
#: `_merge` already treats two candidates within `_MERGE_TOL` of each other as one feature -- so
#: two value-equal candidates are, by the pipeline's own definition, the same slot. The ledger
#: the values end up in keys by claim identity instead, because there two equal-valued *records*
#: really can be two features.
#:
#: Spelled out rather than left as a bare ``dict``: the alias is the only description this map
#: has, and an unparameterised one type-checks ``setdefault(<anything>, 1).no_such_method()``
#: clean. `_Face.bb` below records what that costs on a field this module touches constantly.
_Claims = dict[Slot | Pocket, set[FaceNode]]
_AXIS_ALIGNED_TOL = 1e-3
# Coordinate-merge and floor-coincidence bands. **Absolute, per ADR 0008.**
#
# 0.2.3 scaled these to the solid's largest extent on the reasoning that they have no smaller
# feature to measure against. That reference was too coarse: whether two pockets are one pocket
# depends on the pockets, not on the plate they sit in, so a large plate merged recesses that a
# small one kept. _MERGE_TOL also gates the minimum separation of two slot ends, so the same
# change simultaneously raised a threshold. Both directions lose records, which is why the
# downstream report that prompted this saw nineteen losses across six parts and no gains.
_MERGE_TOL = 0.5
_FLOOR_TOL = 0.3


_FLOOR_COVER_FRAC = 0.5
_VOID_INSET = 0.1
_VOID_VOL_FRAC = 0.01
_LENGTH_TIE_FRAC = 0.05
_SLOT_MAX_SPAN_FRAC = 0.9


def _absorb(claims: _Claims | None, into: Slot | Pocket, *from_: Slot | Pocket) -> None:
    """Give *into* the nodes of every record in *from_*, the records the pipeline replaces by it.

    Every transform below rebuilds records rather than mutating them -- `_merge` keeps one of a
    group, `_collapse_collinear` spans several into one, `_extend_obround_ends` `replace`s
    fields -- so without this the claim would be attached to a record that never reaches the
    caller. `_body_scoped_pairs` `replace`s a field too, but reads the map before it does rather
    than going through here, because that is also where the map is scoped to one solid.
    """

    if claims is None:
        return
    nodes = claims.setdefault(into, set())
    for record in from_:
        nodes |= claims.get(record, set())


def _outward_normal(face) -> tuple[float, float, float] | None:
    """Unit outward normal of a planar face as an (x, y, z) tuple, or None when the face is
    not planar.

    The plane's own frame direction, signed by
    :func:`b123d_recognisers._adjacency.frame_points_outward` -- which is the material-side
    convention this used to spell out for itself, and which three other sites spelled out
    separately."""
    surf = BRepAdaptor_Surface(face.wrapped)
    if surf.GetType() != GeomAbs_Plane:
        return None
    n = surf.Plane().Axis().Direction()
    sign = 1.0 if frame_points_outward(face) else -1.0
    return (sign * n.X(), sign * n.Y(), sign * n.Z())


def _dominant_axis(nrm) -> str | None:
    """Return the axis letter when ``nrm`` is axis-aligned, else None."""
    for axis, k in _AXES.items():
        if abs(abs(nrm[k]) - 1.0) <= _AXIS_ALIGNED_TOL:
            return axis
    return None


@dataclass(frozen=True)
class _Face:
    """A planar face reduced to the data the recogniser needs."""

    normal: tuple
    #: The principal axis this face's normal aligns with, or None when it aligns with none.
    #: Total by ADR 0009: an oblique wall is carried with ``axis=None`` rather than dropped, so
    #: the family that cannot use it is the one seen to decline it.
    axis: str | None
    #: Typed rather than left as ``object``: every use reads ``.min``/``.max``, so the
    #: placeholder silently disabled checking on the field this module touches most.
    bb: Bounds
    wall: bool  # a valid slot wall: LINE/CIRCLE edges, at least one straight LINE
    #: The graph node for this face, when the caller asked for claims; None otherwise. The
    #: reduction above is what the recogniser needs to *decide*, and it deliberately drops the
    #: face -- so before this field there was no way to say which faces a slot was built from,
    #: and passage/slot reconciliation compared record coordinates instead.
    node: FaceNode | None = None


def _is_wall(face, face_edges: FaceEdges | None = None) -> bool:
    """True when *face* can be a slot wall: bounded only by straight (LINE) or circular-arc
    (CIRCLE) edges, with **at least one** straight edge and **at most one** arc. A fully
    rectangular wall qualifies (all LINE); a slot cut into round stock has a wall the OD clips
    into a *single* arc + a straight floor/chord, which now qualifies too.

    A turned groove / circlip recess is still rejected — its annular wall is a washer bounded
    by *two* concentric arcs (the outer OD + the inner floor circle), so the ``<= 1`` arc cap
    excludes it. That cap holds even when a keyway / flat / cross-hole notches a straight edge
    into the annulus, which is why the arc-count proof is stronger than an
    "all edges must be straight" test: the
    two concentric arcs survive, so a keyed groove never reads as a slot. A freeform
    (spline/ellipse) face is rejected outright."""
    edges = face_edges.of(face) if face_edges is not None else face.edges()
    types = [e.geom_type for e in edges]
    if not types or any(t not in (GeomType.LINE, GeomType.CIRCLE) for t in types):
        return False
    n_line = sum(1 for t in types if t == GeomType.LINE)
    n_circle = sum(1 for t in types if t == GeomType.CIRCLE)
    return n_line >= 1 and n_circle <= 1


def _planar_faces(
    part: Part, face_edges: FaceEdges | None = None, graph: FaceGraph | None = None
) -> list[_Face]:
    """Every planar face as an :class:`_Face` record (computed once).

    *graph* is threaded only when the caller wants claims. Without it no node is resolved, so
    a run that claims nothing pays nothing -- which matters because this is called once per
    solid by three families.

    A compound is scanned per solid while the graph covers the whole part, and the faces of a
    solid are the same shapes the part yields, so they resolve against it. A face that does not
    resolve is refused: it can only mean the caller paired a graph with a different part, and
    while no *wrong* claim would then be made, no claim would be made either -- leaving the
    caller unable to tell "this part has no claimable slots" from "you handed me the wrong
    graph". A reconciler reading that empty ledger concludes there is no overlap and reports
    the duplicate feature it exists to suppress. `ClaimLedger.claims_of` refuses a foreign node
    for the same reason rather than answering "no claims"; this is that check one layer up.
    """

    faces = []
    for face in part.faces():
        nrm = _outward_normal(face)
        if nrm is None:
            continue  # not planar, which is this function's declared domain and its name
        bb = face.bounding_box()
        node = None if graph is None else graph.require_node(face)
        # `axis` is None for an oblique planar face, and the face is carried anyway. It used to
        # be dropped here, which made an axis-aligned-walls restriction that three families
        # inherit invisible to all three and impossible to count -- see ADR 0009. Each family
        # now declines it for itself, where the rejection can be named and measured.
        faces.append(
            _Face(nrm, _dominant_axis(nrm), bb, _is_wall(face, face_edges), node)
        )
    return faces


def _center(bb, k) -> float:
    return float(getattr(bb.min, "XYZ"[k]) + getattr(bb.max, "XYZ"[k])) / 2


def _overlap_len(bb_a, bb_b, axis) -> float:
    """Length of the overlap of two bboxes along ``axis`` (0 if disjoint)."""
    c = "XYZ"[_AXES[axis]]
    lo = max(getattr(bb_a.min, c), getattr(bb_b.min, c))
    hi = min(getattr(bb_a.max, c), getattr(bb_b.max, c))
    return float(hi - lo)


def _candidate(fa: _Face, fb: _Face, part_ext: dict[str, float], axis: str) -> Slot | None:
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


def _end_capped(
    faces: list[_Face], foot, foot_area, depth_axis, end, want
) -> bool:
    """True when inward-facing planar faces at ``end`` on ``depth_axis`` together cover at
    least :data:`_FLOOR_COVER_FRAC` of the ``foot`` (width×length) footprint — one end's
    half of the floor test.

    ``want`` is the sign the covering normal must point (+depth at the low end, -depth at the
    high end) so the cap faces *into* the cavity; the part's own outer face at that level
    faces the other way and is excluded (that is what separates a real floor from a
    through-open end). Coverage is *aggregated* over all qualifying faces (not tested per
    face), so a floor split by a rib/divider still counts. The sum (not union) is
    exact for the coplanar floor faces of a valid solid; overlaps only arise from
    interpenetrating solids (degenerate input)."""
    dk = _AXES[depth_axis]
    covered = 0.0
    for f in faces:
        if f.axis != depth_axis or abs(_center(f.bb, dk) - end) > _FLOOR_TOL:
            continue
        if f.normal[dk] * want <= 0:
            continue
        area = 1.0
        for ax, (lo, hi) in foot.items():
            c = "XYZ"[_AXES[ax]]
            ov = min(getattr(f.bb.max, c), hi) - max(getattr(f.bb.min, c), lo)
            area *= max(ov, 0.0)
        covered += area
    return bool(covered >= _FLOOR_COVER_FRAC * foot_area)


def _floor_ends(faces: list[_Face], s: Slot) -> int:
    """How many of *s*'s two depth ends a planar floor caps: ``0`` = through (open both ends),
    ``1`` = a blind recess (one floor + one opening — a real pocket), ``2`` = a sealed internal
    void (capped both ends, no opening — NOT a machinable recess). The obround end-cap recovery
    routes on this exact count, so a sealed void is not misread as a full-thickness-deep pocket."""
    foot = {
        s.width_axis: (s.w_center - s.width / 2, s.w_center + s.width / 2),
        s.long_axis: (s.lo, s.hi),
    }
    foot_area = math.prod(hi - lo for lo, hi in foot.values())
    return int(_end_capped(faces, foot, foot_area, s.depth_axis, s.d_lo, 1.0)) + int(
        _end_capped(faces, foot, foot_area, s.depth_axis, s.d_hi, -1.0)
    )


def _open_sign(faces: list[_Face], s) -> int:
    """Which depth end *s* opens toward: ``+1`` (floor at ``d_lo``, opens +depth) or ``-1``
    (floor at ``d_hi``, opens -depth). The capped end is the floor; the pocket opens the other
    way. Assumes *s* is a blind recess (exactly one floor); the caller has already checked."""
    foot = {
        s.width_axis: (s.w_center - s.width / 2, s.w_center + s.width / 2),
        s.long_axis: (s.lo, s.hi),
    }
    foot_area = math.prod(hi - lo for lo, hi in foot.values())
    return 1 if _end_capped(faces, foot, foot_area, s.depth_axis, s.d_lo, 1.0) else -1


def _has_floor(faces: list[_Face], s: Slot) -> bool:
    """True when a planar floor caps the slot at *either* depth end — i.e. it is not a through
    slot. The through/blind split for :func:`recognise_slots`'s flat-wall path; the obround end-cap
    path uses the finer :func:`_floor_ends` count (a pocket is capped on exactly one end)."""
    return _floor_ends(faces, s) >= 1


# A radiused-end (obround) slot has semicircular end caps whose radius is the slot's
# half-width; a cylindrical face counts as such a cap when its radius is within this fraction
# of width/2 (ADR 0008). Tight, so a filleted-corner rectangular slot (small corner radii) is
# not extended. The fraction is the 0.15 mm constant it replaces over the corpus's 4 mm
# reference radius.
_END_RADIUS_FRAC = 0.0375


def _cylinder_faces(part: Part) -> list[tuple]:
    """``(radius, axis_letter, axis_location, bbox, concave)`` for each axis-aligned cylindrical
    face of *part* — the candidate obround end caps. ``axis_location`` is a point on the
    cylinder axis; ``bbox`` bounds the face (used to confirm the cap spans the slot's depth, not
    some unrelated cylinder at a different depth); ``concave`` is True when the face bounds a
    *void* (its material-outward normal points inward, toward the axis) — a recess wall — rather
    than added material (a boss/post). Shares `_outward_normal`'s material-side convention rather
    than restating it -- both now ask `frame_points_outward`, which is where the convention
    lives."""
    out = []
    for face in part.faces():
        surf = BRepAdaptor_Surface(face.wrapped)
        if surf.GetType() != GeomAbs_Cylinder:
            continue
        cyl = surf.Cylinder()
        d = cyl.Axis().Direction()
        axis = _dominant_axis((d.X(), d.Y(), d.Z()))
        if axis is None:
            continue
        loc = cyl.Axis().Location()
        concave = not frame_points_outward(face)
        out.append((cyl.Radius(), axis, (loc.X(), loc.Y(), loc.Z()), face.bounding_box(), concave))
    return out


def _end_cap_at(caps: list[tuple], s: _R, coord: float) -> bool:
    """True when a semicircular obround end cap sits at ``coord`` along the long axis: a
    **concave** (void-bounding) cylinder of radius ≈ ``s.width/2`` about the depth axis, on the
    slot centreline, **spanning the slot's own depth extent** ``[d_lo, d_hi]``. Two clauses
    separate a real cap from a coaxial impostor at the same place: the depth-extent test rejects
    a boss/hole at a *different* depth, and the concavity test rejects added material — a post or
    boss protruding *into* the slot end at the slot's depth."""
    r = s.width / 2
    li, wi, di = _AXES[s.long_axis], _AXES[s.width_axis], _AXES[s.depth_axis]
    dc = "XYZ"[di]
    return any(
        concave
        and abs(rad - r) <= length_tol(r, rel=_END_RADIUS_FRAC)
        and ax == s.depth_axis
        and abs(loc[li] - coord) <= _MERGE_TOL
        and abs(loc[wi] - s.w_center) <= _MERGE_TOL
        and abs(getattr(bb.min, dc) - s.d_lo) <= _MERGE_TOL
        and abs(getattr(bb.max, dc) - s.d_hi) <= _MERGE_TOL
        for rad, ax, loc, bb, concave in caps
    )


def _extend_obround_ends(
    records: list[_R], part: Part, claims: _Claims | None = None
) -> list[_R]:
    """Extend radiused-end (obround) slots/pockets to their **overall** length.

    The recogniser pairs the two flat side walls, so the raw ``lo``/``hi`` stop at the straight
    portion — a slot with semicircular ends under-reports its length by the two end radii (each
    ``width/2``). A true obround is symmetric, so a slot is extended only when a semicircular end
    cap (:func:`_end_cap_at`) is present at **both** ends; each end is then pushed out by the
    radius, keeping the centre fixed. Requiring both ends (not one) avoids a lone coaxial
    cylinder shifting a flat-ended slot's centre, and matches explicit-object readers that
    derive overall length from the object bounding box. Rectangular slots have no caps
    and are returned unchanged."""
    caps = _cylinder_faces(part)
    if not caps:
        return records
    out: list[_R] = []
    for s in records:
        r = s.width / 2
        if _end_cap_at(caps, s, s.lo) and _end_cap_at(caps, s, s.hi):
            extended = replace(
                s,
                lo=round(s.lo - r, 2),
                hi=round(s.hi + r, 2),
                length=round(s.hi - s.lo + 2 * r, 2),
            )
            _absorb(claims, extended, s)
            out.append(extended)
        else:
            out.append(s)
    return out


# An obround through-slot whose straight section is shorter than its width has flat side
# walls too short to pair as an elongated slot: `_candidate` either rejects it (width > the short
# straight length) or mistakes the full through-thickness for the length (a full-span cut). Its
# length lives in the two semicircular ends, so recognise it directly from the end caps — a pair of
# concave HALF-cylinders (in-plane bbox ≈ 2r × r) of equal radius, coaxial about a through depth
# axis, on a shared centreline, bulging apart along the long axis. A round hole is a FULL cylinder
# (bbox 2r × 2r) so it is never read as an end; a lone unpaired end is a fillet/round.
_OBROUND_RATIO_TOL = 0.1  # a half-cylinder's in-plane extents are 2r (across) / r (bulge) — match
# by RATIO to the radius (2.0 / 1.0), so the discriminator holds at every scale, not just large r.
# Coaxial cap faces (a semicircle a STEP importer split into two quarter-cylinders) are clustered
# when their axis lines sit within this fraction of the cap radius; importer split noise is a
# fraction of the face, well inside it, and a real slot's two ends are separated by its straight
# run, well outside. The fraction is the 0.3 mm constant it replaces over the 4 mm reference.
_CAP_CLUSTER_FRAC = 0.075


def _obround_end(cap: tuple) -> tuple | None:
    """Classify a concave cylinder *cap* (from :func:`_cylinder_faces`) as a half-cylinder obround
    end, or None. A half-cylinder end's in-plane bounding box is ≈ 2r across (its width axis) by
    ≈ r along the bulge (its long axis) — a full cylinder (round hole) is 2r × 2r and is rejected.
    The 2r/r test is by RATIO to the radius so the classifier holds at any scale (fixing the
    absolute-tolerance collapse for small radii). Returns
    ``(width_axis, long_axis, depth_axis,
    radius, w_center, flat, direction, d_lo, d_hi)`` — ``flat`` is the cylinder-axis position on the
    long axis (the straight-wall junction), ``direction`` (±1) the side the cap bulges toward. The
    through/blind split is left to the caller's :func:`_has_floor` (authoritative and local, so a
    through-slot in a thin step of stepped stock is not rejected by a global-thickness
    assumption)."""
    rad, ax, loc, bb, concave = cap
    if not concave or rad <= 0:
        return None
    others = [a for a in "xyz" if a != ax]
    ext = {a: getattr(bb.max, "XYZ"[_AXES[a]]) - getattr(bb.min, "XYZ"[_AXES[a]]) for a in others}
    across = [a for a in others if abs(ext[a] / rad - 2.0) <= _OBROUND_RATIO_TOL]
    bulge = [a for a in others if abs(ext[a] / rad - 1.0) <= _OBROUND_RATIO_TOL]
    if len(across) != 1 or len(bulge) != 1 or across[0] == bulge[0]:
        return None
    width_axis, long_axis = across[0], bulge[0]
    dc = "XYZ"[_AXES[ax]]
    d_lo, d_hi = getattr(bb.min, dc), getattr(bb.max, dc)
    lc = "XYZ"[_AXES[long_axis]]
    flat = loc[_AXES[long_axis]]
    direction = -1 if (flat - getattr(bb.min, lc)) > (getattr(bb.max, lc) - flat) else 1
    # w_center from the (merged) bbox centre, not loc — an imported STEP splits an end into two
    # quarter faces whose axis Location differs by ~0.02 mm across the diameter, so loc[width] is
    # unreliable while the union bbox centre is exact. flat (loc[long]) stays consistent.
    return (
        width_axis,
        long_axis,
        ax,
        rad,
        _center(bb, _AXES[width_axis]),
        flat,
        direction,
        d_lo,
        d_hi,
    )


def _has_side_walls(faces: list[_Face], s: Slot) -> bool:
    """True when the two flat side walls of obround slot *s* are present: **inward-facing** wall
    faces on the width axis at ``w_center - width/2`` (material-outward normal toward
    +width) and ``w_center + width/2`` (normal toward -width), each overlapping the
    straight run ``[s.lo, s.hi]``. Confirms a genuine channel connects the two end caps —
    rejects two independent D-cutouts whose caps merely alternate ``-1, +1`` across solid.
    The normal-direction test is essential: the stock's own OUTWARD-facing side faces sit
    at the same ``w_center ± width/2`` when the stock is exactly as wide as the slot, and
    would otherwise be mistaken for the channel walls.
    """
    wk, lk = _AXES[s.width_axis], _AXES[s.long_axis]
    lo_wall, hi_wall = False, False
    for f in faces:
        if not f.wall or f.axis != s.width_axis:
            continue
        lo, hi = getattr(f.bb.min, "XYZ"[lk]), getattr(f.bb.max, "XYZ"[lk])
        if min(hi, s.hi) - max(lo, s.lo) <= 0:  # wall does not span the straight run
            continue
        c = _center(f.bb, wk)
        # inward-facing: the low-side wall's outward normal points toward the centreline (+width),
        # the high-side wall's toward -width. The stock's exterior faces point the other way.
        if abs(c - (s.w_center - s.width / 2)) <= _MERGE_TOL and f.normal[wk] > 0:
            lo_wall = True
        if abs(c - (s.w_center + s.width / 2)) <= _MERGE_TOL and f.normal[wk] < 0:
            hi_wall = True
    return lo_wall and hi_wall


def _union_bb(a, b) -> SimpleNamespace:
    """Axis-aligned union of two bounding boxes, as a ``min``/``max`` namespace matching the
    build123d ``BoundBox`` interface (``.min.X`` …) the cap helpers read."""
    mn = SimpleNamespace(X=min(a.min.X, b.min.X), Y=min(a.min.Y, b.min.Y), Z=min(a.min.Z, b.min.Z))
    mx = SimpleNamespace(X=max(a.max.X, b.max.X), Y=max(a.max.Y, b.max.Y), Z=max(a.max.Z, b.max.Z))
    return SimpleNamespace(min=mn, max=mx)


def _obround_ends(part: Part) -> list[tuple]:
    """The obround end caps of *part*, robust to the imported-STEP topology that splits a
    semicircular end into two quarter-cylinder faces.

    A physical end is one or more **coaxial** concave cylinder faces sharing an axis line and depth:
    build123d emits it as a single half-cylinder face (in-plane bbox ``2r × r``), while a STEP
    importer commonly splits it into two quarter-cylinders (``r × r`` each) whose axis Locations
    differ by ~0.02 mm across the diameter. Faces are therefore **clustered by proximity** of their
    axis line (same axis + radius + depth, in-plane position within ``_CAP_CLUSTER_FRAC`` of the
    cap radius) rather
    than exact-key grouping, and the UNION in-plane bbox is classified via
    :func:`_obround_end` — the union of the two quarters is the same ``2r × r`` a single
    half-cylinder gives. (A round hole is a full cylinder, ``2r × 2r``, so its union still
    fails the ratio test.)
    """
    clusters: list[dict] = []
    for rad, ax, loc, bb, concave in _cylinder_faces(part):
        if not concave or rad <= 0:
            continue
        o0, o1 = [a for a in "xyz" if a != ax]
        dc = "XYZ"[_AXES[ax]]
        ip = (loc[_AXES[o0]], loc[_AXES[o1]])
        dz = (round(getattr(bb.min, dc), 1), round(getattr(bb.max, dc), 1))
        for cl in clusters:
            if (
                cl["ax"] == ax
                and abs(cl["rad"] - rad) <= length_tol(rad, rel=_END_RADIUS_FRAC)
                and cl["dz"] == dz
                and abs(cl["ip"][0] - ip[0]) <= length_tol(rad, rel=_CAP_CLUSTER_FRAC)
                and abs(cl["ip"][1] - ip[1]) <= length_tol(rad, rel=_CAP_CLUSTER_FRAC)
            ):
                cl["bb"] = _union_bb(cl["bb"], bb)
                break
        else:
            clusters.append({"ax": ax, "rad": rad, "loc": loc, "ip": ip, "dz": dz, "bb": bb})
    ends = []
    for cl in clusters:
        e = _obround_end((cl["rad"], cl["ax"], cl["loc"], cl["bb"], True))
        if e is not None:
            ends.append(e)
    return ends


@overload
def _recognise_obround_from_ends(
    part: Part, faces: list[_Face], *, blind: Literal[False] = ...
) -> list[Slot]: ...


@overload
def _recognise_obround_from_ends(
    part: Part, faces: list[_Face], *, blind: Literal[True]
) -> list[Pocket]: ...


def _recognise_obround_from_ends(
    part: Part, faces: list[_Face], *, blind: bool = False
) -> list[Slot] | list[Pocket]:
    """Recognise obround recesses from their semicircular end caps — the path for recesses whose
    flat walls are too short for :func:`_candidate`/:func:`_pocket_candidate` to pair.
    Merged ends (:func:`_obround_ends`, quarter/half-cylinder agnostic) are grouped by centreline/
    radius/depth, then within a group sorted along the run and paired: a cap bulging toward -long
    immediately followed by one bulging toward +long is one recess's two ends (the void lies between
    their flats); the reverse adjacency is the solid gap between two recesses and is skipped. Each
    pair is confirmed by :func:`_has_side_walls` (a real channel connects the ends — not two
    D-cutouts across solid), then :func:`_has_floor` routes it: ``blind=False`` keeps only through
    recesses (:class:`Slot`), ``blind=True`` keeps only floored ones (:class:`Pocket`, depth =
    ``d_hi - d_lo``). ``lo``/``hi`` are emitted at the straight-wall junctions so
    :func:`_extend_obround_ends` adds the two radii (uniform with the flat-wall path, and `_merge`
    folds any duplicate an elongated obround's flat walls also produced).

    The two flats must be more than ``_MERGE_TOL`` apart to count as distinct ends — so a genuinely
    sub-millimetre obround (straight run < 0.5 mm) is not recovered; supporting that would need the
    module-wide absolute ``_MERGE_TOL`` to go relative, out of scope here."""
    groups: dict[tuple, list[tuple]] = {}
    for e in _obround_ends(part):
        wa, la, da, rad, wc, flat, direction, dlo, dhi = e
        key = (wa, la, da, round(rad, 2), round(wc, 2), round(dlo, 2), round(dhi, 2))
        groups.setdefault(key, []).append(e)
    # The list is homogeneous per call -- `blind` decides which record kind is appended -- but
    # that is a fact about the flag, not about this local, so the overloads above carry it and
    # the local is typed as what it structurally is.
    out: list[Slot | Pocket] = []
    for (wa, la, _da, rad, wc, dlo, dhi), grp in groups.items():
        run = sorted(grp, key=lambda e: e[5])  # by flat along the long axis
        i = 0
        while i < len(run) - 1:
            lo_end, hi_end = run[i], run[i + 1]
            # A recess's two ends bulge APART (low end toward -long, high end toward +long), so the
            # void is between their flats. The reverse pair is solid stock between recesses — skip.
            if not (
                lo_end[6] == -1
                and hi_end[6] == 1
                and hi_end[5] - lo_end[5] > _MERGE_TOL
            ):
                i += 1
                continue
            lo_f, hi_f = round(lo_end[5], 2), round(hi_end[5], 2)
            s = Slot(
                width_axis=wa,
                long_axis=la,
                width=round(2 * rad, 2),
                length=round(hi_f - lo_f, 2),
                w_center=round(wc, 2),
                lo=lo_f,
                hi=hi_f,
                d_lo=round(dlo, 2),
                d_hi=round(dhi, 2),
            )
            # Confirm a real channel (side walls) joins the ends, rather than two D-cutouts
            # bridging solid. On failure the caps may belong to a later valid pair, so advance
            # by one.
            if not _has_side_walls(faces, s):
                i += 1
                continue
            # Route on the EXACT floor count: a pocket is capped on ONE end (floor + opening); a
            # through-slot on neither; a sealed internal void (both ends capped) is neither — do not
            # emit it as a full-thickness-deep pocket.
            n_floor = _floor_ends(faces, s)
            if blind and n_floor == 1:
                out.append(
                    Pocket(
                        width_axis=wa,
                        long_axis=la,
                        width=round(2 * rad, 2),
                        length=round(hi_f - lo_f, 2),
                        depth=round(dhi - dlo, 2),
                        w_center=round(wc, 2),
                        lo=lo_f,
                        hi=hi_f,
                        d_lo=round(dlo, 2),
                        d_hi=round(dhi, 2),
                        # which face this obround pocket opens through
                        open_sign=_open_sign(faces, s),
                    )
                )
                i += 2
            elif not blind and n_floor == 0:
                out.append(s)
                i += 2
            else:
                i += 1  # not ours: a pocket in a slot scan, a slot in a pocket scan, or a void
    return cast(list[Slot] | list[Pocket], out)


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

    faces = _planar_faces(part, face_edges, graph)
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
                s = _candidate(walls[i], walls[j], part_ext, axis)
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


def _body_signature(solid) -> tuple[float, ...]:
    """Exact geometry-derived correspondence key for one physical solid.

    Position, envelope, volume, and area are independent of compound traversal order.  The key
    is deliberately not a traversal index or an OCP object/hash, so it remains serializable
    under package ADR 0002. Callers treat duplicate signatures across separate solids as
    ambiguous and fail closed rather than using the signature as proof of shared ownership.
    """
    bb = solid.bounding_box()
    return (
        float(bb.min.X),
        float(bb.min.Y),
        float(bb.min.Z),
        float(bb.max.X),
        float(bb.max.Y),
        float(bb.max.Z),
        float(solid.volume),
        float(solid.area),
    )


def _body_scoped_pairs(sources, recognise_one, claims: _Claims | None = None) -> list[tuple]:
    """The same, paired with the nodes each record was built from.

    The claim is read **per solid**, before the next one runs, and the map is cleared between
    them. Reading it afterwards would have been wrong for a compound: the map is keyed by record
    value, and two solids occupying the same space produce value-equal slots *and* duplicate body
    signatures -- so both records would have come back carrying the union of both solids' faces.
    That is precisely the cross-solid confusion `body_key` fails closed on, and it would have
    reappeared in the claims.
    """

    signatures = [_body_signature(solid) for solid in sources]
    counts = Counter(signatures)
    out: list[tuple] = []
    for solid, signature in zip(sources, signatures, strict=True):
        if claims is not None:
            claims.clear()
        for record in recognise_one(solid):
            keyed = replace(record, body_key=signature if counts[signature] == 1 else None)
            nodes = frozenset() if claims is None else frozenset(claims.get(record, ()))
            out.append((keyed, nodes))
    return out


def _same_channel_line(a: Slot, b: Slot) -> tuple[float, float] | None:
    """When ``a`` and ``b`` are collinear co-axial slot *arms* — same wall plane
    (width axis, centreline, width and depth extent) but disjoint along their run
    — return the gap ``(g_lo, g_hi)`` between them along ``long_axis``; else None.

    Two arms of one channel that a crossing cut has split share every
    dimension but their run; two genuinely parallel slots have different
    centrelines (``w_center``) and never reach here."""
    if a.width_axis != b.width_axis or a.long_axis != b.long_axis:
        return None
    if abs(a.w_center - b.w_center) > _MERGE_TOL or abs(a.width - b.width) > _MERGE_TOL:
        return None
    if abs(a.d_lo - b.d_lo) > _MERGE_TOL or abs(a.d_hi - b.d_hi) > _MERGE_TOL:
        return None
    if a.hi <= b.lo:
        gap = (a.hi, b.lo)
    elif b.hi <= a.lo:
        gap = (b.hi, a.lo)
    else:
        return None  # overlapping along the run — not two disjoint arms
    return gap if gap[1] - gap[0] > 0 else None


def _gap_is_void(gap, arm: Slot, part: Part) -> bool:
    """True when the *whole* gap between two collinear arms is empty space — a
    crossing channel of matching cross-section runs through it — rather than solid
    stock or merely pierced by an incidental void.

    The gap region is the box of its full run (along ``long_axis``) × the arm's
    width × the arm's depth, inset slightly off the arm walls to avoid
    coincident-face noise.  A crossing channel carves this box away entirely, so
    its intersection with the solid is (near) zero volume.  A solid bridge fills
    it; a small unrelated hole between two aligned slots leaves the box corners
    solid — both keep a substantial intersection, so the arms stay separate.
    Testing the whole box (not a single sample point) is what distinguishes a
    channel from an incidental hole at the gap centre.

    Known limitation: a wide *enclosed* void (a square window/pocket) flush with
    the arm ends also empties the box and so fuses the arms.  This is a continuum
    with the accepted symmetric-cross case — which likewise leaves the merged
    slot wall-less where the crossing channel passes — and distinguishing a
    narrow crossing channel from a wide window is an aspect-ratio judgement with
    no clean line; the supported scope is intersecting *channels*, so it is left as-is."""
    span = {
        arm.long_axis: (gap[0], gap[1]),
        arm.width_axis: (arm.w_center - arm.width / 2, arm.w_center + arm.width / 2),
        arm.depth_axis: (arm.d_lo, arm.d_hi),
    }
    size, centre = {}, {}
    for ax, (lo, hi) in span.items():
        inset = min(_VOID_INSET, (hi - lo) / 4)
        size[ax] = (hi - lo) - 2 * inset
        centre[ax] = (lo + hi) / 2
    if min(size.values()) <= 0:
        return False
    probe = Pos(centre["x"], centre["y"], centre["z"]) * Box(size["x"], size["y"], size["z"])
    inter = part.intersect(probe)
    # ``intersect`` returns None (empty), a single shape with ``.volume`` (older
    # build123d), or a ShapeList of shapes (newer build123d) — sum either way.
    if inter is None:
        inter_vol = 0.0
    elif hasattr(inter, "volume"):
        inter_vol = inter.volume
    else:
        inter_vol = sum(s.volume for s in inter)
    box_vol = size["x"] * size["y"] * size["z"]
    return bool(inter_vol <= _VOID_VOL_FRAC * box_vol)


def _collapse_collinear(
    slots: list[Slot], part: Part, claims: _Claims | None = None
) -> list[Slot]:
    """Recombine slot arms split by a crossing channel into whole channels.

    A ``+`` of two intersecting through-channels is milled as one continuous slot
    each, but the central intersection removes the middle of both channels' walls,
    so the wall scan yields two collinear arm-slots per channel (four total).
    Union collinear co-axial arms whose gap is void (a crossing channel passes
    between them), and span each group into a single slot running its full length.
    Arms separated by solid material — two genuinely distinct slots — are left as
    separate features."""
    parent = list(range(len(slots)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(slots)):
        for j in range(i + 1, len(slots)):
            gap = _same_channel_line(slots[i], slots[j])
            if gap is not None and _gap_is_void(gap, slots[i], part):
                parent[find(i)] = find(j)

    groups: dict[int, list[Slot]] = {}
    for idx, s in enumerate(slots):
        groups.setdefault(find(idx), []).append(s)

    out: list[Slot] = []
    for members in groups.values():
        if len(members) == 1:
            out.append(members[0])
            continue
        base = members[0]
        lo = min(m.lo for m in members)
        hi = max(m.hi for m in members)
        spanned = Slot(
            width_axis=base.width_axis,
            long_axis=base.long_axis,
            width=base.width,
            length=round(hi - lo, 2),
            w_center=base.w_center,
            lo=round(lo, 2),
            hi=round(hi, 2),
            d_lo=base.d_lo,
            d_hi=base.d_hi,
        )
        # One channel milled through, split into arms by a crossing channel: every arm's walls
        # bound the whole feature.
        _absorb(claims, spanned, *members)
        out.append(spanned)
    return sorted(out, key=lambda c: (c.width, _region_center(c)))


def _region_center(s: Slot | Pocket) -> tuple[float, float, float]:
    """The slot's mid-point in part coordinates (axis-ordered)."""
    c = {
        s.width_axis: s.w_center,
        s.long_axis: (s.lo + s.hi) / 2,
        s.depth_axis: (s.d_lo + s.d_hi) / 2,
    }
    return (c["x"], c["y"], c["z"])


def _merge(candidates: list[_R], claims: _Claims | None = None) -> list[_R]:
    """A rectangular slot is bounded by two orthogonal opposed-wall pairs (the
    width walls and the length end-caps), so the same feature is detected twice
    — once per pair.  Collapse candidates that occupy the same region, keeping
    the one with the smallest width (the true across-flats).

    Sorted by ``(width, region_centre)`` so the output order — and therefore the
    ``slot{i}`` annotation names downstream — is determined by geometry alone,
    not by OCC face-iteration order (which is not stable across kernels)."""
    kept: list[_R] = []
    for s in sorted(candidates, key=lambda c: (c.width, _region_center(c))):
        cs = _region_center(s)
        keeper = next((k for k in kept if math.dist(cs, _region_center(k)) <= _MERGE_TOL), None)
        if keeper is not None:
            # The dropped candidate is the *same* feature seen through its other wall pair, so
            # its walls are as much this slot's evidence as the ones that survived.
            _absorb(claims, keeper, s)
            continue
        kept.append(s)
    return kept


def _floored_candidate(
    fa,
    fb,
    faces,
    part_ext,
    axis: str,
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
    fa: _Face, fb: _Face, faces: list[_Face], part_ext: dict[str, float], axis: str
) -> Pocket | None:
    candidate = _floored_candidate(fa, fb, faces, part_ext, axis)
    return candidate if isinstance(candidate, Pocket) else None


def _channel_candidate(
    fa: _Face, fb: _Face, faces: list[_Face], part_ext: dict[str, float], part_bounds, axis: str
) -> Channel | None:
    candidate = _floored_candidate(
        fa, fb, faces, part_ext, axis, channel_bounds=part_bounds
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

    faces = _planar_faces(part, face_edges, graph)
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
                p = _pocket_candidate(walls[i], walls[j], faces, part_ext, axis)
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


def _recognise_channels_one(part: Part, face_edges: FaceEdges | None = None) -> list[Channel]:
    """Recognise channels using one solid's faces and bounds."""
    faces = _planar_faces(part, face_edges)
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
    candidates: list[Channel] = []
    for axis, walls in by_axis.items():
        for i in range(len(walls)):
            for j in range(i + 1, len(walls)):
                channel = _channel_candidate(
                    walls[i], walls[j], faces, part_ext, part_bounds, axis
                )
                if channel is not None:
                    candidates.append(channel)
    return sorted(
        set(candidates),
        key=_channel_sort_key,
    )


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
