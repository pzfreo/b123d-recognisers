# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Recognition of bounded, axis-aligned rectangular raised pads."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any

from build123d import Vector
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

from b123d_recognisers._analytic_surfaces import SurfaceKind
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import EvidenceWriter
from b123d_recognisers._effective_surfaces import (
    AnalyticSurfaceFact,
    EffectiveFaceSurfaceQuery,
    SurfaceUse,
    SurfaceUseRefusal,
    effective_faces_for_graph,
    effective_faces_for_part,
)
from b123d_recognisers._geometry import AXIS_ALIGNED_COS, AXIS_ZERO_COS
from b123d_recognisers._record import Record
from b123d_recognisers._typing import FaceLike, Part
from b123d_recognisers.experimental_geometry import (
    AnalyticSurface,
    BlendFact,
    FaceRef,
    GeometryGraph,
)
from b123d_recognisers.experimental_geometry import SurfaceKind as InspectionSurfaceKind

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


def _wall_role(
    vertical_faces: list[tuple[FaceLike, Any, Any]],
    *,
    axis: str,
    pos: float,
    lo: float,
    hi: float,
    top: float,
    tol: float,
) -> tuple[float, tuple[FaceLike, ...]] | None:
    """Return the current maximal-base original faces for one perimeter role."""

    matches = []
    for face, bounds, normal in vertical_faces:
        n_axis = abs(normal.X) if axis == "x" else abs(normal.Y)
        if n_axis < AXIS_ALIGNED_COS:
            continue
        plane_pos = (
            (bounds.min.X + bounds.max.X) / 2 if axis == "x" else (bounds.min.Y + bounds.max.Y) / 2
        )
        cross_lo = bounds.min.Y if axis == "x" else bounds.min.X
        cross_hi = bounds.max.Y if axis == "x" else bounds.max.X
        if (
            abs(plane_pos - pos) <= tol
            and abs(bounds.max.Z - top) <= tol
            and top - tol > bounds.min.Z
            and cross_lo <= lo + tol
            and cross_hi >= hi - tol
        ):
            matches.append((float(bounds.min.Z), face))
    if not matches:
        return None
    base = max(item[0] for item in matches)
    return base, tuple(face for candidate_base, face in matches if candidate_base == base)


def _touches_plan(a: RaisedPad, b: RaisedPad, *, tol: float) -> bool:
    """Return the current tolerance-inclusive XY contact predicate."""

    return min(a.x1, b.x1) - max(a.x0, b.x0) >= -tol and min(a.y1, b.y1) - max(a.y0, b.y0) >= -tol


def _tier_suppresses(pad: RaisedPad, region: RaisedPad, *, tol: float) -> bool:
    """Return whether one raw top is the current touching-tier suppression context."""

    return abs(region.z1 - pad.z0) <= tol and _touches_plan(pad, region, tol=tol)


def _recognise_rectangular_pads_one(
    part, *, tol: float | None, face_surfaces: EffectiveFaceSurfaceQuery
) -> list[_PadProposal]:
    """Recognise pads using one solid's faces and bounds."""
    bb = part.bounding_box()
    tol = _TOL if tol is None else tol
    suppression_tops: list[tuple[float, float, float, float, float, FaceLike]] = []
    certified_tops: list[tuple[float, float, float, float, float, FaceLike]] = []
    for face in part.faces():
        fact = face_surfaces.fact(face)
        if not isinstance(fact, AnalyticSurfaceFact) or fact.kind is not SurfaceKind.PLANE:
            continue
        direction = fact.parameters[:3]
        if abs(direction[2]) < AXIS_ALIGNED_COS:
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
        top = (
            round(fb.min.X, 3),
            round(fb.max.X, 3),
            round(fb.min.Y, 3),
            round(fb.max.Y, 3),
            round(fb.max.Z, 3),
            face,
        )
        top_surface = face_surfaces.use(face, material_side=True)
        if isinstance(top_surface, SurfaceUseRefusal):
            # Tier suppression is conservative context, not a feature claim.
            # Keep unverified geometric ledges in that context; refusing a ledge
            # must never introduce a Pad claim on the tier above it.
            suppression_tops.append(top)
            continue
        certificate = top_surface.material_side
        if certificate is None:
            suppression_tops.append(top)
            continue
        if certificate.outward[2] < AXIS_ALIGNED_COS:
            continue
        suppression_tops.append(top)
        certified_tops.append(top)

    # Recover each pad's base from its own four downward perimeter walls. A
    # part-global "highest horizontal level below the top" is wrong when another
    # feature has an unrelated intervening Z level.
    vertical_faces = []
    for face in part.faces():
        fact = face_surfaces.fact(face)
        if not isinstance(fact, AnalyticSurfaceFact) or fact.kind is not SurfaceKind.PLANE:
            continue
        direction = fact.parameters[:3]
        if abs(direction[2]) > AXIS_ZERO_COS:
            continue
        fb = face.bounding_box()
        vertical_faces.append((face, fb, Vector(*direction)))

    proposals: list[_PadProposal] = []
    for x0, x1, y0, y1, z1, top_face in certified_tops:
        roles = (
            _wall_role(vertical_faces, axis="x", pos=x0, lo=y0, hi=y1, top=z1, tol=tol),
            _wall_role(vertical_faces, axis="x", pos=x1, lo=y0, hi=y1, top=z1, tol=tol),
            _wall_role(vertical_faces, axis="y", pos=y0, lo=x0, hi=x1, top=z1, tol=tol),
            _wall_role(vertical_faces, axis="y", pos=y1, lo=x0, hi=x1, top=z1, tol=tol),
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
    raw_regions = [
        RaisedPad(x0, x1, y0, y1, z1, z1) for x0, x1, y0, y1, z1, _face in suppression_tops
    ]
    return [
        proposal
        for proposal in proposals
        if not any(_tier_suppresses(proposal.record, other, tol=tol) for other in raw_regions)
    ]


def _surface_area(face: FaceLike) -> float:
    properties = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face.wrapped, properties)
    return float(properties.Mass())


def _recognise_blended_rectangular_pads_one(
    part,
    *,
    tol: float | None,
    face_surfaces: EffectiveFaceSurfaceQuery,
    geometry: GeometryGraph,
) -> list[_PadProposal]:
    """Recognise one complete four-corner convex blend cycle around a rectangular pad."""

    tol = _TOL if tol is None else tol
    bb = part.bounding_box()
    faces = tuple(part.faces())
    refs = {geometry.ref(face): face for face in faces}
    local_refs = set(refs)

    vertical: dict[FaceRef, tuple[FaceLike, Any, tuple[float, float, float]]] = {}
    for ref, face in refs.items():
        fact = face_surfaces.fact(face)
        normal = geometry.normal(ref)
        if (
            isinstance(fact, AnalyticSurfaceFact)
            and fact.kind is SurfaceKind.PLANE
            and normal is not None
            and abs(normal[2]) <= AXIS_ZERO_COS
        ):
            vertical[ref] = (face, face.bounding_box(), normal)

    eligible_chains: list[BlendFact] | None = None

    proposals: list[_PadProposal] = []
    for top_ref, top_face in refs.items():
        fact = face_surfaces.fact(top_face)
        if not isinstance(fact, AnalyticSurfaceFact) or fact.kind is not SurfaceKind.PLANE:
            continue
        top_bounds = top_face.bounding_box()
        z1 = round(top_bounds.max.Z, 3)
        if bb.min.Z + tol >= z1:
            continue

        adjacent_vertical = set(geometry.neighbours(top_ref)) & set(vertical)
        roles: dict[str, FaceRef] = {}
        for ref in adjacent_vertical:
            _face, bounds, normal = vertical[ref]
            if abs(bounds.max.Z - z1) > tol:
                continue
            if abs(normal[0]) >= AXIS_ALIGNED_COS and abs(normal[1]) <= AXIS_ZERO_COS:
                role = "x1" if normal[0] > 0 else "x0"
            elif abs(normal[1]) >= AXIS_ALIGNED_COS and abs(normal[0]) <= AXIS_ZERO_COS:
                role = "y1" if normal[1] > 0 else "y0"
            else:
                continue
            if role in roles:
                roles = {}
                break
            roles[role] = ref
        if set(roles) != {"x0", "x1", "y0", "y1"}:
            continue

        ordered_refs = tuple(roles[name] for name in ("x0", "x1", "y0", "y1"))
        x0 = round(sum(geometry.bounds(roles["x0"])[0]) / 2, 3)
        x1 = round(sum(geometry.bounds(roles["x1"])[0]) / 2, 3)
        y0 = round(sum(geometry.bounds(roles["y0"])[1]) / 2, 3)
        y1 = round(sum(geometry.bounds(roles["y1"])[1]) / 2, 3)
        if x1 - x0 <= tol or y1 - y0 <= tol:
            continue
        full_x = bb.min.X + tol >= x0 and bb.max.X - tol <= x1
        full_y = bb.min.Y + tol >= y0 and bb.max.Y - tol <= y1
        if full_x or full_y:
            continue
        role_cross_spans = (
            geometry.bounds(roles["x0"])[1],
            geometry.bounds(roles["x1"])[1],
            geometry.bounds(roles["y0"])[0],
            geometry.bounds(roles["y1"])[0],
        )
        expected_cross_spans = ((y0, y1), (y0, y1), (x0, x1), (x0, x1))
        if all(
            actual[0] <= expected[0] + tol and actual[1] >= expected[1] - tol
            for actual, expected in zip(role_cross_spans, expected_cross_spans, strict=True)
        ):
            continue  # the unchanged sharp path owns uninterrupted wall roles

        top_use = face_surfaces.use(top_face, material_side=True)
        if isinstance(top_use, SurfaceUseRefusal) or top_use.material_side is None:
            continue
        if top_use.material_side.outward[2] < AXIS_ALIGNED_COS:
            continue

        if eligible_chains is None:  # pragma: no branch - cached after the first eligible top
            eligible_chains = []
            for chain in geometry.blend_facts():
                if (
                    chain.side != "convex"
                    or len(chain.blend_faces) != 1
                    or any(len(support) != 1 for support in chain.supports)
                ):
                    continue
                left = next(iter(chain.supports[0]))
                right = next(iter(chain.supports[1]))
                if left not in vertical or right not in vertical:
                    continue  # pragma: no cover - graph-issued support refs are local
                if not chain.blend_faces <= local_refs:
                    continue  # pragma: no cover - graph-issued blend refs are local
                blend_fact = geometry.surface_fact(next(iter(chain.blend_faces)))
                if (
                    not isinstance(blend_fact, AnalyticSurface)
                    or blend_fact.kind is not InspectionSurfaceKind.CYLINDER
                ):
                    continue
                left_span = geometry.bounds(left)[2]
                right_span = geometry.bounds(right)[2]
                if abs(left_span[1] - right_span[1]) > tol:
                    continue  # pragma: no cover - one native chain has one shared axial span
                eligible_chains.append(chain)

        expected_pairs = (
            frozenset((roles["x0"], roles["y0"])),
            frozenset((roles["x0"], roles["y1"])),
            frozenset((roles["x1"], roles["y0"])),
            frozenset((roles["x1"], roles["y1"])),
        )
        expected_pair_set = set(expected_pairs)
        by_pair: dict[frozenset[FaceRef], list[BlendFact]] = {}
        for chain in eligible_chains:
            pair = frozenset((next(iter(chain.supports[0])), next(iter(chain.supports[1]))))
            if pair in expected_pair_set:
                by_pair.setdefault(pair, []).append(chain)
        if set(by_pair) != expected_pair_set or any(
            len(chains) != 1 for chains in by_pair.values()
        ):
            continue
        selected = tuple(by_pair[pair][0] for pair in expected_pairs)

        spans = [geometry.bounds(ref)[2] for ref in ordered_refs]
        if any(abs(span[1] - z1) > tol for span in spans):
            continue  # pragma: no cover - adjacency to this planar top fixes the upper span
        z0 = round(max(span[0] for span in spans), 3)
        if z1 - z0 <= tol:
            continue  # pragma: no cover - eligible vertical faces have positive height

        # Four quarter-circle removals explain the rounded top exactly; another trim or hole
        # cannot borrow the blend cycle's permission to become a Pad.
        if len(top_face.wires()) != 1:
            continue
        removed = math.fsum((1.0 - math.pi / 4.0) * chain.radius**2 for chain in selected)
        expected_area = (x1 - x0) * (y1 - y0) - removed
        if abs(_surface_area(top_face) - expected_area) > max(tol * tol, 0.005 * expected_area):
            continue

        bridges = geometry.collapsed_bridges(tuple(chain.ref for chain in selected))
        if len(bridges) != 4:
            raise ValueError("selected Pad blend cycle has no unique logical bridges")
        for chain in selected:
            pair = frozenset((next(iter(chain.supports[0])), next(iter(chain.supports[1]))))
            matching = [bridge for bridge in bridges if frozenset(bridge.supports) == pair]
            if len(matching) != 1:
                raise ValueError("selected Pad blend chain has no unique logical bridge")
            expected_faces = frozenset((*chain.blend_faces, *chain.supports[0], *chain.supports[1]))
            if matching[0].provenance.faces != expected_faces or Counter(
                matching[0].provenance.boundary
            ) != Counter(chain.boundary):
                raise ValueError("selected Pad blend bridge lost original provenance")

        proposals.append(
            _PadProposal(
                RaisedPad(x0, x1, y0, y1, z0, z1),
                top_face,
                tuple((vertical[ref][0],) for ref in ordered_refs),
            )
        )
    return proposals


def recognise_rectangular_pads(part: Part, *, tol: float | None = None) -> list[RaisedPad]:
    """Return bounded rectangular raised faces independently per solid.

    A candidate is a planar +Z face whose area fills its XY bounding rectangle
    and is bounded on both in-plane axes. Full-span steps are excluded;
    non-rectangular pocket floors and perforated plate faces fail the area test.
    Body-local walls and bounds prevent a detached component from being treated
    as a pad raised from another component. Each input face must have one unique
    owner in a valid closed solid; open, invalid, or ambiguous body ownership is
    refused and returns no Pad records.
    """
    return _discover_rectangular_pads(part, tol=tol)


def _discover_rectangular_pads(
    part: Part,
    *,
    tol: float | None = None,
    writer: EvidenceWriter | None = None,
    face_surfaces: EffectiveFaceSurfaceQuery | None = None,
    geometry: GeometryGraph | None = None,
) -> list[RaisedPad]:
    """Shared rectangular-pad discovery with optional aggregate evidence issuance."""

    if face_surfaces is None:
        face_surfaces = (
            effective_faces_for_part(part)
            if writer is None
            else effective_faces_for_graph(writer.graph)
        )
    elif writer is not None and face_surfaces.run_token is not writer.graph.run_token:
        raise ValueError("Pad surface facts and evidence writer belong to different runs")
    if geometry is None:
        geometry = (
            GeometryGraph._from_graph(writer.graph) if writer is not None else GeometryGraph(part)
        )
    elif writer is not None and not geometry._uses_graph(writer.graph):
        raise ValueError("Pad geometry and evidence writer belong to different runs")

    solids = list(part.solids())
    sources = solids if len(solids) > 1 else [part]
    occurrences: list[tuple[RaisedPad, tuple[_PadProposal, ...]]] = []
    for solid in sources:
        by_record: dict[RaisedPad, list[_PadProposal]] = {}
        proposals = _recognise_rectangular_pads_one(solid, tol=tol, face_surfaces=face_surfaces)
        proposals.extend(
            _recognise_blended_rectangular_pads_one(
                solid, tol=tol, face_surfaces=face_surfaces, geometry=geometry
            )
        )
        for proposal in proposals:
            by_record.setdefault(proposal.record, []).append(proposal)
        occurrences.extend((record, tuple(group)) for record, group in by_record.items())
    occurrences.sort(key=lambda item: item[0])
    records = [record for record, _group in occurrences]
    if writer is None:
        return records

    pending: list[tuple[RaisedPad, tuple[Any, ...], tuple[SurfaceUse, ...]]] = []
    used_tops: set[Any] = set()
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
        if signature[0] in used_tops:
            raise ValueError("Pad occurrences share a defining top face")
        ordered = tuple(node for node in writer.graph.nodes if node in node_set)
        if writer.graph.common_valid_solid(ordered) is None:
            raise ValueError("Pad defining faces do not belong to one valid solid")
        used_tops.add(signature[0])
        selected = alternatives[0]
        selected_faces = (selected.top_face, *(faces[0] for faces in selected.wall_roles))
        issued_uses = tuple(
            face_surfaces.use(face, material_side=face is selected.top_face)
            for face in selected_faces
        )
        if any(isinstance(use, SurfaceUseRefusal) for use in issued_uses):
            raise ValueError("Pad surface provenance became unavailable before issuance")
        surface_by_node = {use.node: use for use in issued_uses if isinstance(use, SurfaceUse)}
        surface_uses = tuple(surface_by_node[node] for node in ordered)
        pending.append((record, ordered, surface_uses))
    for record, nodes, surface_uses in pending:
        writer.add_defining(
            record,
            nodes,
            family=FamilyId.PADS,
            surfaces=surface_uses,
        )
    return records
