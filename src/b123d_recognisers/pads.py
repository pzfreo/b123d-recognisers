# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Recognition of bounded, axis-aligned rectangular raised pads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.GeomAbs import GeomAbs_Plane
from OCP.GProp import GProp_GProps

from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import EvidenceWriter
from b123d_recognisers._geometry import AXIS_ALIGNED_COS, AXIS_ZERO_COS
from b123d_recognisers._record import Record
from b123d_recognisers._typing import FaceLike, Part

#: **A minimum-evidence threshold, not a tolerance — deliberately absolute (ADR 0008).**
#: Scaling it to the part makes a feature's existence depend on what surrounds it, so a small
#: feature on a large part disappears. Whether such a feature is worth dimensioning is consumer
#: policy, and ADR 0001 puts policy with the consumer; recognition reports it either way.
#: Also the pad-footprint minimum on both in-plane axes.
_TOL = 0.2


@dataclass(frozen=True, order=True)
class RaisedPad(Record):
    """A bounded rectangular island, including its plan footprint and height."""

    x0: float
    x1: float
    y0: float
    y1: float
    z0: float
    z1: float


@dataclass(frozen=True, slots=True)
class _PadProposal:
    record: RaisedPad
    top_face: FaceLike
    wall_roles: tuple[tuple[FaceLike, ...], ...]


def _recognise_rectangular_pads_one(part, *, tol: float | None) -> list[_PadProposal]:
    """Recognise pads using one solid's faces and bounds."""
    bb = part.bounding_box()
    tol = _TOL if tol is None else tol
    raw_tops: list[tuple[float, float, float, float, float, FaceLike]] = []
    for face in part.faces():
        surf = BRepAdaptor_Surface(face.wrapped)
        if surf.GetType() != GeomAbs_Plane:
            continue
        try:
            normal = face.normal_at()
        except Exception:  # noqa: BLE001 - degenerate faces are not pads
            continue
        if normal.Z < AXIS_ALIGNED_COS:
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
                face,
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
        if abs(normal.Z) > AXIS_ZERO_COS:
            continue
        fb = face.bounding_box()
        vertical_faces.append((face, fb, normal))

    def wall_role(
        axis: str, pos: float, lo: float, hi: float, top: float
    ) -> tuple[float, tuple[FaceLike, ...]] | None:
        matches = []
        for face, fb, normal in vertical_faces:
            n_axis = abs(normal.X) if axis == "x" else abs(normal.Y)
            if n_axis < AXIS_ALIGNED_COS:
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
                matches.append((float(fb.min.Z), face))
        if not matches:
            return None
        base = max(item[0] for item in matches)
        return base, tuple(face for candidate_base, face in matches if candidate_base == base)

    proposals: list[_PadProposal] = []
    for x0, x1, y0, y1, z1, top_face in raw_tops:
        roles = (
            wall_role("x", x0, y0, y1, z1),
            wall_role("x", x1, y0, y1, z1),
            wall_role("y", y0, x0, x1, z1),
            wall_role("y", y1, x0, x1, z1),
        )
        if any(role is None for role in roles):
            continue
        complete_roles = tuple(role for role in roles if role is not None)
        numeric_bases = [role[0] for role in complete_roles]
        # A pad touching the part envelope may have one exterior wall merged all
        # the way to the stock base. The highest perimeter-wall base is the local
        # support plane; the other three walls still prove the bounded island.
        z0 = max(numeric_bases)
        proposals.append(
            _PadProposal(
                RaisedPad(x0, x1, y0, y1, round(z0, 3), z1),
                top_face,
                tuple(role[1] for role in complete_roles),
            )
        )

    # A tiered/staircase tower has rectangular ledges touching the candidate at its
    # recovered local base.  Lower ledges on a sloped support can touch the pad in plan
    # without belonging to that stack; comparing every different Z discarded the
    # real upper pad.  Disjoint pads may legitimately have any number of heights.
    def touches_plan(a: RaisedPad, b: RaisedPad) -> bool:
        return (
            min(a.x1, b.x1) - max(a.x0, b.x0) >= -tol and min(a.y1, b.y1) - max(a.y0, b.y0) >= -tol
        )

    raw_regions = [RaisedPad(x0, x1, y0, y1, z1, z1) for x0, x1, y0, y1, z1, _face in raw_tops]
    return [
        proposal
        for proposal in proposals
        if not any(
            abs(other.z1 - proposal.record.z0) <= tol and touches_plan(proposal.record, other)
            for other in raw_regions
        )
    ]


def recognise_rectangular_pads(part: Part, *, tol: float | None = None) -> list[RaisedPad]:
    """Return bounded rectangular raised faces independently per solid.

    A candidate is a planar +Z face whose area fills its XY bounding rectangle
    and is bounded on both in-plane axes. Full-span steps are excluded;
    non-rectangular pocket floors and perforated plate faces fail the area test.
    Body-local walls and bounds prevent a detached component from being treated
    as a pad raised from another component.
    """
    return _discover_rectangular_pads(part, tol=tol)


def _discover_rectangular_pads(
    part: Part,
    *,
    tol: float | None = None,
    writer: EvidenceWriter | None = None,
) -> list[RaisedPad]:
    """Shared rectangular-pad discovery with optional aggregate evidence issuance."""

    solids = list(part.solids())
    sources = solids if len(solids) > 1 else [part]
    occurrences: list[tuple[RaisedPad, tuple[_PadProposal, ...]]] = []
    for solid in sources:
        by_record: dict[RaisedPad, list[_PadProposal]] = {}
        for proposal in _recognise_rectangular_pads_one(solid, tol=tol):
            by_record.setdefault(proposal.record, []).append(proposal)
        occurrences.extend((record, tuple(group)) for record, group in by_record.items())
    occurrences.sort(key=lambda item: item[0])
    records = [record for record, _group in occurrences]
    if writer is None:
        return records

    pending: list[tuple[RaisedPad, tuple[Any, ...]]] = []
    used: set[Any] = set()
    for record, alternatives in occurrences:
        identity_signatures: list[tuple[Any, ...]] = []
        for proposal in alternatives:
            top = writer.graph.require_node(proposal.top_face)
            roles: list[Any] = []
            for faces in proposal.wall_roles:
                resolved = {writer.graph.require_node(face) for face in faces}
                if len(resolved) != 1:
                    raise ValueError("a Pad wall role has ambiguous maximal-base faces")
                roles.append(next(iter(resolved)))
            signature = (top, *roles)
            if len(set(signature)) != 5:
                raise ValueError("a Pad requires five pairwise-distinct defining faces")
            identity_signatures.append(signature)
        distinct = set(identity_signatures)
        if len(distinct) != 1:
            raise ValueError("equal Pad values have ambiguous defining occurrences")
        signature = next(iter(distinct))
        node_set = frozenset(signature)
        if used & node_set:
            raise ValueError("Pad occurrences share defining faces")
        ordered = tuple(node for node in writer.graph.nodes if node in node_set)
        if writer.graph.common_valid_solid(ordered) is None:
            raise ValueError("Pad defining faces do not belong to one valid solid")
        used.update(node_set)
        pending.append((record, ordered))
    for record, nodes in pending:
        writer.add_defining(record, nodes, family=FamilyId.PADS)
    return records
