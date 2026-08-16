# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Hole and boss records and recognition over the shared cylinder substrate."""

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Sphere, GeomAbs_Torus
from OCP.TopAbs import TopAbs_Orientation

from b123d_recognisers._cylinder_substrate import (
    _STACK_GAP_TOL,
    _cyl_group_key,
    _line_key,
    _merge_runs,
    analyse_cylinders,
    full_cylinders,
)
from b123d_recognisers._geometry import _unit
from b123d_recognisers._record import Record
from b123d_recognisers._typing import CylinderInventory, Part, Vector3
from b123d_recognisers.countersinks import CounterSink, countersink_matches_hole

_full_cyls = full_cylinders
# A counterbore-like step shallower than this fraction of its diameter is a spotface.
_SPOTFACE_MAX_RATIO = 0.2


@dataclass(frozen=True)
class CounterBore(Record):
    """A cylindrical enlargement at a hole mouth: diameter and axial depth.

    The containing :class:`HoleRecord` distinguishes ``cbore`` from ``spotface``. Their
    geometry is otherwise identical, so classification uses the documented depth/diameter
    ratio: a shallow facing cut below ``_SPOTFACE_MAX_RATIO`` is a spotface; a deeper tool step
    is a counterbore. Diameter alone cannot establish that manufacturing distinction.
    """

    diameter: float
    depth: float


@dataclass(frozen=True)
class HoleRecord(Record):
    """A drilled hole: the bore plus optional counterbore/spotface steps.

    ``axis`` is the drilling direction (unit vector pointing from the opening
    into the hole) and ``location`` the axis point at the opening surface.
    ``diameter``/``depth`` describe the bore itself — the narrowest segment of
    the stack — with ``depth`` measured from the top of the bore to the hole's
    deep end (a bottom relief groove counts, a drill point's cone does not).
    ``bottom`` is ``"through"``, ``"flat"``, ``"drill_point"``, or
    ``"unknown"`` when the adjacent geometry matches none of those.
    """

    axis: Vector3
    location: Vector3
    diameter: float
    depth: float
    bottom: str
    cbore: CounterBore | None = None
    spotface: CounterBore | None = None
    # A countersink (flat-head seat) coaxial with the bore, or None. Composed
    # from the standalone :func:`recognise_countersinks` so the hole's spec/grouping and
    # the callout-width estimate all see it.
    csink: CounterSink | None = None


@dataclass(frozen=True)
class BossRecord(Record):
    """An external cylindrical boss (including a turned part's OD).

    ``axis`` points from the base toward the free end, ``location`` is the
    axis point at the free end, and ``height`` the axial extent.
    """

    axis: Vector3
    location: Vector3
    diameter: float
    height: float


def _segments(cyls):
    """Collapse cylinder patches into segments: one per (axis line, diameter,
    contiguous axial range). Keyway-split patches of one bore merge; coaxial
    same-diameter holes from opposite faces stay separate."""
    return [
        dict(
            run[0],
            s_lo=min(p["s_lo"] for p in run),
            s_hi=max(p["s_hi"] for p in run),
            faces=[p["face"] for p in run],
        )
        for run in _merge_runs(cyls, _cyl_group_key)
    ]


def _axis_point(seg, s):
    """The 3D point on *seg*'s axis at axial coordinate *s*."""
    ax, ay, az = seg["axis_xyz"]
    dx, dy, dz = seg["dir_xyz"]
    s_ap = ax * dx + ay * dy + az * dz
    t = s - s_ap
    return (ax + t * dx, ay + t * dy, az + t * dz)


def _end_partners(seg, s_end, edge_faces, cache=None):
    """The faces beyond one axial end of *seg*: partners of edges that lie at
    that end. An opening edge on a slanted or curved surface dips away from
    the end plane (by the lip sagitta), so edges match within a margin — but
    stay well clear of the segment's other end.

    *cache* (optional) memoises the result per ``(seg, s_end)`` within one
    ``recognise_holes``/``recognise_bosses`` call — the same end is classified several
    times (``_merge_stacks`` plus the main loop), and each scan walks every
    face's edges. The seg is stored in the cached value so an ``is`` check
    rejects (and pins against) any ``id`` reuse."""
    if cache is not None:
        key = ("ep", id(seg), round(s_end, 9))
        hit = cache.get(key)
        if hit is not None and hit[0] is seg:
            return hit[1]
    dx, dy, dz = seg["dir_xyz"]
    margin = max(_STACK_GAP_TOL, min(0.45 * (seg["s_hi"] - seg["s_lo"]), 0.5 * seg["diameter"]))
    partners = []
    for face in seg["faces"]:
        for edge in face.edges():
            pts = [edge.center()] + [v.center() for v in edge.vertices()]
            if not all(abs(p.X * dx + p.Y * dy + p.Z * dz - s_end) <= margin for p in pts):
                continue
            for partner in edge_faces.get(edge, ()):
                if not any(partner.is_same(f) for f in seg["faces"]):
                    partners.append(partner)
    if cache is not None:
        cache[key] = (seg, partners)
    return partners


def _classify_end(seg, s_end, hi_end, edge_faces, cache=None):
    """Cached wrapper over :func:`_classify_end_uncached` (see *cache* there)."""
    if cache is None:
        return _classify_end_uncached(seg, s_end, hi_end, edge_faces)
    key = ("ce", id(seg), round(s_end, 9), hi_end)
    hit = cache.get(key)
    if hit is not None and hit[0] is seg:
        return hit[1]
    result = _classify_end_uncached(seg, s_end, hi_end, edge_faces, cache)
    cache[key] = (seg, result)
    return result


def _classify_end_uncached(seg, s_end, hi_end, edge_faces, cache=None):
    """Classify one axial end of a cylinder segment from the face beyond it.

    Returns ``"open"`` (the bore exits, or the boss's free end), ``"flat"``
    (closed by a plane facing back into the segment, or a boss's base),
    ``"drill_point"`` (a bore closed by a cone), or ``"unknown"``.

    Planes, cones, and tori are decisive; a curved wall (cylinder/sphere) is
    a weak signal — an exit for a bore, a base for a boss — that only counts
    when no decisive partner is present (a crossing port near a flat bottom
    must not outvote the bottom).

    An adjacent cone is read through the segment's internal/external context
    and its apex direction: for a bore, apex outward closes it (drill point)
    while apex inward widens it (an entry chamfer or countersink — open);
    for a boss the senses flip (apex outward is a chamfered free end, apex
    inward a base draft).  Tori follow the corner they round: one curling
    inward (major radius below the segment's) is a closed corner — a blind
    bore's bottom or a boss's base — and one flaring outward is an opening
    lip or a free end.
    """
    dx, dy, dz = seg["dir_xyz"]
    e_sign = 1.0 if hi_end else -1.0
    weak = None
    for partner in _end_partners(seg, s_end, edge_faces, cache):
        surf = BRepAdaptor_Surface(partner.wrapped)
        kind = surf.GetType()
        if kind == GeomAbs_Cone:
            cone = surf.Cone()
            apex = cone.Apex()
            apex_s = apex.X() * dx + apex.Y() * dy + apex.Z() * dz
            outward = (apex_s - s_end) * e_sign > 0
            if not seg["external"]:
                if outward:
                    # A deburr chamfer on a flat floor's rim is also an
                    # apex-outward cone — closed either way, but it has the
                    # floor plane right next to it where a true drill point
                    # has nothing beyond its apex.
                    for e2 in partner.edges():
                        for n in edge_faces.get(e2, ()):
                            if n.is_same(partner) or any(n.is_same(f) for f in seg["faces"]):
                                continue
                            n_surf = BRepAdaptor_Surface(n.wrapped)
                            if n_surf.GetType() != GeomAbs_Plane:
                                continue
                            nv = n.normal_at(n.center())
                            if abs(nv.X * dx + nv.Y * dy + nv.Z * dz) > 0.9:
                                return "flat"
                    return "drill_point"
                return "open"
            return "open" if outward else "flat"
        if kind == GeomAbs_Torus:
            curls_in = surf.Torus().MajorRadius() < seg["diameter"] / 2
            if not seg["external"]:
                return "flat" if curls_in else "open"
            return "open" if curls_in else "flat"
        if kind == GeomAbs_Plane:
            n = partner.normal_at(partner.center())
            dot = (n.X * dx + n.Y * dy + n.Z * dz) * e_sign
            if dot < -0.5:
                return "flat"
            if dot > 0.5:
                return "open"
        elif kind == GeomAbs_Sphere:
            # Convex (material inside the sphere): the bore exits through a
            # spherical surface. Concave (a ball-nose cavity): a closed
            # bottom — reported as "flat" (no rounded-bottom category).
            convex = (
                partner.wrapped.Orientation() == TopAbs_Orientation.TopAbs_FORWARD
            ) == surf.Sphere().Position().Direct()
            if not seg["external"]:
                weak = "open" if convex else "flat"
            else:
                weak = "flat" if convex else "open"
        elif kind == GeomAbs_Cylinder:
            weak = "open" if not seg["external"] else "flat"
    return weak or "unknown"


def _edge_face_map(part):
    """Map every edge of *part* to the faces that share it."""
    edge_faces: dict = {}
    for f in part.faces():
        for e in f.edges():
            edge_faces.setdefault(e, []).append(f)
    return edge_faces


def _shared_transition(a, b, edge_faces, cache=None):
    """True when a cone or torus face spans the gap between segment *a*'s
    high end and segment *b*'s low end — the shoulder chamfer or fillet that
    makes the two segments steps of one hole. The transition face touches
    one segment directly and may reach the other through the shoulder ring
    plane, so one adjacency hop is followed. Solid material between two
    unrelated coaxial features has no such connecting face."""
    a_partners = _end_partners(a, a["s_hi"], edge_faces, cache)
    b_partners = _end_partners(b, b["s_lo"], edge_faces, cache)
    for own, other in ((a_partners, b_partners), (b_partners, a_partners)):
        for t in own:
            if BRepAdaptor_Surface(t.wrapped).GetType() not in (GeomAbs_Cone, GeomAbs_Torus):
                continue
            if any(t.is_same(o) for o in other):
                return True
            neighbours = [f for e in t.edges() for f in edge_faces.get(e, ())]
            if any(n.is_same(o) for n in neighbours for o in other):
                return True
    return False


def _merge_stacks(stacks, edge_faces, cache=None):
    """Recombine coaxial stacks that are one hole:

    - same bore diameter on both sides of a crossing void, neither facing
      end closed (a flat bottom or drill point means genuinely separate
      holes, e.g. blind holes drilled from opposite faces);
    - different diameters whose gap is bridged by a shoulder chamfer or
      fillet face (the steps of a counterbored hole with a deburred
      shoulder).
    """
    by_line: dict = {}
    for stack in stacks:
        by_line.setdefault(_line_key(stack[0]), []).append(stack)
    merged = []
    for line_stacks in by_line.values():
        line_stacks.sort(key=lambda st: min(s["s_lo"] for s in st))
        cur = line_stacks[0]
        for nxt in line_stacks[1:]:
            a = max(cur, key=lambda s: s["s_hi"])
            b = min(nxt, key=lambda s: s["s_lo"])
            closed = ("flat", "drill_point")
            if (
                abs(a["diameter"] - b["diameter"]) < 0.01
                and _classify_end(a, a["s_hi"], True, edge_faces, cache) not in closed
                and _classify_end(b, b["s_lo"], False, edge_faces, cache) not in closed
            ):
                joined = dict(a, s_hi=b["s_hi"], faces=a["faces"] + b["faces"])
                cur = [s for s in cur if s is not a] + [joined] + [s for s in nxt if s is not b]
            elif b["s_lo"] - a["s_hi"] <= _STACK_GAP_TOL + abs(
                a["diameter"] - b["diameter"]
            ) and _shared_transition(a, b, edge_faces, cache):
                cur = cur + nxt
            else:
                merged.append(cur)
                cur = nxt
        merged.append(cur)
    return merged


def _csink_for_hole(h: HoleRecord, csinks: Sequence[CounterSink]) -> CounterSink | None:
    """The countersink seated on hole *h*, or None. A countersink belongs to the
    hole when its **minor circle** — where the cone meets the drilled bore — sits coaxially
    at one of the hole's bore *ends*: the opening (``s`` ≈ 0) or, for a through hole (open
    at both faces), the far end (``s`` ≈ depth). Keying on the minor-at-a-bore-end (not the
    opening face, nor the axis direction) makes association independent of which end
    ``recognise_holes`` happened to call the opening, and still excludes a *separate*
    coaxial hole on the opposite face — whose own bore ends are elsewhere."""
    for cs in csinks:
        if countersink_matches_hole(cs, h):
            return cs
    return None


def recognise_holes(
    part: Part,
    *,
    cyls: CylinderInventory | None = None,
    csinks: Sequence[CounterSink] | None = None,
) -> list[HoleRecord]:
    """Recognise drilled holes on *part* (see :class:`HoleRecord`).

    Coaxial internal cylinders are grouped into stacks — drill + optional
    counterbore + optional spotface become one hole, and a bore interrupted
    by a crossing hole is recombined.  The bottom is classified by probing
    the face adjacent to the deep end.  Countersinks are not recognised as
    steps (the cone is treated as an opening); steps on the far side of the
    bore (e.g. a second counterbore from the back face) are not reported.

    Pass *cyls* — a precomputed ``analyse_cylinders(part)`` result — to avoid
    re-scanning the solid (mirrors ``lint_feature_coverage``'s parameter).

    Pass *csinks* — a precomputed ``recognise_countersinks(part)`` result — to
    compose each countersink onto the hole it flares. Per the package ADR 0002
    contract this recogniser does **not** recognise countersinks itself; the
    caller owns the single inventory and injects it.
    With ``csinks=None`` the holes come back without countersink attribution.
    """
    z_cyls, cross_cyls = cyls if cyls is not None else analyse_cylinders(part)
    internal = [c for c in _full_cyls(z_cyls) + _full_cyls(cross_cyls) if not c["external"]]
    if not internal:
        return []
    edge_faces = _edge_face_map(part)
    # one end-classification cache for the whole call: the same (seg, end) is
    # classified by _merge_stacks and again in the loop below, each scan walking
    # every face's edges.
    cache: dict = {}
    stacks = _merge_stacks(_merge_runs(_segments(internal), _line_key), edge_faces, cache)

    holes = []
    for stack in stacks:
        d = stack[0]["dir_xyz"]
        lo_seg = min(stack, key=lambda s: s["s_lo"])
        hi_seg = max(stack, key=lambda s: s["s_hi"])
        lo_state = _classify_end(lo_seg, lo_seg["s_lo"], False, edge_faces, cache)
        hi_state = _classify_end(hi_seg, hi_seg["s_hi"], True, edge_faces, cache)

        # The opening is the open end; with both ends open (a through hole)
        # prefer the wider segment's end (counterbores sit at the opening),
        # falling back to the high-coordinate end (drilled from the top).
        if lo_state == "open" and hi_state != "open":
            from_hi = False
        elif hi_state == "open" and lo_state != "open":
            from_hi = True
        else:
            from_hi = hi_seg["diameter"] >= lo_seg["diameter"]
        opening_seg, opening_s = (hi_seg, hi_seg["s_hi"]) if from_hi else (lo_seg, lo_seg["s_lo"])
        bottom_state = lo_state if from_hi else hi_state
        bottom = {"open": "through"}.get(bottom_state, bottom_state)

        # Order segments from the opening inward; the bore is the narrowest
        # (not the farthest — a through hole counterbored from both sides has
        # a step beyond the bore) and only steps on the opening side count.
        ordered = sorted(stack, key=lambda s: s["s_hi"], reverse=from_hi)
        bore_i = min(range(len(ordered)), key=lambda i: ordered[i]["diameter"])
        bore = ordered[bore_i]

        # Steps narrow monotonically from the opening to the bore; a wider
        # segment between same-diameter lands is a groove (e.g. an O-ring
        # gland inside a counterbore), not a step. Lands of one step span
        # their groove.
        spans: dict = {}
        step_order = []
        min_d = math.inf
        for step in ordered[:bore_i]:
            if step["diameter"] > min_d + 0.01:
                continue
            min_d = step["diameter"]
            key = round(step["diameter"], 2)
            if key not in spans:
                spans[key] = [step["s_lo"], step["s_hi"]]
                step_order.append(key)
            else:
                spans[key][0] = min(spans[key][0], step["s_lo"])
                spans[key][1] = max(spans[key][1], step["s_hi"])
        cbore = spotface = None
        for key in step_order:
            lo, hi = spans[key]
            spec = CounterBore(key, round(hi - lo, 2))
            if spec.depth < _SPOTFACE_MAX_RATIO * spec.diameter:
                spotface = spotface or spec
            else:
                cbore = cbore or spec

        # The bore's depth runs from its top to the hole's deep end: bore
        # lands span a mid-bore groove, and a blind hole's depth includes a
        # bottom relief groove — but not a through hole's far-side steps.
        bore_segs = [s for s in stack if abs(s["diameter"] - bore["diameter"]) < 0.01]
        deep_segs = bore_segs if bottom == "through" else stack
        if from_hi:
            depth = max(s["s_hi"] for s in bore_segs) - min(s["s_lo"] for s in deep_segs)
        else:
            depth = max(s["s_hi"] for s in deep_segs) - min(s["s_lo"] for s in bore_segs)
        holes.append(
            HoleRecord(
                axis=_unit(tuple(-c for c in d) if from_hi else d),
                location=_axis_point(opening_seg, opening_s),
                diameter=bore["diameter"],
                depth=round(depth, 2),
                bottom=bottom,
                cbore=cbore,
                spotface=spotface,
            )
        )
    # Compose the injected countersinks: a coaxial cone flaring from the bore is
    # a hole attribute (like a counterbore), so it rides on the HoleRecord — HoleSpec
    # grouping and the callout-width estimate then see it for free. The caller injects the
    # inventory (package ADR 0002 — no sibling re-recognition here).
    if csinks:
        holes = [
            (replace(h, csink=cs) if (cs := _csink_for_hole(h, csinks)) is not None else h)
            for h in holes
        ]
    return holes


def recognise_bosses(part: Part, *, cyls: CylinderInventory | None = None) -> list[BossRecord]:
    """Recognise external cylindrical bosses on *part* (one
    :class:`BossRecord` per coaxial external cylinder segment, including a
    turned part's OD — callers wanting only local bosses can filter on
    diameter against the part envelope).

    Pass *cyls* — a precomputed ``analyse_cylinders(part)`` result — to avoid
    re-scanning the solid (mirrors ``recognise_holes``'s parameter, so a caller
    computing both holes and bosses can share one analysis).
    """
    z_cyls, cross_cyls = cyls if cyls is not None else analyse_cylinders(part)
    external = [c for c in _full_cyls(z_cyls) + _full_cyls(cross_cyls) if c["external"]]
    if not external:
        return []
    edge_faces = _edge_face_map(part)
    cache: dict = {}

    bosses = []
    for seg in _segments(external):
        d = seg["dir_xyz"]
        lo_state = _classify_end(seg, seg["s_lo"], False, edge_faces, cache)
        hi_state = _classify_end(seg, seg["s_hi"], True, edge_faces, cache)
        # The free end is the open one (its cap faces away from the segment);
        # default to the high end when both or neither are open.
        from_hi = not (lo_state == "open" and hi_state != "open")
        bosses.append(
            BossRecord(
                axis=_unit(d if from_hi else tuple(-c for c in d)),
                location=_axis_point(seg, seg["s_hi"] if from_hi else seg["s_lo"]),
                diameter=seg["diameter"],
                height=round(seg["s_hi"] - seg["s_lo"], 2),
            )
        )
    return bosses


def feature_diameters(
    part: Part,
    cyls: CylinderInventory | None = None,
    holes: Sequence[HoleRecord] | None = None,
    bosses: Sequence[BossRecord] | None = None,
) -> list[float]:
    """Sorted unique diameters of the *recognised* dimensionable cylindrical
    features on *part*: every hole bore, each hole's counterbore/spotface step,
    and every boss.

    This is the inventory to use for coverage checks ("is each dimensionable
    diameter called out?"). It is deliberately built from
    :func:`recognise_holes` / :func:`recognise_bosses`, not the raw :func:`full_cylinders`
    patch list, so partial cylinders that never become a real feature — slot ends and
    interrupted recesses (an exact half-cylinder pair sums to a full turn and
    fools an angle-only test, but is not a bore) — are excluded, while genuine
    counterbore/spotface steps are kept.

    Pass *cyls* — a precomputed ``analyse_cylinders(part)`` result — to share one
    scan between ``recognise_holes`` and ``recognise_bosses``. Pass *holes* — a precomputed
    ``recognise_holes`` result — to reuse the single feature inventory instead of
    re-detecting (the single-inventory rule).
    """
    cyls = analyse_cylinders(part) if cyls is None else cyls
    if holes is None:
        holes = recognise_holes(part, cyls=cyls)
    diams: list[float] = []
    for h in holes:
        diams.append(h.diameter)
        if h.cbore is not None:
            diams.append(h.cbore.diameter)
        if h.spotface is not None:
            diams.append(h.spotface.diameter)
    for b in recognise_bosses(part, cyls=cyls) if bosses is None else bosses:
        diams.append(b.diameter)
    return sorted(set(diams))


# Preserve the historical implementation-module path used by repr/pickle tooling.
for _record_type in (CounterBore, HoleRecord, BossRecord):
    _record_type.__module__ = "b123d_recognisers._features"
