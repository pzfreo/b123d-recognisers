# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Recognition of bounded regular hexagonal bosses and whole-stock prisms.

The proven capability is intentionally narrow: Z-axis hexagons with six planar side faces,
opposed equal support planes, and unambiguous terminal caps. Other axes or polygon classes fail
closed until independent corpus evidence establishes their geometry contract.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane

from b123d_recognisers._geometry import AXIS_ALIGNED_COS, resolved_tol
from b123d_recognisers._record import Record
from b123d_recognisers._typing import Part

#: Face/bound coincidence band, as a fraction of the owning solid's largest extent (ADR 0008).
#: Derived per solid, matching the per-solid recognition boundary. The fraction is the 0.2 mm
#: default it replaces over the corpus's 70 mm median extent.
_TOL_FRAC = 0.00286

#: A boss side face is vertical: its normal has essentially no Z component. Looser than the
#: package's AXIS_ZERO_COS because an extruded prism's walls carry the sketch's angular noise,
#: and a side rejected here costs the whole ring.
_SIDE_VERTICAL_COS = 0.02


@dataclass(frozen=True, order=True)
class PolygonalBoss(Record):
    """A regular hexagonal Z-axis prism attached to a support face.

    The current recogniser emits exactly ``axis="z"`` and ``side_count=6``. Other
    axes and polygon classes require their own evidence before they become package
    capability. ``flat_directions`` preserve the ordered outward evidence that
    established the hexagon. ``flat_centres`` are real points on the defining side
    faces, so rendering can anchor a leader without reconstructing it from A/F.
    """

    axis: str
    center: tuple[float, float, float]
    side_count: int
    across_flats: float
    base: float
    top: float
    flat_directions: tuple[tuple[float, float, float], ...]
    flat_centres: tuple[tuple[float, float, float], ...]

    @property
    def height(self) -> float:
        return self.top - self.base


@dataclass(frozen=True, order=True)
class PolygonalStock(Record):
    """A whole solid proved to be a regular hexagonal prism.

    The current recogniser emits exactly ``axis="z"`` and ``side_count=6``.
    This is deliberately distinct from :class:`PolygonalBoss`: its two caps terminate the
    complete solid, rather than one cap being an attachment to supporting material.
    """

    axis: str
    center: tuple[float, float, float]
    side_count: int
    across_flats: float
    base: float
    top: float
    flat_directions: tuple[tuple[float, float, float], ...]
    flat_centres: tuple[tuple[float, float, float], ...]

    @property
    def length(self) -> float:
        return self.top - self.base


def _normal(face):
    try:
        normal = face.normal_at(face.center())
    except Exception:  # noqa: BLE001 - a degenerate face cannot prove a boss
        return None
    return (float(normal.X), float(normal.Y), float(normal.Z))


def _bbox_tuple(face) -> tuple[float, float, float, float, float, float]:
    bb = face.bounding_box()
    return (
        float(bb.min.X),
        float(bb.max.X),
        float(bb.min.Y),
        float(bb.max.Y),
        float(bb.min.Z),
        float(bb.max.Z),
    )


def _cap_z(
    face,
    tol: float,
    *,
    positive: bool,
    lower_than: float | None,
    higher_than: float | None,
) -> float | None:
    """The Z of *face* if it can serve as a terminal cap, else ``None``.

    A cap is planar, faces squarely along Z in the required direction, sits at a single Z rather
    than spanning a range, and lies on the correct side of the wall it terminates.
    """

    if BRepAdaptor_Surface(face.wrapped).GetType() != GeomAbs_Plane:
        return None
    normal = _normal(face)
    if normal is None or (
        normal[2] < AXIS_ALIGNED_COS if positive else normal[2] > -AXIS_ALIGNED_COS
    ):
        return None
    bb = _bbox_tuple(face)
    if bb[5] - bb[4] > tol:
        return None
    z = (bb[4] + bb[5]) / 2
    if lower_than is not None and z > lower_than + tol:
        return None
    if higher_than is not None and z < higher_than - tol:
        return None
    return z


def _common_cap(
    component: tuple[int, ...],
    faces: list,
    adjacent_to: Callable[[int], set[int]],
    tol: float,
    *,
    upper: bool,
    positive: bool,
    wall_lo: float,
    wall_hi: float,
) -> float | None:
    """The single cap Z shared by every side of the ring, or ``None``.

    Each side must reach the end through exactly one neighbour — an ambiguous choice means the
    ring is not cleanly terminated — and those neighbours must then meet at exactly one cap
    face. Requiring exactly one at both steps is what makes this fail closed: a boss with two
    candidate tops is not a boss whose top we can name.
    """

    boundary: list[int] = []
    component_set = set(component)
    for side in component:
        choices = []
        for other in adjacent_to(side) - component_set:
            bb = _bbox_tuple(faces[other])
            reaches_end = abs(bb[4] - wall_hi) <= tol if upper else abs(bb[5] - wall_lo) <= tol
            if reaches_end:
                choices.append(other)
        if len(choices) != 1:
            return None
        boundary.append(choices[0])

    boundary_set = set(boundary)
    if len(boundary_set) == 1:
        candidates = boundary_set
    else:
        candidates = set.intersection(*(adjacent_to(face) for face in boundary_set))
        candidates -= component_set | boundary_set
    cap_zs = [
        cap
        for index in candidates
        if (
            cap := _cap_z(
                faces[index],
                tol,
                positive=positive,
                lower_than=None if upper else wall_lo,
                higher_than=wall_hi if upper else None,
            )
        )
        is not None
    ]
    return cap_zs[0] if len(cap_zs) == 1 else None


def _side_rings(
    vertical: list[int],
    bounds: dict[int, tuple[float, float, float, float, float, float]],
    tol: float,
    shares_edge: Callable[[int, int], bool],
) -> list[tuple[int, ...]]:
    """Group side faces into rings: connected, and spanning the same Z range.

    Both conditions are needed. Sharing an edge alone would chain a boss into the plate it
    stands on; sharing a Z span alone would merge two separate bosses of equal height into one
    ring with twelve sides.
    """

    def same_span(i: int, j: int) -> bool:
        return abs(bounds[i][4] - bounds[j][4]) <= tol and abs(bounds[i][5] - bounds[j][5]) <= tol

    rings: list[tuple[int, ...]] = []
    unseen = set(vertical)
    while unseen:
        connected = {unseen.pop()}
        frontier = list(connected)
        while frontier:
            current = frontier.pop()
            joined = {
                other
                for other in unseen
                if same_span(current, other) and shares_edge(current, other)
            }
            unseen -= joined
            connected |= joined
            frontier.extend(joined)
        rings.append(tuple(connected))
    return rings


def _vertical_side_faces(
    faces: list,
    tol: float,
) -> tuple[
    dict[int, tuple[float, float, float]],
    dict[int, tuple[float, float, float, float, float, float]],
    list[int],
]:
    """Index the planar faces that could be prism sides: vertical, and tall enough to be walls.

    Returns their normals, bounding boxes and indices. Everything downstream works from these
    three, so the scan is done once and the rest of recognition never touches a raw face again.
    """

    normals: dict[int, tuple[float, float, float]] = {}
    bounds: dict[int, tuple[float, float, float, float, float, float]] = {}
    vertical: list[int] = []
    for index, face in enumerate(faces):
        if BRepAdaptor_Surface(face.wrapped).GetType() != GeomAbs_Plane:
            continue
        normal = _normal(face)
        if normal is None or abs(normal[2]) > _SIDE_VERTICAL_COS:
            continue
        bb = _bbox_tuple(face)
        if bb[5] - bb[4] <= tol:
            continue
        normals[index] = normal
        bounds[index] = bb
        vertical.append(index)
    return normals, bounds, vertical


def _regular_ring_order(
    component: tuple[int, ...],
    normals: dict[int, tuple[float, float, float]],
    angle_tol: float,
) -> tuple[int, ...] | None:
    """Order a side ring by heading, or reject it as not a regular polygon.

    Two independent proofs, both needed: the headings are evenly spaced, and each side faces
    directly away from the one opposite it. Even spacing alone admits a ring that spirals; the
    opposed test alone admits an irregular polygon whose pairs happen to be parallel.
    """

    side_count = len(component)
    ordered = tuple(sorted(component, key=lambda i: math.atan2(normals[i][1], normals[i][0])))
    angles = [math.atan2(normals[i][1], normals[i][0]) % (2 * math.pi) for i in ordered]
    gaps = [(angles[(i + 1) % side_count] - angles[i]) % (2 * math.pi) for i in range(side_count)]
    expected_gap = 2 * math.pi / side_count
    if any(abs(gap - expected_gap) > angle_tol for gap in gaps):
        return None
    opposite = side_count // 2
    if any(
        normals[ordered[i]][0] * normals[ordered[i + opposite]][0]
        + normals[ordered[i]][1] * normals[ordered[i + opposite]][1]
        > -math.cos(angle_tol)
        for i in range(opposite)
    ):
        return None
    return ordered


def _ring_profile(
    ordered: tuple[int, ...],
    normals: dict[int, tuple[float, float, float]],
    centres: list,
    tol: float,
) -> tuple[float, float, float] | None:
    """The ring's axis ``(x, y)`` and across-flats, or ``None`` if it is not one prism.

    Each opposed pair of side planes defines a midplane containing the axis. Six such planes
    over-determine a point, so the axis is the least-squares intersection rather than any one
    pair's — which keeps a single noisy face from moving the reported centre.

    The support distances then have to agree: every side the same distance out, and every
    opposed pair the same distance apart. Disagreement means an irregular polygon, and a
    non-positive support means the walls face inward, which is a recess rather than a boss.
    """

    side_count = len(ordered)
    opposite = side_count // 2
    plane_offsets = [
        normals[index][0] * float(point.X) + normals[index][1] * float(point.Y)
        for index, point in zip(ordered, centres, strict=True)
    ]
    midplanes = [
        (
            normals[ordered[i]][0],
            normals[ordered[i]][1],
            (plane_offsets[i] - plane_offsets[i + opposite]) / 2,
        )
        for i in range(opposite)
    ]
    sxx = sum(nx * nx for nx, _ny, _offset in midplanes)
    sxy = sum(nx * ny for nx, ny, _offset in midplanes)
    syy = sum(ny * ny for _nx, ny, _offset in midplanes)
    bx = sum(nx * offset for nx, _ny, offset in midplanes)
    by = sum(ny * offset for _nx, ny, offset in midplanes)
    determinant = sxx * syy - sxy * sxy
    # Six normals that passed the near-60-degree ring gate necessarily span the plane.
    cx = (bx * syy - by * sxy) / determinant
    cy = (sxx * by - sxy * bx) / determinant

    supports = [
        offset - normals[index][0] * cx - normals[index][1] * cy
        for index, offset in zip(ordered, plane_offsets, strict=True)
    ]
    if min(supports) <= tol:
        return None  # inward-facing walls describe a recess, not material projecting out
    across_values = [supports[i] + supports[i + opposite] for i in range(opposite)]
    across = sum(across_values) / len(across_values)
    if max(abs(value - across) for value in across_values) > tol:
        return None
    if max(abs(value - across / 2) for value in supports) > tol:
        return None
    return cx, cy, across


def _recognise_one(
    part, *, tol: float | None, angle_tol: float, whole_stock: bool = False
) -> list[PolygonalBoss | PolygonalStock]:
    tol = resolved_tol(tol, part.bounding_box(), rel=_TOL_FRAC)
    faces = list(part.faces())
    edges = [[edge.wrapped for edge in face.edges()] for face in faces]
    adjacency: dict[tuple[int, int], bool] = {}

    def shares_edge(i: int, j: int) -> bool:
        key = (min(i, j), max(i, j))
        if key not in adjacency:
            adjacency[key] = any(a.IsSame(b) for a in edges[i] for b in edges[j])
        return adjacency[key]

    normals, bounds, vertical = _vertical_side_faces(faces, tol)

    components = _side_rings(vertical, bounds, tol, shares_edge)

    def adjacent_to(index: int) -> set[int]:
        return {
            other for other in range(len(faces)) if other != index and shares_edge(index, other)
        }


    found: list[PolygonalBoss | PolygonalStock] = []
    for component in components:
        side_count = len(component)
        # The accepted corpus proves hexagonal bosses. Broader polygon classes need their own
        # corpus evidence before automatic recognition can claim them.
        if side_count != 6:
            continue
        # Whole stock is intentionally the exact-prism class: one closed solid made only
        # from this side ring and its two terminal caps. Attached bosses, recesses, holes,
        # chamfers and assemblies need different ownership/evidence.
        if whole_stock and len(faces) != side_count + 2:
            continue
        component_set = set(component)
        if any(
            len({other for other in component_set if other != side and shares_edge(side, other)})
            != 2
            for side in component
        ):
            continue

        ordered = _regular_ring_order(component, normals, angle_tol)
        if ordered is None:
            continue
        centres = [faces[i].center() for i in ordered]
        profile = _ring_profile(ordered, normals, centres, tol)
        if profile is None:
            continue
        cx, cy, across = profile

        wall_lo = sum(bounds[i][4] for i in component) / side_count
        wall_hi = sum(bounds[i][5] for i in component) / side_count
        base = _common_cap(
            component,
            faces,
            adjacent_to,
            tol,
            upper=False,
            positive=not whole_stock,
            wall_lo=wall_lo,
            wall_hi=wall_hi,
        )
        top = _common_cap(
            component, faces, adjacent_to, tol, upper=True, positive=True,
            wall_lo=wall_lo, wall_hi=wall_hi,
        )
        if base is None or top is None or top - base <= tol:
            continue
        if whole_stock and (abs(base - wall_lo) > tol or abs(top - wall_hi) > tol):
            continue
        flat_centres = tuple(
            (round(float(point.X), 3), round(float(point.Y), 3), round(float(point.Z), 3))
            for point in centres
        )
        flat_directions = tuple(
            (round(normals[index][0], 3), round(normals[index][1], 3), 0.0) for index in ordered
        )
        record_type = PolygonalStock if whole_stock else PolygonalBoss
        found.append(
            record_type(
                axis="z",
                center=(round(cx, 4), round(cy, 4), round((base + top) / 2, 4)),
                side_count=side_count,
                across_flats=round(across, 4),
                base=round(base, 4),
                top=round(top, 4),
                flat_directions=flat_directions,
                flat_centres=flat_centres,
            )
        )
    return found


def recognise_polygonal_bosses(
    part: Part, *, tol: float | None = None, angle_tol: float = math.radians(2)
) -> list[PolygonalBoss]:
    """Return regular hexagonal Z-axis bosses independently per physical solid.

    A candidate is accepted from a closed ring of outward planar side faces, opposed
    support planes with one A/F value, and common attached support/top caps. A whole prism,
    a blind recess, or faces assembled across separate solids cannot satisfy that evidence.
    """
    solids = list(part.solids())
    sources = solids if len(solids) > 1 else [part]
    return sorted(
        boss
        for solid in sources
        for boss in _recognise_one(solid, tol=tol, angle_tol=angle_tol)
        if isinstance(boss, PolygonalBoss)
    )


def recognise_polygonal_stock(
    part: Part, *, tol: float | None = None, angle_tol: float = math.radians(2)
) -> list[PolygonalStock]:
    """Return one record only when the complete part is a regular hexagonal prism.

    The exact-prism boundary is fail closed: multi-solid assemblies and solids with any
    additional or missing face are not silently promoted to stock.
    """
    if len(list(part.solids())) != 1 or len(list(part.faces())) != 8:
        return []
    return sorted(
        record
        for record in _recognise_one(part, tol=tol, angle_tol=angle_tol, whole_stock=True)
        if isinstance(record, PolygonalStock)
    )
