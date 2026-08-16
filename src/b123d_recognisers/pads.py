# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Recognition of bounded, axis-aligned rectangular raised pads."""

from __future__ import annotations

from dataclasses import dataclass

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.GeomAbs import GeomAbs_Plane
from OCP.GProp import GProp_GProps

from b123d_recognisers._geometry import resolved_tol
from b123d_recognisers._record import Record
from b123d_recognisers._typing import Part

#: Face/bound coincidence band, as a fraction of the owning solid's largest extent (ADR 0008).
#: Derived per solid, not per assembly, so a small component in a large assembly is judged by
#: its own size. The fraction is the 0.2 mm default it replaces over the corpus's 70 mm median.
_TOL_FRAC = 0.00286


@dataclass(frozen=True, order=True)
class RaisedPad(Record):
    """A bounded rectangular island, including its plan footprint and height."""

    x0: float
    x1: float
    y0: float
    y1: float
    z0: float
    z1: float


def _recognise_rectangular_pads_one(part, *, tol: float | None) -> list[RaisedPad]:
    """Recognise pads using one solid's faces and bounds."""
    bb = part.bounding_box()
    tol = resolved_tol(tol, bb, rel=_TOL_FRAC)
    raw_tops: list[tuple[float, float, float, float, float]] = []
    for face in part.faces():
        surf = BRepAdaptor_Surface(face.wrapped)
        if surf.GetType() != GeomAbs_Plane:
            continue
        try:
            normal = face.normal_at()
        except Exception:  # noqa: BLE001 - degenerate faces are not pads
            continue
        if normal.Z < 0.99:
            continue
        fb = face.bounding_box()
        dx = fb.max.X - fb.min.X
        dy = fb.max.Y - fb.min.Y
        if dx <= tol or dy <= tol or bb.min.Z + tol >= fb.max.Z:
            continue
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face.wrapped, props)
        if abs(props.Mass() - dx * dy) > max(tol * tol, 0.005 * dx * dy):
            continue
        full_x = bb.min.X + tol >= fb.min.X and bb.max.X - tol <= fb.max.X
        full_y = bb.min.Y + tol >= fb.min.Y and bb.max.Y - tol <= fb.max.Y
        if full_x or full_y:
            continue
        raw_tops.append(
            (
                round(fb.min.X, 3),
                round(fb.max.X, 3),
                round(fb.min.Y, 3),
                round(fb.max.Y, 3),
                round(fb.max.Z, 3),
            )
        )

    # Recover each pad's base from its own four downward perimeter walls. A
    # part-global "highest horizontal level below the top" is wrong when another
    # feature has an unrelated intervening Z level.
    vertical_faces = []
    for face in part.faces():
        surf = BRepAdaptor_Surface(face.wrapped)
        if surf.GetType() != GeomAbs_Plane:
            continue
        try:
            normal = face.normal_at()
        except Exception:  # noqa: BLE001 - degenerate faces cannot bound a pad
            continue
        if abs(normal.Z) > 0.01:
            continue
        fb = face.bounding_box()
        vertical_faces.append((fb, normal))

    def wall_base(axis: str, pos: float, lo: float, hi: float, top: float) -> float | None:
        bases = []
        for fb, normal in vertical_faces:
            n_axis = abs(normal.X) if axis == "x" else abs(normal.Y)
            if n_axis < 0.99:
                continue
            plane_pos = (fb.min.X + fb.max.X) / 2 if axis == "x" else (fb.min.Y + fb.max.Y) / 2
            cross_lo = fb.min.Y if axis == "x" else fb.min.X
            cross_hi = fb.max.Y if axis == "x" else fb.max.X
            if (
                abs(plane_pos - pos) <= tol
                and abs(fb.max.Z - top) <= tol
                and top - tol > fb.min.Z
                and cross_lo <= lo + tol
                and cross_hi >= hi - tol
            ):
                bases.append(float(fb.min.Z))
        return max(bases) if bases else None

    out: set[RaisedPad] = set()
    for x0, x1, y0, y1, z1 in raw_tops:
        bases = (
            wall_base("x", x0, y0, y1, z1),
            wall_base("x", x1, y0, y1, z1),
            wall_base("y", y0, x0, x1, z1),
            wall_base("y", y1, x0, x1, z1),
        )
        if any(base is None for base in bases):
            continue
        numeric_bases = [float(base) for base in bases if base is not None]
        # A pad touching the part envelope may have one exterior wall merged all
        # the way to the stock base. The highest perimeter-wall base is the local
        # support plane; the other three walls still prove the bounded island.
        z0 = max(numeric_bases)
        out.add(RaisedPad(x0, x1, y0, y1, round(z0, 3), z1))

    # A tiered/staircase tower has rectangular ledges touching the candidate at its
    # recovered local base.  Lower ledges on a sloped support can touch the pad in plan
    # without belonging to that stack; comparing every different Z discarded the
    # real upper pad.  Disjoint pads may legitimately have any number of heights.
    def touches_plan(a: RaisedPad, b: RaisedPad) -> bool:
        return (
            min(a.x1, b.x1) - max(a.x0, b.x0) >= -tol and min(a.y1, b.y1) - max(a.y0, b.y0) >= -tol
        )

    raw_regions = [RaisedPad(x0, x1, y0, y1, z1, z1) for x0, x1, y0, y1, z1 in raw_tops]
    return sorted(
        pad
        for pad in out
        if not any(
            abs(other.z1 - pad.z0) <= tol and touches_plan(pad, other) for other in raw_regions
        )
    )


def recognise_rectangular_pads(part: Part, *, tol: float | None = None) -> list[RaisedPad]:
    """Return bounded rectangular raised faces independently per solid.

    A candidate is a planar +Z face whose area fills its XY bounding rectangle
    and is bounded on both in-plane axes. Full-span steps are excluded;
    non-rectangular pocket floors and perforated plate faces fail the area test.
    Body-local walls and bounds prevent a detached component from being treated
    as a pad raised from another component.
    """
    solids = list(part.solids())
    sources = solids if len(solids) > 1 else [part]
    pads = [pad for solid in sources for pad in _recognise_rectangular_pads_one(solid, tol=tol)]
    return sorted(pads)
