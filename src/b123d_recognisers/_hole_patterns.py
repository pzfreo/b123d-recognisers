# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Hole-pattern records and derived recognition."""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from b123d_recognisers._hole_features import CounterBore, HoleRecord
from b123d_recognisers._pattern_geometry import (
    _PATTERN_ABS_TOL,
    _linear_array_candidates,
    _pattern_tol,
    _plane_uv,
    _rect_grid,
)
from b123d_recognisers._record import Record
from b123d_recognisers._typing import Vector3

_BC_SPACING_FRAC = 0.04


@dataclass(frozen=True)
class BoltCircle(Record):
    """≥3 identical holes equally spaced on a circle.

    ``center`` is the world point at the holes' opening plane, ``diameter``
    the bolt-circle diameter (BCD), ``holes`` the member features.
    """

    holes: tuple[HoleRecord, ...]
    center: Vector3
    diameter: float


@dataclass(frozen=True)
class LinearArray(Record):
    """≥3 identical holes collinear at constant pitch.

    ``direction`` is the unit vector from the first hole toward the last
    (members are ordered along it).
    """

    holes: tuple[HoleRecord, ...]
    pitch: float
    direction: Vector3


@dataclass(frozen=True)
class RectGrid(Record):
    """A fully-populated rectangular grid of identical holes (an N×M lattice).

    ``rows``×``cols`` holes sit on a regular rectangular lattice; every lattice
    position is occupied (``rows * cols == len(holes)``). ``center`` is the world
    point at the grid centroid (opening plane).

    The serialized lattice convention is self-contained: **columns** are spaced
    ``col_pitch`` apart along the lattice's first basis direction and **rows**
    ``row_pitch`` apart along the second, and ``angle`` is the COLUMN direction's
    orientation in degrees within the holes' opening plane, measured in the
    :func:`b123d_recognisers._geometry.plane_axes` frame and normalised to ``[0, 180)``.

    ``[0, 180)`` and not ``[0, 90)``: the lattice is unchanged by a half-turn (its
    cell set is symmetric about ``center``, so the basis sign carries no
    information) but a QUARTER-turn swaps rows for columns, which these fields
    distinguish. Note the first basis is the SHORTEST pairwise vector rather than
    anything world-aligned, so a grid may legitimately come back with its rows and
    columns named the other way round — what is fixed is that each count keeps its
    own pitch, and that the fields describe the same lattice.

    A rectangular *ring* / perimeter (holes only around the edge, interior
    empty) is not a grid — it is reported as its constituent edge
    :class:`LinearArray` rows instead.
    """

    holes: tuple[HoleRecord, ...]
    rows: int
    cols: int
    row_pitch: float
    col_pitch: float
    angle: float
    center: Vector3


@dataclass(frozen=True)
class HoleSpec(Record):
    """The machining spec shared by holes that are the *same drilled feature*.

    Two holes drilled with the same tool, in the same direction, with the same
    counterbore/spotface stack have equal :class:`HoleSpec` values (a through
    drill is the same spec whatever wall it pierces). Because the dataclass is
    frozen it hashes and compares by value, so it is a stable dict/set key for
    grouping holes — pattern detection and callout grouping agree when they key
    on the same :class:`HoleSpec`.

    Build one with :meth:`from_hole`; do not construct the fields by hand (the
    normalisation in :meth:`from_hole` is part of the contract). ``axis`` is the
    drilling direction snapped to 6 dp (boolean ops leave ~1e-16 noise on the
    components, and exact float keys would split a pattern silently). ``depth``
    is ``None`` for a through hole — its depth is irrelevant to the spec —
    otherwise the bore depth. Public and stable for downstream consumers.
    """

    axis: Vector3
    diameter: float
    depth: float | None
    bottom: str
    cbore: CounterBore | None
    spotface: CounterBore | None
    # The countersink's *size* only — ``(major_diameter, included_angle)`` — never its
    # location, so identical countersunk holes at different positions share one spec.
    csink: tuple[float, float] | None = None

    @classmethod
    def from_hole(cls, hole: HoleRecord) -> "HoleSpec":
        """The :class:`HoleSpec` for *hole* (a :class:`HoleRecord`)."""
        depth = None if hole.bottom == "through" else hole.depth
        axis = tuple(0.0 if abs(c) < 1e-6 else round(c, 6) for c in hole.axis)
        csink = (hole.csink.major_diameter, hole.csink.included_angle) if hole.csink else None
        return cls(
            (axis[0], axis[1], axis[2]),
            hole.diameter,
            depth,
            hole.bottom,
            hole.cbore,
            hole.spotface,
            csink,
        )


def _spec_key(h) -> HoleSpec:
    return HoleSpec.from_hole(h)


def _as_bolt_circle(holes, pts) -> BoltCircle | None:
    """BoltCircle when *pts* (2D) are equally spaced on a common circle."""
    n = len(pts)
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    radii = [math.hypot(p[0] - cx, p[1] - cy) for p in pts]
    r = sum(radii) / n
    if r < _PATTERN_ABS_TOL or max(abs(ri - r) for ri in radii) > _pattern_tol(r):
        return None
    angles = sorted(math.atan2(p[1] - cy, p[0] - cx) for p in pts)
    gaps = [angles[i + 1] - angles[i] for i in range(n - 1)]
    gaps.append(2 * math.pi - (angles[-1] - angles[0]))
    even = 2 * math.pi / n
    if max(abs(g - even) for g in gaps) > _BC_SPACING_FRAC * even:
        return None
    center = tuple(sum(c) / n for c in zip(*(h.location for h in holes), strict=True))
    return BoltCircle(holes=tuple(holes), center=center, diameter=round(2 * r, 2))


def _circumcircle(p0, p1, p2) -> tuple[float, float, float] | None:
    """Centre and radius ``(cx, cy, r)`` of the circle through three 2D points,
    or ``None`` when they are collinear (so a collinear triple can never seed a
    bolt circle — collinearity must win, per :func:`recognise_hole_patterns`)."""
    ax, ay = p0
    bx, by = p1
    cx, cy = p2
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-9:
        return None
    a2, b2, c2 = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    ux = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d
    uy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d
    return ux, uy, math.hypot(ax - ux, ay - uy)


def _bolt_circle_candidates(members, pts) -> list[tuple[BoltCircle, frozenset[int]]]:
    """All bolt circles within a spec group: every triple seeds a candidate
    circle, the group's points lying on it are gathered, and the set is kept
    only if :func:`_as_bolt_circle` confirms it is fully, evenly populated.
    Returns ``(BoltCircle, frozenset(member indices))`` candidates."""
    n = len(pts)
    out, seen = [], set()
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                circ = _circumcircle(pts[i], pts[j], pts[k])
                if circ is None:
                    continue
                cx, cy, r = circ
                if r < _PATTERN_ABS_TOL:
                    continue
                key = (round(cx, 2), round(cy, 2), round(r, 2))
                if key in seen:
                    continue
                seen.add(key)
                tol = _pattern_tol(r)
                idx = [
                    m
                    for m in range(n)
                    if abs(math.hypot(pts[m][0] - cx, pts[m][1] - cy) - r) <= tol
                ]
                if len(idx) < 3:
                    continue
                pat = _as_bolt_circle([members[m] for m in idx], [pts[m] for m in idx])
                if pat is not None:
                    out.append((pat, frozenset(idx)))
    return out


def _mk_hole_linear(members, pitch, direction) -> LinearArray:
    return LinearArray(holes=tuple(members), pitch=pitch, direction=direction)


def _mk_hole_grid(members, rows, cols, row_pitch, col_pitch, angle, center) -> RectGrid:
    return RectGrid(
        holes=tuple(members),
        rows=rows,
        cols=cols,
        row_pitch=row_pitch,
        col_pitch=col_pitch,
        angle=angle,
        center=center,
    )


def recognise_hole_patterns(
    holes: Sequence[HoleRecord],
) -> list[BoltCircle | LinearArray | RectGrid]:
    """Recognise :class:`BoltCircle`, :class:`LinearArray`, and
    :class:`RectGrid` patterns among *holes* (``HoleRecord`` records, e.g.
    from :func:`recognise_holes`).

    Holes are grouped by machining spec and drilling axis, then each group is
    *sub-clustered* — a single spec can contribute several patterns (two
    separate bolt circles, the rows of a rectangular perimeter, a grid). All
    candidate sub-patterns are enumerated and allocated greedily largest-first,
    so each hole belongs to at most one pattern and the richest interpretation
    wins. Precedence is deterministic: a full grid claims its complete same-spec group first;
    remaining candidates sort by member count with stable family order. A filled N×M lattice
    becomes one :class:`RectGrid`; a rectangular
    ring or perimeter is reported as its edge :class:`LinearArray` rows.

    Collinearity is tested ahead of concyclicity (any three points are
    concyclic, so a 3-hole "bolt circle" must really be an equilateral
    triangle); unpatterned holes are simply absent from the result.
    """
    groups: dict = {}
    for h in holes:
        groups.setdefault(_spec_key(h), []).append(h)

    patterns: list[BoltCircle | LinearArray | RectGrid] = []
    for spec, members in groups.items():
        if len(members) < 3:
            continue
        u, v = _plane_uv(spec.axis)
        pts = [
            (
                sum(a * b for a, b in zip(h.location, u, strict=True)),
                sum(a * b for a, b in zip(h.location, v, strict=True)),
            )
            for h in members
        ]
        grid = _rect_grid(members, pts, _mk_hole_grid)
        if grid is not None:
            # `_rect_grid` succeeds only when this entire same-spec group fills one
            # lattice. The grid therefore claims every member, sorts ahead of every
            # equal-sized candidate, and makes all circle/linear candidates impossible
            # to allocate. Return it now instead of doing O(n^4) work whose results are
            # guaranteed to be discarded.
            patterns.append(grid)
            continue
        candidates: list = []
        candidates += _bolt_circle_candidates(members, pts)
        candidates += _linear_array_candidates(members, pts, _mk_hole_linear)
        # allocate largest-first; a hole used by one pattern is off the table
        # for the rest (stable sort keeps grids ahead of circles ahead of rows
        # at equal size)
        candidates.sort(key=lambda c: -len(c[1]))
        used: set = set()
        for pattern, idx in candidates:
            if idx & used:
                continue
            patterns.append(pattern)
            used |= idx
    return patterns


# Preserve the historical implementation-module path used by repr/pickle tooling.
for _record_type in (BoltCircle, LinearArray, RectGrid, HoleSpec):
    _record_type.__module__ = "b123d_recognisers._features"
