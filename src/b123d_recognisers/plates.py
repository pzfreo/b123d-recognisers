# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Thin-slab (plate/wall) recognition for multi-plate prismatic parts.

``recognise_plates`` returns the plate/wall thicknesses of a prismatic part — the thin
extent of each slab that makes up an L-/T-/U-bracket and kin. It is the
complement of the other prismatic recognisers: ``recognise_face_levels`` (levels.py)
finds a monotonic Z staircase and ``EnvelopeFeature`` gives the overall bbox, but
neither recovers a *plate thickness* that is (a) along X or Y, or (b) along Z yet
too thin to survive the step-ladder legibility gate. A single flat plate needs no
help — its thickness IS the envelope, already dimensioned by ``dim_height``.

A plate along axis *a* is a slab of solid material between two large parallel
planar faces perpendicular to *a*: an **outward-−a** face at the low coord and an
**outward-+a** face at the high coord (solid lies between them). The opposite
arrangement — +a at the low coord, −a at the high — is a *slot / channel* with air
between the faces, and is correctly rejected. Two gates keep it to genuine plates:

- **large area** — each bounding face must cover at least ``min_area_frac`` of the
  part's cross-section on that axis, so a small internal feature face (a
  counterbore floor, a boss end) is never read as a plate; and
- **thin** — the thickness must be under ``max_thick_frac`` of the part's overall
  extent on that axis, so the full-envelope span of a single flat plate (thickness
  == extent) is excluded (``dim_height``/envelope already own it). A slab thicker
  than that fraction of its axis reads as a block, not a plate, and is left to the
  step/envelope dims — the conservative side of the cut.

Only the low−a/high+a *adjacent* pair along an axis is a plate: a pairing that skips
an intervening face crosses an air gap (two stacked plates on a common post) and is
rejected, so a slab thickness never spans a void.

Bottom of the recognition DAG: depends only on build123d/OCP.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.GeomAbs import GeomAbs_Plane
from OCP.GProp import GProp_GProps

from b123d_recognisers._geometry import (
    AXIS_ALIGNED_COS,
    clears_threshold,
    cluster_coordinates,
    resolved_tol,
)
from b123d_recognisers._record import Record
from b123d_recognisers._typing import Part

#: Coplanar-face grouping band, as a fraction of the part's largest extent (ADR 0008). The
#: fraction is the 0.5 mm default it replaces over the corpus's 70 mm median extent.
_TOL_FRAC = 0.00714


@dataclass(frozen=True)
class Plate(Record):
    """A recognised thin slab. ``axis`` is the thin (thickness) axis ("x"/"y"/"z");
    ``lo``/``hi`` are the slab's two bounding coords along it (``hi - lo`` is the
    thickness); ``u``/``v`` are the slab centre on the other two axes (in axis order),
    a representative point the renderer places the thickness dim beside."""

    axis: str
    lo: float
    hi: float
    u: float
    v: float

    @property
    def thickness(self) -> float:
        return self.hi - self.lo


def has_multi_axis_plates(plates: Sequence[Plate]) -> bool:
    """Whether plate evidence proves a base/wall structure rather than one slab axis."""
    return len({plate.axis for plate in plates}) >= 2


def recognise_plates(
    part: Part,
    *,
    min_area_frac: float = 0.4,
    max_thick_frac: float = 0.5,
    tol: float | None = None,
) -> list[Plate]:
    """Recognise the plate/wall thicknesses of a prismatic *part* (see module docstring).

    Returns one :class:`Plate` per recognised slab, deduplicated by (axis, lo, hi).
    Deterministic: sorted by (axis, lo, hi). Empty for a single flat plate (its
    thickness is the envelope) or a part with no thin slabs.
    """
    bb = part.bounding_box()
    tol = resolved_tol(tol, bb, rel=_TOL_FRAC)
    ext = {"x": bb.max.X - bb.min.X, "y": bb.max.Y - bb.min.Y, "z": bb.max.Z - bb.min.Z}
    axidx = {"x": 0, "y": 1, "z": 2}

    # Collect, per axis, the large planar faces perpendicular to it — bucketed by
    # coord and split by OUTWARD-normal sign. `.normal_at()` respects face
    # orientation (the raw OCC plane axis is always +, useless for inside/outside).
    faces = [f for f in part.faces() if BRepAdaptor_Surface(f.wrapped).GetType() == GeomAbs_Plane]

    out: list[Plate] = []
    for axis, i in axidx.items():
        cross = 1.0
        for o in axidx:
            if o != axis:
                cross *= ext[o]
        if cross <= 0:
            continue
        # Coplanar faces are gathered per outward-normal sign, then grouped by how far apart
        # their planes are rather than by which tol-wide grid cell they round into. The group's
        # coordinate is its lowest member's *actual* plane location: rounding to the grid put a
        # multiple of tol into Plate.lo/hi, so a slab's reported thickness was quantised to half
        # a millimetre by default.
        sides: tuple[list[tuple[float, float, float, float]], ...] = ([], [])
        oi = [j for j in (0, 1, 2) if j != i]  # the two in-plane axis indices
        for f in faces:
            s = BRepAdaptor_Surface(f.wrapped)
            try:
                nv = f.normal_at()
            except Exception:  # noqa: BLE001 — a degenerate face has no clean normal
                continue
            comp = (nv.X, nv.Y, nv.Z)[i]
            if abs(comp) < AXIS_ALIGNED_COS:
                continue
            props = GProp_GProps()
            BRepGProp.SurfaceProperties_s(f.wrapped, props)
            area = props.Mass()
            c = props.CentreOfMass()
            cp = (c.X(), c.Y(), c.Z())
            loc = (s.Plane().Location().X(), s.Plane().Location().Y(), s.Plane().Location().Z())[i]
            sides[comp > 0].append((loc, area, cp[oi[0]] * area, cp[oi[1]] * area))

        neg, pos = (
            {
                min(side[index][0] for index in group): [
                    sum(side[index][field] for index in group) for field in (1, 2, 3)
                ]
                for group in cluster_coordinates([entry[0] for entry in side], tol=tol)
            }
            for side in sides
        )

        thresh = min_area_frac * cross
        max_t = max_thick_frac * ext[axis]
        # A slab is a −a face IMMEDIATELY below a +a face with nothing between — solid
        # fills the gap. Sort all large faces along the axis and pair only *adjacent*
        # (−a, +a) neighbours: a −a low / +a high pairing that skips an intervening face
        # crosses an air gap (two stacked plates on a common post) and must not be read
        # as one plate. Same-coord ties order −a first so a degenerate pair is t≈0.
        events = [(c, -1, a, u, v) for c, (a, u, v) in neg.items() if clears_threshold(a, thresh)]
        events += [(c, 1, a, u, v) for c, (a, u, v) in pos.items() if clears_threshold(a, thresh)]
        events.sort(key=lambda e: (e[0], e[1]))
        for (c0, s0, a0, u0, v0), (c1, s1, a1, u1, v1) in zip(
            events, events[1:], strict=False
        ):
            if s0 != -1 or s1 != 1:
                continue
            t = c1 - c0
            if t <= tol or t >= max_t:
                continue
            # Slab centre on the two in-plane axes — area-weighted over both faces.
            aw = a0 + a1
            u = (u0 + u1) / aw
            v = (v0 + v1) / aw
            out.append(Plate(axis=axis, lo=round(c0, 3), hi=round(c1, 3), u=u, v=v))

    # Dedup by (axis, lo, hi); keep the first (deterministic) representative point.
    seen: set = set()
    uniq: list[Plate] = []
    for p in sorted(out, key=lambda p: (p.axis, p.lo, p.hi)):
        key = (p.axis, p.lo, p.hi)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq
