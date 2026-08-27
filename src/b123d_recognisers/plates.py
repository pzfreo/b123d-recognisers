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

from build123d import Face
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.GeomAbs import GeomAbs_Plane
from OCP.GProp import GProp_GProps

from b123d_recognisers._adjacency import FaceNode, SolidRef
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import EvidenceWriter
from b123d_recognisers._geometry import (
    AXIS_ALIGNED_COS,
    clears_threshold,
    cluster_coordinates,
)
from b123d_recognisers._record import Record
from b123d_recognisers._typing import Part

#: **A minimum-evidence threshold, not a tolerance — deliberately absolute (ADR 0008).**
#: Scaling it to the part makes a feature's existence depend on what surrounds it, so a small
#: feature on a large part disappears. Whether such a feature is worth dimensioning is consumer
#: policy, and ADR 0001 puts policy with the consumer; recognition reports it either way.
#: Also the slab-thickness minimum, which is why it cannot follow the part.
_TOL = 0.5


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


class _PlateAttributionError(ValueError):
    """Complete Plate provenance cannot be published for this aggregate input."""


@dataclass(frozen=True, slots=True)
class _PlateProposal:
    record: Plate
    low_faces: tuple[Face, ...]
    high_faces: tuple[Face, ...]


@dataclass(frozen=True, slots=True)
class _PlateGroup:
    area: float
    u_sum: float
    v_sum: float
    faces: tuple[Face, ...]


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
    return _discover_plates(
        part,
        min_area_frac=min_area_frac,
        max_thick_frac=max_thick_frac,
        tol=tol,
    )


def _discover_plates(
    part: Part,
    *,
    min_area_frac: float = 0.4,
    max_thick_frac: float = 0.5,
    tol: float | None = None,
    writer: EvidenceWriter | None = None,
) -> list[Plate]:
    """Discover Plates and optionally issue complete low/high planar groups atomically."""

    bb = part.bounding_box()
    tol = _TOL if tol is None else tol
    ext = {"x": bb.max.X - bb.min.X, "y": bb.max.Y - bb.min.Y, "z": bb.max.Z - bb.min.Z}
    axidx = {"x": 0, "y": 1, "z": 2}

    # Collect, per axis, the large planar faces perpendicular to it — bucketed by
    # coord and split by OUTWARD-normal sign. `.normal_at()` respects face
    # orientation (the raw OCC plane axis is always +, useless for inside/outside).
    faces = [f for f in part.faces() if BRepAdaptor_Surface(f.wrapped).GetType() == GeomAbs_Plane]

    out: list[_PlateProposal] = []
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
        sides: tuple[list[tuple[float, float, float, float, Face]], ...] = ([], [])
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
            sides[comp > 0].append((loc, area, cp[oi[0]] * area, cp[oi[1]] * area, f))

        grouped: list[dict[float, _PlateGroup]] = []
        for side in sides:
            groups: dict[float, _PlateGroup] = {}
            for cluster in cluster_coordinates([entry[0] for entry in side], tol=tol):
                groups[min(side[index][0] for index in cluster)] = _PlateGroup(
                    sum(side[index][1] for index in cluster),
                    sum(side[index][2] for index in cluster),
                    sum(side[index][3] for index in cluster),
                    tuple(side[index][4] for index in cluster),
                )
            grouped.append(groups)
        neg, pos = grouped

        thresh = min_area_frac * cross
        max_t = max_thick_frac * ext[axis]
        # A slab is a −a face IMMEDIATELY below a +a face with nothing between — solid
        # fills the gap. Sort all large faces along the axis and pair only *adjacent*
        # (−a, +a) neighbours: a −a low / +a high pairing that skips an intervening face
        # crosses an air gap (two stacked plates on a common post) and must not be read
        # as one plate. Same-coord ties order −a first so a degenerate pair is t≈0.
        events = [
            (c, -1, group) for c, group in neg.items() if clears_threshold(group.area, thresh)
        ]
        events += [
            (c, 1, group) for c, group in pos.items() if clears_threshold(group.area, thresh)
        ]
        events.sort(key=lambda e: (e[0], e[1]))
        for (c0, s0, group0), (c1, s1, group1) in zip(events, events[1:], strict=False):
            if s0 != -1 or s1 != 1:
                continue
            t = c1 - c0
            if t <= tol or t >= max_t:
                continue
            # Slab centre on the two in-plane axes — area-weighted over both faces.
            aw = group0.area + group1.area
            u = (group0.u_sum + group1.u_sum) / aw
            v = (group0.v_sum + group1.v_sum) / aw
            out.append(
                _PlateProposal(
                    Plate(axis=axis, lo=round(c0, 3), hi=round(c1, 3), u=u, v=v),
                    group0.faces,
                    group1.faces,
                )
            )

    ordered = sorted(out, key=lambda p: (p.record.axis, p.record.lo, p.record.hi))
    if writer is None:
        # Public geometry-only compatibility remains value-deduplicated.  Attribution cannot
        # make that choice until the graph has resolved wrappers to original topology identity.
        seen: set[tuple[str, float, float]] = set()
        uniq = []
        for proposal in ordered:
            key = (proposal.record.axis, proposal.record.lo, proposal.record.hi)
            if key not in seen:
                seen.add(key)
                uniq.append(proposal)
    else:
        bound: dict[
            tuple[str, float, float],
            dict[tuple[frozenset[FaceNode], frozenset[FaceNode]], _PlateProposal],
        ] = {}
        used: set[FaceNode] = set()
        try:
            for proposal in ordered:
                low = frozenset(writer.graph.require_node(face) for face in proposal.low_faces)
                high = frozenset(writer.graph.require_node(face) for face in proposal.high_faces)
                if not low or not high or low & high:
                    raise _PlateAttributionError("Plate role groups are empty or overlap")
                low_by_solid: dict[SolidRef, set[FaceNode]] = {}
                high_by_solid: dict[SolidRef, set[FaceNode]] = {}
                for role, owner_groups in ((low, low_by_solid), (high, high_by_solid)):
                    for node in role:
                        solid = writer.graph.common_valid_solid((node,))
                        if solid is None:
                            raise _PlateAttributionError(
                                "Plate role face has no unambiguous valid solid"
                            )
                        owner_groups.setdefault(solid, set()).add(node)
                shared_solids = low_by_solid.keys() & high_by_solid.keys()
                if len(shared_solids) != 1:
                    raise _PlateAttributionError(
                        "Plate role groups do not identify one common solid"
                    )
                solid = next(iter(shared_solids))
                low = frozenset(low_by_solid[solid])
                high = frozenset(high_by_solid[solid])
                key = (proposal.record.axis, proposal.record.lo, proposal.record.hi)
                bound.setdefault(key, {}).setdefault((low, high), proposal)
            if any(len(role_pairs) > 1 for role_pairs in bound.values()):
                raise _PlateAttributionError("Plate key has competing defining groups")

            pending: list[tuple[Plate, tuple[FaceNode, ...]]] = []
            uniq = []
            for role_pairs in bound.values():
                (low, high), proposal = next(iter(role_pairs.items()))
                resolved = low | high
                nodes = tuple(node for node in writer.graph.nodes if node in resolved)
                if used & resolved:
                    raise _PlateAttributionError("Plate occurrences reuse defining faces")
                if writer.graph.common_valid_solid(nodes) is None:
                    raise _PlateAttributionError(
                        "Plate defining groups do not prove one valid solid"
                    )
                used.update(resolved)
                pending.append((proposal.record, nodes))
                uniq.append(proposal)
        except _PlateAttributionError:
            raise
        except (KeyError, RuntimeError, ValueError) as exc:
            raise _PlateAttributionError("Plate face binding failed") from exc
        for record, nodes in pending:
            writer.add_defining(record, nodes, family=FamilyId.PLATES)
    return [proposal.record for proposal in uniq]
