# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Recognition of bounded regular hexagonal bosses and whole-stock prisms.

The proven capability is intentionally narrow: Z-axis hexagons with six planar side faces,
opposed equal support planes, and unambiguous terminal caps. Other axes or polygon classes fail
closed until independent corpus evidence establishes their geometry contract.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TypeVar, cast

from b123d_recognisers._adjacency import FaceGraph, FaceNode, connected_components
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import EvidenceWriter
from b123d_recognisers._geometry import AXIS_ALIGNED_COS
from b123d_recognisers._record import Record
from b123d_recognisers._typing import FaceLike, Part
from b123d_recognisers.experimental_geometry import (
    AnalyticSurface,
    BlendFact,
    GeometryGraph,
    SurfaceKind,
)

#: Whatever a caller keys its ring by: this module passes face nodes, the unit tests pass ints.
#: The two polygon helpers below never look inside it, which is the point -- they are geometry
#: over headings and have no business knowing a B-Rep exists.
_K = TypeVar("_K")

#: **A minimum-evidence threshold, not a tolerance — deliberately absolute (ADR 0008).**
#: Scaling it to the part makes a feature's existence depend on what surrounds it, so a small
#: feature on a large part disappears. Whether such a feature is worth dimensioning is consumer
#: policy, and ADR 0001 puts policy with the consumer; recognition reports it either way.
#: Also the minimum boss height and support span.
_TOL = 0.2

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


@dataclass(frozen=True, slots=True)
class _PolygonalProposal:
    record: PolygonalBoss | PolygonalStock
    side_faces: tuple[FaceLike, ...]
    lower_cap: FaceLike
    upper_cap: FaceLike


@dataclass(frozen=True, slots=True)
class _CapSelection:
    """One unique terminal cap retained with the coordinate it establishes."""

    node: FaceNode
    z: float


def _heading(graph: FaceGraph, node: FaceNode) -> tuple[float, float, float]:
    """A side face's outward normal, known to exist.

    Every node that reaches the ring helpers came through `_vertical_side_faces`, which already
    refused a face whose normal will not evaluate. Saying that once here beats either guarding
    it at six call sites or writing six unreachable branches -- the graph cannot know the
    filter has run, but this module does.
    """

    return cast("tuple[float, float, float]", graph.normal(node))


def _cap_z(
    graph: FaceGraph,
    node: FaceNode,
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

    if not graph.is_planar(node):
        return None
    normal = graph.normal(node)
    if normal is None or (
        normal[2] < AXIS_ALIGNED_COS if positive else normal[2] > -AXIS_ALIGNED_COS
    ):
        return None
    z_lo, z_hi = graph.bounds(node)[2]
    if z_hi - z_lo > tol:
        return None
    z = (z_lo + z_hi) / 2
    if lower_than is not None and z > lower_than + tol:
        return None
    if higher_than is not None and z < higher_than - tol:
        return None
    return z


def _common_cap(
    component: tuple[FaceNode, ...],
    graph: FaceGraph,
    adjacent_to: Callable[[FaceNode], set[FaceNode]],
    tol: float,
    *,
    upper: bool,
    positive: bool,
    wall_lo: float,
    wall_hi: float,
) -> _CapSelection | None:
    """The single cap Z shared by every side of the ring, or ``None``.

    Each side must reach the end through exactly one neighbour — an ambiguous choice means the
    ring is not cleanly terminated — and those neighbours must then meet at exactly one cap
    face. Requiring exactly one at both steps is what makes this fail closed: a boss with two
    candidate tops is not a boss whose top we can name.
    """

    boundary: list[FaceNode] = []
    component_set = set(component)
    for side in component:
        choices = []
        for other in adjacent_to(side) - component_set:
            z_lo, z_hi = graph.bounds(other)[2]
            reaches_end = abs(z_lo - wall_hi) <= tol if upper else abs(z_hi - wall_lo) <= tol
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
    cap_selections = [
        _CapSelection(node, cap)
        for node in candidates
        if (
            cap := _cap_z(
                graph,
                node,
                tol,
                positive=positive,
                lower_than=None if upper else wall_lo,
                higher_than=wall_hi if upper else None,
            )
        )
        is not None
    ]
    return cap_selections[0] if len(cap_selections) == 1 else None


def _side_rings(
    vertical: list[FaceNode],
    graph: FaceGraph,
    tol: float,
    shares_edge: Callable[[FaceNode, FaceNode], bool],
) -> list[tuple[FaceNode, ...]]:
    """Group side faces into rings: connected, and spanning the same Z range.

    Both conditions are needed. Sharing an edge alone would chain a boss into the plate it
    stands on; sharing a Z span alone would merge two separate bosses of equal height into one
    ring with twelve sides.
    """

    def same_span(i: FaceNode, j: FaceNode) -> bool:
        lo_i, hi_i = graph.bounds(i)[2]
        lo_j, hi_j = graph.bounds(j)[2]
        return abs(lo_i - lo_j) <= tol and abs(hi_i - hi_j) <= tol

    return connected_components(vertical, lambda i, j: same_span(i, j) and shares_edge(i, j))


def _vertical_side_faces(graph: FaceGraph, tol: float) -> list[FaceNode]:
    """The planar faces that could be prism sides: vertical, and tall enough to be walls.

    Only the selection is this recogniser's; the normal and the bounding box it selects on come
    from the graph, which memoises them per face. Deriving them here meant a second copy of both
    for every face the module touched, and the map that held them was the ad hoc face graph this
    package now has one of.
    """

    vertical: list[FaceNode] = []
    for node in graph.nodes:
        if not graph.is_planar(node):
            continue
        normal = graph.normal(node)
        if normal is None or abs(normal[2]) > _SIDE_VERTICAL_COS:
            continue
        z_lo, z_hi = graph.bounds(node)[2]
        if z_hi - z_lo <= tol:
            continue
        vertical.append(node)
    return vertical


def _six_support_cycle_indices(
    pairs: tuple[frozenset[FaceNode], ...],
) -> tuple[int, ...]:
    """Indices belonging to disjoint exact six-edge/six-node degree-two components."""

    remaining = set(range(len(pairs)))
    selected: list[int] = []
    while remaining:
        seed = min(remaining)
        remaining.remove(seed)
        component = {seed}
        supports = set(pairs[seed])
        changed = True
        while changed:
            changed = False
            for at in tuple(remaining):
                if supports.intersection(pairs[at]):
                    remaining.remove(at)
                    component.add(at)
                    supports.update(pairs[at])
                    changed = True
        ordered = sorted(component)
        component_pairs = [pairs[at] for at in ordered]
        if len(ordered) != 6 or len(supports) != 6 or len(set(component_pairs)) != 6:
            continue
        if any(sum(node in pair for pair in component_pairs) != 2 for node in supports):
            continue
        selected.extend(ordered)
    return tuple(selected)


def _polygonal_boss_blend_bridges(
    graph: FaceGraph, vertical: list[FaceNode], tol: float
) -> frozenset[frozenset[FaceNode]]:
    """Return only provenance-complete bridges for unambiguous six-support blend cycles."""

    geometry = GeometryGraph._from_graph(graph)
    face_refs = {node: geometry.ref(graph.face(node)) for node in graph.nodes}
    nodes_by_ref = {ref: node for node, ref in face_refs.items()}
    vertical_set = set(vertical)
    possible: list[tuple[FaceNode, frozenset[FaceNode]]] = []
    for node in graph.nodes:
        if node in vertical_set:
            continue
        supports = vertical_set.intersection(graph.neighbours(node))
        if len(supports) != 2:
            continue
        left, right = tuple(supports)
        if any(
            abs(a - b) > tol
            for a, b in zip(graph.bounds(left)[2], graph.bounds(right)[2], strict=True)
        ):
            continue
        possible.append((node, frozenset(supports)))

    def contains_six_cycle(pairs: list[frozenset[FaceNode]]) -> bool:
        possible_supports = set().union(*pairs) if pairs else set()
        return len(pairs) >= 6 and any(
            len(component) == 6
            and sum(pair <= set(component) for pair in pairs) >= 6
            for component in connected_components(
                possible_supports,
                lambda left, right: frozenset((left, right)) in pairs,
            )
        )

    possible_pairs = [pair for _node, pair in possible]
    if not contains_six_cycle(possible_pairs):
        return frozenset()

    cylindrical_pairs = [
        pair
        for node, pair in possible
        if isinstance(fact := geometry.surface_fact(face_refs[node]), AnalyticSurface)
        and fact.kind is SurfaceKind.CYLINDER
    ]
    if not contains_six_cycle(cylindrical_pairs):
        return frozenset()
    eligible: list[tuple[BlendFact, FaceNode, FaceNode]] = []
    for chain in geometry.blend_facts():
        if chain.side != "convex" or len(chain.blend_faces) != 1:
            continue
        if any(len(support) != 1 for support in chain.supports):
            continue
        left_ref = next(iter(chain.supports[0]))
        right_ref = next(iter(chain.supports[1]))
        left = nodes_by_ref[left_ref]
        right = nodes_by_ref[right_ref]
        support_facts = (geometry.surface_fact(left_ref), geometry.surface_fact(right_ref))
        if left is right or any(
            not isinstance(fact, AnalyticSurface) or fact.kind is not SurfaceKind.PLANE
            for fact in support_facts
        ):
            continue
        normals = (graph.normal(left), graph.normal(right))
        if any(normal is None or abs(normal[2]) > _SIDE_VERTICAL_COS for normal in normals):
            continue
        left_span = graph.bounds(left)[2]
        right_span = graph.bounds(right)[2]
        if any(abs(a - b) > tol for a, b in zip(left_span, right_span, strict=True)):
            continue
        eligible.append((chain, left, right))

    eligible_pairs = tuple(frozenset((left, right)) for _chain, left, right in eligible)
    selected_indices = _six_support_cycle_indices(eligible_pairs)
    selected = [eligible[at][0] for at in selected_indices]
    selected_pairs = [eligible_pairs[at] for at in selected_indices]

    if not selected:
        return frozenset()
    bridges = geometry.collapsed_bridges(tuple(chain.ref for chain in selected))
    for chain, pair in zip(selected, selected_pairs, strict=True):
        left, right = tuple(pair)
        support_refs = frozenset((face_refs[left], face_refs[right]))
        arcs = tuple(
            bridge for bridge in bridges if frozenset(bridge.supports) == support_refs
        )
        if len(arcs) != 1:
            raise ValueError("selected Polygonal Boss blend chain has no unique logical bridge")
        provenance = arcs[0].provenance
        expected_nodes = frozenset((*chain.blend_faces, *chain.supports[0], *chain.supports[1]))
        if provenance.faces != expected_nodes or Counter(provenance.boundary) != Counter(
            chain.boundary
        ):
            raise ValueError("selected Polygonal Boss bridge lost original provenance")
    return frozenset(selected_pairs)


def _regular_ring_order(
    component: tuple[_K, ...],
    headings: Mapping[_K, tuple[float, float, float]],
    angle_tol: float,
) -> tuple[_K, ...] | None:
    """Order a side ring by heading, or reject it as not a regular polygon.

    Two independent proofs, both needed: the headings are evenly spaced, and each side faces
    directly away from the one opposite it. Even spacing alone admits a ring that spirals; the
    opposed test alone admits an irregular polygon whose pairs happen to be parallel.
    """

    side_count = len(component)

    def heading_angle(key: _K) -> float:
        across, along, _ = headings[key]
        return math.atan2(along, across)

    ordered = tuple(sorted(component, key=heading_angle))
    angles = [heading_angle(i) % (2 * math.pi) for i in ordered]
    gaps = [(angles[(i + 1) % side_count] - angles[i]) % (2 * math.pi) for i in range(side_count)]
    expected_gap = 2 * math.pi / side_count
    if any(abs(gap - expected_gap) > angle_tol for gap in gaps):
        return None
    opposite = side_count // 2
    if any(
        headings[ordered[i]][0] * headings[ordered[i + opposite]][0]
        + headings[ordered[i]][1] * headings[ordered[i + opposite]][1]
        > -math.cos(angle_tol)
        for i in range(opposite)
    ):
        return None
    return ordered


def _ring_profile(
    ordered: tuple[_K, ...],
    headings: Mapping[_K, tuple[float, float, float]],
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
        headings[index][0] * float(point.X) + headings[index][1] * float(point.Y)
        for index, point in zip(ordered, centres, strict=True)
    ]
    midplanes = [
        (
            headings[ordered[i]][0],
            headings[ordered[i]][1],
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
        offset - headings[index][0] * cx - headings[index][1] * cy
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
    part: Part,
    *,
    tol: float | None,
    angle_tol: float,
    whole_stock: bool = False,
    graph: FaceGraph | None = None,
) -> list[_PolygonalProposal]:
    tol = _TOL if tol is None else tol
    # The graph holds the face inventory, the adjacency and the per-face attributes this
    # module used to keep three private maps for. Its accessors memoise on first ask, which is
    # the property the hand-rolled cache here existed for: only the vertical sides and the few
    # faces bounding a ring are ever asked about, and resolving the rest measured at more than
    # half of this recogniser's total time on the corpus.
    #
    # Memoising is also why an aggregate should hand its own graph down rather than let this
    # build a second one over the same faces: the run has already resolved some of them.
    if graph is None:
        graph = FaceGraph(part)
    else:
        # A graph over the wrong solid would not raise here on its own -- it would answer
        # questions about the wrong faces, and a boss found on one solid would be reported for
        # another. Checked rather than trusted, as `_rings` checks its own caller.
        faces = tuple(part.faces())
        resolved = {graph.require_node(face) for face in faces}
        if len(resolved) != len(faces) or len(resolved) != len(graph):
            raise ValueError("supplied Polygonal Boss graph does not exactly match the part")

    vertical = _vertical_side_faces(graph, tol)
    if len(vertical) < 6:
        return []
    blend_bridges = (
        frozenset()
        if whole_stock
        else _polygonal_boss_blend_bridges(graph, vertical, tol)
    )

    def shares_edge(i: FaceNode, j: FaceNode) -> bool:
        return j in graph.neighbours(i) or frozenset((i, j)) in blend_bridges

    components = _side_rings(vertical, graph, tol, shares_edge)

    def adjacent_to(node: FaceNode) -> set[FaceNode]:
        # A fresh set each time: `_common_cap` subtracts from what it gets back, and the graph
        # hands out a tuple precisely so one ring's bookkeeping cannot corrupt the next one's.
        return set(graph.neighbours(node))

    found: list[_PolygonalProposal] = []
    for component in components:
        side_count = len(component)
        # The accepted corpus proves hexagonal bosses. Broader polygon classes need their own
        # corpus evidence before automatic recognition can claim them.
        if side_count != 6:
            continue
        # Whole stock is intentionally the exact-prism class: one closed solid made only
        # from this side ring and its two terminal caps. Attached bosses, recesses, holes,
        # chamfers and assemblies need different ownership/evidence.
        if whole_stock and len(graph) != side_count + 2:
            continue
        component_set = set(component)
        if any(
            len({other for other in component_set if other != side and shares_edge(side, other)})
            != 2
            for side in component
        ):
            continue

        # Sourced from the graph's memo, not re-derived -- but handed on as a plain mapping,
        # because these two are pure geometry over headings and have their own unit tests.
        # Making them take the graph would have coupled a polygon calculation to a B-Rep.
        headings = {node: _heading(graph, node) for node in component}
        ordered = _regular_ring_order(component, headings, angle_tol)
        if ordered is None:
            continue
        centres = [graph.face(i).center() for i in ordered]
        profile = _ring_profile(ordered, headings, centres, tol)
        if profile is None:
            continue
        cx, cy, across = profile

        wall_lo = sum(graph.bounds(i)[2][0] for i in component) / side_count
        wall_hi = sum(graph.bounds(i)[2][1] for i in component) / side_count
        base = _common_cap(
            component,
            graph,
            adjacent_to,
            tol,
            upper=False,
            positive=not whole_stock,
            wall_lo=wall_lo,
            wall_hi=wall_hi,
        )
        top = _common_cap(
            component,
            graph,
            adjacent_to,
            tol,
            upper=True,
            positive=True,
            wall_lo=wall_lo,
            wall_hi=wall_hi,
        )
        if base is None or top is None or top.z - base.z <= tol:
            continue
        if whole_stock and (abs(base.z - wall_lo) > tol or abs(top.z - wall_hi) > tol):
            continue
        flat_centres = tuple(
            (round(float(point.X), 3), round(float(point.Y), 3), round(float(point.Z), 3))
            for point in centres
        )
        flat_directions = tuple(
            (round(headings[index][0], 3), round(headings[index][1], 3), 0.0) for index in ordered
        )
        record_type = PolygonalStock if whole_stock else PolygonalBoss
        record = record_type(
            axis="z",
            center=(round(cx, 4), round(cy, 4), round((base.z + top.z) / 2, 4)),
            side_count=side_count,
            across_flats=round(across, 4),
            base=round(base.z, 4),
            top=round(top.z, 4),
            flat_directions=flat_directions,
            flat_centres=flat_centres,
        )
        found.append(
            _PolygonalProposal(
                record,
                tuple(graph.face(node) for node in ordered),
                graph.face(base.node),
                graph.face(top.node),
            )
        )
    return found


def recognise_polygonal_bosses(
    part: Part,
    *,
    tol: float | None = None,
    angle_tol: float = math.radians(2),
    graph: FaceGraph | None = None,
) -> list[PolygonalBoss]:
    """Return regular hexagonal Z-axis bosses independently per physical solid.

    A candidate is accepted from a closed ring of outward planar side faces, opposed
    support planes with one A/F value, and common attached support/top caps. A whole prism,
    a blind recess, or faces assembled across separate solids cannot satisfy that evidence.

    *graph* is an existing graph over *part*, from a caller running several recognisers over
    one solid. It is used only when *part* is a single solid: with more than one, this looks at
    each solid separately on purpose -- a ring assembled from faces of two solids is not a boss
    -- and a whole-part graph would be the wrong inventory to ask.
    """
    return _discover_polygonal_bosses(part, tol=tol, angle_tol=angle_tol, graph=graph)


def _discover_polygonal_bosses(
    part: Part,
    *,
    tol: float | None = None,
    angle_tol: float = math.radians(2),
    graph: FaceGraph | None = None,
    writer: EvidenceWriter | None = None,
) -> list[PolygonalBoss]:
    """Shared Polygonal Boss discovery with optional aggregate evidence issuance."""

    solids = list(part.solids())
    sources = solids if len(solids) > 1 else [part]
    shared = graph if len(sources) == 1 else None
    proposals = sorted(
        (
            proposal
            for solid in sources
            for proposal in _recognise_one(solid, tol=tol, angle_tol=angle_tol, graph=shared)
            if isinstance(proposal.record, PolygonalBoss)
        ),
        key=lambda proposal: proposal.record,
    )
    records = [cast("PolygonalBoss", proposal.record) for proposal in proposals]
    if writer is None:
        return records
    if shared is not None and shared is not writer.graph:
        raise ValueError("Polygonal Boss discovery graph does not match its evidence writer")

    pending: list[tuple[PolygonalBoss, tuple[FaceNode, ...]]] = []
    used: set[FaceNode] = set()
    for proposal, record in zip(proposals, records, strict=True):
        resolved = {writer.graph.require_node(face) for face in proposal.side_faces}
        nodes = tuple(node for node in writer.graph.nodes if node in resolved)
        if len(nodes) != 6:
            raise ValueError("a Polygonal Boss requires six distinct original side faces")
        if used & resolved:
            raise ValueError("Polygonal Boss occurrences share defining side faces")
        if writer.graph.common_valid_solid(nodes) is None:
            raise ValueError("Polygonal Boss side faces do not belong to one valid solid")
        used.update(resolved)
        pending.append((record, nodes))
    for record, nodes in pending:
        writer.add_defining(record, nodes, family=FamilyId.POLYGONAL_BOSSES)
    return records


def recognise_polygonal_stock(
    part: Part,
    *,
    tol: float | None = None,
    angle_tol: float = math.radians(2),
    graph: FaceGraph | None = None,
) -> list[PolygonalStock]:
    """Return one record only when the complete part is a regular hexagonal prism.

    The exact-prism boundary is fail closed: multi-solid assemblies and solids with any
    additional or missing face are not silently promoted to stock.

    *graph* is an existing graph over *part*, as above. This one asks about the whole part and
    only ever with a single solid, so there is no case where the caller's graph is the wrong
    inventory.
    """
    return _discover_polygonal_stock(
        part,
        tol=tol,
        angle_tol=angle_tol,
        graph=graph,
    )


def _discover_polygonal_stock(
    part: Part,
    *,
    tol: float | None = None,
    angle_tol: float = math.radians(2),
    graph: FaceGraph | None = None,
    writer: EvidenceWriter | None = None,
) -> list[PolygonalStock]:
    """Discover exact-prism stock and optionally issue its complete eight-face boundary."""

    if len(list(part.solids())) != 1 or len(list(part.faces())) != 8:
        return []
    if graph is not None and writer is not None and graph is not writer.graph:
        raise ValueError("Polygonal Stock graph and writer must share one authority")
    owner = writer.graph if writer is not None else graph
    proposals = sorted(
        (
            proposal
            for proposal in _recognise_one(
                part, tol=tol, angle_tol=angle_tol, whole_stock=True, graph=owner
            )
            if isinstance(proposal.record, PolygonalStock)
        ),
        key=lambda proposal: proposal.record,
    )
    records = [cast("PolygonalStock", proposal.record) for proposal in proposals]
    if writer is None:
        return records

    pending: list[tuple[PolygonalStock, tuple[FaceNode, ...]]] = []
    for proposal, record in zip(proposals, records, strict=True):
        resolved = {
            writer.graph.require_node(face)
            for face in (*proposal.side_faces, proposal.lower_cap, proposal.upper_cap)
        }
        nodes = tuple(node for node in writer.graph.nodes if node in resolved)
        if len(nodes) != 8 or resolved != set(writer.graph.nodes):
            raise ValueError("Polygonal Stock requires its complete eight-face graph inventory")
        if writer.graph.common_valid_solid(nodes) is None:
            raise ValueError("Polygonal Stock boundary does not prove one valid solid")
        pending.append((record, nodes))
    for record, nodes in pending:
        writer.add_defining(record, nodes, family=FamilyId.POLYGONAL_STOCK)
    return records
