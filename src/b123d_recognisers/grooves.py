# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Turned/circlip-groove recognition on round stock.

A *groove* is an annular channel turned into round stock — a circlip / retaining-ring
groove, an O-ring groove, a run-out relief. It reads as a *narrow* band of the OD whose diameter
is a **strict local minimum**: smaller than the contiguous bands on *both* axial sides,
bounded by the two annular walls where the OD steps down then up again. It is a channel cut in
uniform stock — the two walls step back to the **same OD**, and the band is **narrower than the
wider wall** (not a segment of an alternating fine-step staircase). It is dimensioned
by its **width** (the axial span) and its **floor diameter** — not as a slot (whose walls
are rectangular / radial, so :func:`recognise_slots` rejects it) and not as a plain step
(a *monotonic* OD change, one wall, handled by :func:`recognise_turned_steps`).

The recognition is definitive from :func:`analyse_cylinders`. The two annular walls a groove
must have are implied by the band structure — a smaller band contiguous with a larger band
on each side *is* a step-down then a step-up — so no separate wall-face search is needed, and
the corner fillets/chamfers a real groove carries are tori / cones (never cylinders), so they
never appear as spurious bands. They do, however, sit *between* the bands: a **chamfered**
lead-in is read as the join it is (see :func:`_joined`), because the manufactured groove
usually has one where the textbook drawing shows a sharp corner. A **radiused** lead-in is a
torus and is not read, so it remains outside the proven scope. ``width`` is the flat floor
either way — what an O-ring or circlip seat is dimensioned by — never the wider opening the
chamfers cut. Bands are grouped by axis **line** (not merely the axis letter) so two lone
grooves on distinct parallel shafts are never confused for one channel. Bottom of the
recognition DAG: depends on no other recogniser — the owned ``analyse_cylinders`` primitive
plus its own read of the part's conical faces.
"""

from __future__ import annotations

from dataclasses import dataclass

from build123d import GeomType

from b123d_recognisers._features import analyse_cylinders
from b123d_recognisers._geometry import length_tol
from b123d_recognisers._record import Record
from b123d_recognisers._typing import CylinderInventory, FaceLike, Part

#: A conical face as ``(axis direction, ((rim centre, rim radius), ...))``.
ConeJoin = tuple[
    tuple[float, float, float], tuple[tuple[tuple[float, float, float], float], ...]
]

# Every gate below is a fraction of the band it judges, per ADR 0008: a groove in 5 mm bar and
# the same groove in 500 mm bar are the same feature, and only a proportional gate says so.
# Each fraction is the millimetre constant it replaces divided by the reference size the corpus
# calibrates against — 8 mm for a diameter, 10 mm for an axial width.
#
# Two bands are axially contiguous (one is the other's wall) when the gap between them is
# within this fraction of the band diameter — a tolerance, so it follows the band.
_ADJ_FRAC = 0.0125
# A neighbour must be wider than the floor by more than this (mm of diameter) to count as a step
# up out of the groove. A **minimum-evidence threshold**, so absolute per ADR 0008: as a fraction
# of the wall it demanded a proportionally deeper groove on bigger stock, and a 2 mm groove found
# on a 15 mm shaft vanished on a 100 mm one.
_DIA_MARGIN = 0.2
# A groove is a *narrow channel* cut into UNIFORM stock. Two signatures separate it from a
# segment of an alternating fine-step staircase:
#  - its two walls step back to (nearly) the same OD — within this fraction of the wider wall.
#    Unequal walls are a stepped profile (a shoulder), not a channel in round bar.
_WALL_DIA_FRAC = 0.0625
#  - it is narrower than the WIDER of its two walls, by more than this (mm). A band as wide as
#    its walls is a staircase step; an end-adjacent groove keeps one wide wall (the shaft
#    continues) even when the other is a thin retaining land, so the *wider* wall is the test.
#    Also a minimum-evidence threshold, so also absolute.
_WIDTH_MARGIN = 0.05


def _cone_joins(part: Part) -> list[ConeJoin]:
    """Every conical face as its axis direction plus its circular rims.

    Read once per part so :func:`_joined` can test a lead-in chamfer rather than assume the
    groove's bands touch."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    joins: list[ConeJoin] = []
    for face in part.faces().filter_by(GeomType.CONE):
        circles = face.edges().filter_by(GeomType.CIRCLE)
        if len(circles) < 2:
            continue  # a drill-point cone is one circle and an apex: it joins nothing
        direction = BRepAdaptor_Surface(face.wrapped).Cone().Axis().Direction()
        rims = tuple(
            ((c.arc_center.X, c.arc_center.Y, c.arc_center.Z), c.radius) for c in circles
        )
        joins.append(((direction.X(), direction.Y(), direction.Z()), rims))
    return joins


def _joined(lower, upper, tol: float, cones: list[ConeJoin]) -> bool:
    """Whether *upper* follows *lower* along the shaft.

    Directly, when the two bands touch; or across a **conical lead-in** — the chamfer a
    manufactured groove usually carries where the textbook drawing shows a sharp corner.

    The cone has to land on both rims: its narrow end on one band's edge at that band's
    diameter, its wide end on the other's. That makes the allowance self-limiting — a taper
    that merely passes nearby, or that runs on to some third diameter, joins nothing — so
    there is no separate "how much cone counts as a lead-in" gate to calibrate.
    """
    if abs(lower["s_hi"] - upper["s_lo"]) <= tol:
        return True
    axis = lower["dir_xyz"]
    for direction, rims in cones:
        if abs(sum(direction[i] * axis[i] for i in range(3))) < 1 - 1e-6:
            continue  # not coaxial with this shaft
        ends = sorted(
            (sum(centre[i] * axis[i] for i in range(3)), radius) for centre, radius in rims
        )
        (s_lo, r_lo), (s_hi, r_hi) = ends[0], ends[-1]
        if (
            abs(s_lo - lower["s_hi"]) <= tol
            and abs(s_hi - upper["s_lo"]) <= tol
            and abs(2 * r_lo - lower["diameter"]) <= tol
            and abs(2 * r_hi - upper["diameter"]) <= tol
        ):
            return True
    return False


def _shaft_key(c) -> tuple:
    """The axis line a band is turned about: the axis letter plus the axis point projected
    onto the plane perpendicular to the axis direction (position-independent along the axis),
    plus the owning solid. Bands with the same key are coaxial on one shaft; distinct parallel
    shafts differ, and — like the sibling ``_line_key`` — coaxial bands in *separate*
    butted solids stay distinct so three stacked bodies are never misread as one channel."""
    px, py, pz = c["axis_xyz"]
    dx, dy, dz = c["dir_xyz"]
    t = px * dx + py * dy + pz * dz
    return (
        c["axis"],
        c["solid_idx"],
        round(px - t * dx, 2),
        round(py - t * dy, 2),
        round(pz - t * dz, 2),
    )


@dataclass(frozen=True)
class Groove(Record):
    """A recognised turned / circlip groove on round stock. ``axis`` is the turning axis the
    stock is coaxial about ("x"/"y"/"z"); ``width`` is the groove's axial span (wall to
    wall); ``diameter`` is the floor (reduced-OD) diameter; ``at`` is the groove centre on
    the axis (the callout leader's tip)."""

    axis: str
    width: float
    diameter: float
    at: tuple[float, float, float]


def floor_face_anchor(face: FaceLike) -> tuple[float, float, float]:
    """The groove leader-tip anchor: the **bbox centre** of the floor face (the reduced-OD
    band), unrounded. The one anchor contract shared by :func:`recognise_grooves` and the
    explicit-face reader — the substrates differ
    (band dicts from ``analyse_cylinders`` vs a single user-supplied face), but the leader
    tip must not."""
    bb = face.bounding_box()
    return (
        0.5 * (bb.min.X + bb.max.X),
        0.5 * (bb.min.Y + bb.max.Y),
        0.5 * (bb.min.Z + bb.max.Z),
    )


def recognise_grooves(
    part: Part, *, cyls: CylinderInventory | None = None
) -> list[Groove]:
    """Recognise the turned grooves of *part* (see module docstring). Returns one
    :class:`Groove` per external band whose OD is a strict local minimum between two
    contiguous larger bands on the same shaft, sorted deterministically. Empty when the
    part has no round stock or no groove.

    Pass *cyls* — a precomputed ``analyse_cylinders(part)`` result — to avoid
    re-scanning the solid, matching the dependency-injection contract of
    :func:`recognise_holes`."""
    z_cyls, cross_cyls = cyls if cyls is not None else analyse_cylinders(part)
    ext = [c for c in (*z_cyls, *cross_cyls) if c.get("external")]
    if not ext:
        return []

    shafts: dict[tuple, list] = {}
    for c in ext:
        shafts.setdefault(_shaft_key(c), []).append(c)

    cones = _cone_joins(part)
    out: list[Groove] = []
    for bands in shafts.values():
        bands = sorted(bands, key=lambda c: c["s_lo"])
        for i in range(1, len(bands) - 1):
            prev, cur, nxt = bands[i - 1], bands[i], bands[i + 1]
            # The neighbours must be the groove's own walls — contiguous with the floor band,
            # or reaching it across the lead-in chamfer a manufactured groove usually carries.
            adj_tol = length_tol(cur["diameter"], rel=_ADJ_FRAC)
            if not _joined(prev, cur, adj_tol, cones):
                continue
            if not _joined(cur, nxt, adj_tol, cones):
                continue
            # A strict local OD minimum: the OD steps *down* into the band and *up* out of it.
            # A monotonic change (a plain step / shoulder) fails one side and is not a groove.
            if cur["diameter"] > prev["diameter"] - _DIA_MARGIN:
                continue
            if cur["diameter"] > nxt["diameter"] - _DIA_MARGIN:
                continue
            # Cut into uniform stock: the two walls step back to (nearly) the same OD. Unequal
            # walls are a shoulder / stepped profile, not an annular channel.
            wider_dia = max(prev["diameter"], nxt["diameter"])
            if abs(prev["diameter"] - nxt["diameter"]) > length_tol(
                wider_dia, rel=_WALL_DIA_FRAC
            ):
                continue
            # A narrow channel: narrower than the WIDER of its two walls. A band as wide as its
            # walls is a staircase step; an end-adjacent groove keeps one wide
            # wall (the shaft) even when the other is a thin retaining land, so test the wider.
            cur_w = cur["s_hi"] - cur["s_lo"]
            wider_wall = max(prev["s_hi"] - prev["s_lo"], nxt["s_hi"] - nxt["s_lo"])
            if cur_w >= wider_wall - _WIDTH_MARGIN:
                continue
            cx, cy, cz = floor_face_anchor(cur["face"])
            at = (round(cx, 3), round(cy, 3), round(cz, 3))
            out.append(
                Groove(
                    axis=cur["axis"],
                    width=round(cur["s_hi"] - cur["s_lo"], 3),
                    diameter=round(cur["diameter"], 3),
                    at=at,
                )
            )
    return sorted(out, key=lambda g: (g.axis, g.at))
