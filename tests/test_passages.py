# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""A passage, and the two things it is not.

Every test here is built around one block with one void through it, varied in exactly one way
at a time: capped at an end (a pocket), filled instead of hollow (a boss), or left open (a
passage). The pairing is the point -- a fixture that differed in several ways at once could
pass for reasons unrelated to the gate it names.
"""

from __future__ import annotations

import pytest
from build123d import (
    Box,
    BuildPart,
    BuildSketch,
    Compound,
    Face,
    Locations,
    Plane,
    Polygon,
    Pos,
    RegularPolygon,
    Rot,
    Shell,
    Solid,
    Vector,
    Wire,
    chamfer,
    export_step,
    extrude,
    fillet,
    import_step,
)
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_IN

from b123d_recognisers import (
    Passage,
    build_recognition_result,
    recognise_passages,
    recognise_slots,
)
from b123d_recognisers._adjacency import FaceEdges, FaceGraph
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._rings import _canonical, _centroid, _interior_point, _wall_regions


def _block() -> Box:
    return Box(60, 40, 20)


def _hexagonal_passage():
    """A six-walled void running the full depth in Z, open at both ends."""

    with BuildPart() as bore:
        with BuildSketch(Plane.XY):
            RegularPolygon(9, 6)
        extrude(amount=40, both=True)
    return _block() - bore.part


def _planar_face(*points):
    return Face(Wire.make_polygon([Vector(*point) for point in points], close=True))


def _split_square_passage(scale: float = 1.0) -> Solid:
    """One unchanged square void whose four logical walls are eight sewn face patches."""

    part = Box(60 * scale, 40 * scale, 20 * scale) - Box(30 * scale, 10 * scale, 30 * scale)
    walls = [
        face
        for face in part.faces()
        if abs(face.center().Z) <= 1e-9
        and (
            abs(abs(face.center().X) - 15 * scale) <= 1e-9
            or abs(abs(face.center().Y) - 5 * scale) <= 1e-9
        )
    ]
    assert len(walls) == 4
    x0, x1, y0, y1, z0, z1 = (value * scale for value in (-15, 15, -5, 5, -10, 10))
    split = {"yp": -3 * scale, "yn": 2 * scale, "xp": 4 * scale, "xn": -5 * scale}
    patches = [
        _planar_face((x0, y1, z0), (x1, y1, z0), (x1, y1, split["yp"]), (x0, y1, split["yp"])),
        _planar_face((x0, y1, split["yp"]), (x1, y1, split["yp"]), (x1, y1, z1), (x0, y1, z1)),
        _planar_face((x0, y0, z0), (x0, y0, split["yn"]), (x1, y0, split["yn"]), (x1, y0, z0)),
        _planar_face((x0, y0, split["yn"]), (x0, y0, z1), (x1, y0, z1), (x1, y0, split["yn"])),
        _planar_face((x1, y0, z0), (x1, y0, split["xp"]), (x1, y1, split["xp"]), (x1, y1, z0)),
        _planar_face((x1, y0, split["xp"]), (x1, y0, z1), (x1, y1, z1), (x1, y1, split["xp"])),
        _planar_face((x0, y0, z0), (x0, y1, z0), (x0, y1, split["xn"]), (x0, y0, split["xn"])),
        _planar_face((x0, y0, split["xn"]), (x0, y1, split["xn"]), (x0, y1, z1), (x0, y0, z1)),
    ]
    solid = Solid(
        Shell(
            [
                *(face for face in part.faces() if not any(face.is_same(wall) for wall in walls)),
                *patches,
            ]
        )
    )
    assert solid.is_valid
    return solid


def _split_one_z_wall(part, wall, at: float = 0.0) -> Solid:
    """Replace one vertical quadrilateral by two orientation-preserving sewn patches."""

    low = sorted(
        (tuple(vertex) for vertex in wall.vertices() if at > vertex.Z),
        key=lambda point: point[:2],
    )
    high = sorted(
        (tuple(vertex) for vertex in wall.vertices() if at < vertex.Z),
        key=lambda point: point[:2],
    )
    assert len(low) == len(high) == 2
    middle = [(point[0], point[1], at) for point in low]

    def oriented(*points):
        face = _planar_face(*points)
        if face.normal_at().dot(wall.normal_at()) < 0:
            face = _planar_face(*points[::-1])
        return face

    patches = (
        oriented(low[0], low[1], middle[1], middle[0]),
        oriented(middle[0], middle[1], high[1], high[0]),
    )
    solid = Solid(Shell([*(face for face in part.faces() if not face.is_same(wall)), *patches]))
    assert solid.is_valid
    return solid


def test_a_void_open_at_both_ends_is_a_passage():
    passages = recognise_passages(_hexagonal_passage())

    assert len(passages) == 1
    passage = passages[0]
    assert passage.axis == "z"
    assert passage.sides == 6
    assert passage.length == 20.0


def test_coplanar_wall_subdivisions_preserve_one_passage_and_all_claim_evidence():
    """A gAAG logical wall removes representation splits without changing feature geometry."""

    part = _split_square_passage()
    ledger = ClaimLedger(FaceGraph(part))

    (passage,) = recognise_passages(part, ledger=ledger)

    assert passage == Passage(
        axis="z",
        sides=4,
        length=20.0,
        at=(0.0, 0.0, 0.0),
        section=((-15.0, -5.0), (15.0, -5.0), (15.0, 5.0), (-15.0, 5.0)),
    )
    assert len(ledger.defining_of(passage)) == 8


def test_wall_normalization_is_not_specialized_to_rectangular_sections():
    """An oblique hexagon wall split is still one logical side, not two taxonomy sides."""

    plain = _hexagonal_passage()
    wall = next(
        face
        for face in plain.faces()
        if abs(face.center().Z) < 1e-9
        and abs(face.normal_at().Z) < 1e-9
        and abs(face.normal_at().X) < 0.99
        and abs(face.normal_at().Y) < 0.99
    )
    split = _split_one_z_wall(plain, wall)
    ledger = ClaimLedger(FaceGraph(split))

    (passage,) = recognise_passages(split, ledger=ledger)

    assert passage == recognise_passages(plain)[0]
    assert passage.sides == 6
    assert len(ledger.defining_of(passage)) == 7


def test_split_wall_passage_is_stable_across_step_roundtrip_axes_and_scale(tmp_path):
    """Normalization is geometric, not tied to sewing order, Z, or millimetre-sized fixtures."""

    base = _split_square_passage()
    path = tmp_path / "split-wall-passage.step"
    export_step(base, path)
    assert recognise_passages(import_step(path)) == recognise_passages(base)

    for part, axis in (
        (base, "z"),
        (Rot(90, 0, 0) * base, "y"),
        (Rot(0, 90, 0) * base, "x"),
    ):
        (passage,) = recognise_passages(part)
        assert passage.axis == axis
        assert passage.sides == 4

    for scale in (0.001, 1000.0):
        (passage,) = recognise_passages(_split_square_passage(scale))
        assert passage.sides == 4
        assert passage.length == pytest.approx(20 * scale, abs=max(0.001, scale * 1e-6))


def test_aggregate_keeps_the_complete_split_wall_ring_over_slot_fragments():
    """Patch-local paired walls cannot defeat the complete normalized physical boundary."""

    result = build_recognition_result(_split_square_passage())

    assert result.slots == ()
    assert len(result.passages) == 1
    assert result.passages[0].sides == 4


def test_one_split_wall_is_enough_to_identify_patch_local_slot_fragments():
    """The opposite logical wall need not also be subdivided for the artifact to be local."""

    plain = Box(60, 40, 20) - Box(30, 10, 30)
    wall = next(
        face
        for face in plain.faces()
        if abs(face.center().Y - 5) < 1e-8
        and abs(face.center().Z) < 1e-8
        and face.area < 1000
    )
    result = build_recognition_result(_split_one_z_wall(plain, wall, at=0))

    assert result.slots == ()
    assert len(result.passages) == 1


def test_normalization_does_not_promote_offset_or_branched_voids_to_one_sweep():
    """Smooth coplanar patches are harmless; changed sections and branches are feature geometry."""

    offset = Box(40, 40, 40) - (Pos(0, 0, -10) * Box(10, 10, 20) + Pos(2, 0, 10) * Box(10, 10, 20))
    assert recognise_passages(offset) == []

    main = Box(40, 40, 40) - Box(10, 10, 60)
    branched = main - Box(60, 4, 4)
    before = recognise_passages(main)
    after = recognise_passages(branched)
    assert [item for item in after if item.axis == "z"] == before
    assert not any(item.axis == "x" and item.length == 40 for item in after)


def test_notched_coplanar_patches_do_not_become_one_logical_wall():
    """Connectivity and a common plane cannot erase the actual non-rectangular boundary."""

    lower = _planar_face((0, 0, 0), (1, 0, 0), (1, 0, 2), (0, 0, 2))
    upper = _planar_face((1, 0, 1), (2, 0, 1), (2, 0, 2), (1, 0, 2))
    graph = FaceGraph(Shell([lower, upper]))
    nodes = list(graph.nodes)
    assert graph.coplanar_region(nodes[0]) == frozenset(nodes)

    regions = _wall_regions(graph, nodes, axis=2)

    assert len(regions) == 2
    assert all(len(region.nodes) == 1 for region in regions)


def test_a_through_slot_is_reported_here_too_and_the_aggregate_resolves_it():
    """The reconciliation is the aggregate's, and it compares faces rather than coordinates.

    A through slot *is* a closed uncapped ring, so this family sees it. An earlier draft
    suppressed it inside the recogniser by asking `recognise_slots` what it had found, which
    ADR 0002 forbids -- recognisers do not call siblings -- and ADR 0003 forbids by name. So
    the recogniser now reports the ring, and `build_recognition_result` drops it because the
    slot's two walls sit inside the passage's ring.
    """

    slotted = Box(130, 150, 16) - Box(30, 8, 60)
    assert recognise_slots(slotted), "the fixture must be a recognisable slot"
    assert [p.sides for p in recognise_passages(slotted)] == [4], "the candidate is reported"

    result = build_recognition_result(slotted)
    assert result.slots, "the slot is what survives, because it dimensions the void"
    assert result.passages == (), "and the passage it also is, does not"

    # A four-walled void no slot claims is still a passage: the side count was never the point.
    square = Box(60, 40, 20) - Box(10, 10, 60)
    assert recognise_slots(square) == []
    assert [p.sides for p in build_recognition_result(square).passages] == [4]


def test_a_passage_crossing_a_slot_only_in_projection_survives():
    """The regression for the heuristic that was replaced.

    The old rule compared a ring's averaged centre with a slot record's centre in X and Y
    within 1e-6, ignoring the run axis and Z entirely. Two solids, one carrying a Z-through
    slot and one an X-through passage at the same XY, are therefore the same feature to it and
    share not one face. Reconciling on claimed faces cannot make this mistake.
    """

    slotted = Box(120, 60, 20) - Box(10, 30, 60)
    bored = Pos(0, 0, 100) * (Box(120, 60, 20) - Box(200, 8, 8))
    part = Compound(children=[slotted, bored])

    result = build_recognition_result(part)
    assert result.slots, "the Z slot"
    assert [p.axis for p in result.passages] == ["x"], "the X passage, at the same XY, survives"


def test_the_same_void_with_a_floor_is_a_pocket_and_not_a_passage():
    """The control, differing in one way: the void stops inside the block.

    A pocket's ring is capped by a face perpendicular to the run axis that fills the ring's
    cross-section. That the cap must *fill* it is the whole subtlety -- at a passage mouth the
    block's own end face is perpendicular and edge-adjacent too, and a test that only looked
    for a perpendicular neighbour rejected every passage there is.
    """

    with BuildPart() as bore:
        with BuildSketch(Plane.XY):
            RegularPolygon(9, 6)
        extrude(amount=14)
    blind = _block() - Pos(0, 0, -4) * bore.part

    assert recognise_passages(blind) == []


def test_a_column_of_material_is_not_a_passage():
    """The same ring of walls, with the material inside it rather than outside.

    A hexagonal column joining two plates is bounded by an identical closed uncapped ring, and
    only the solid-classifier probe separates it from a void. The fixture matters: a boss
    standing *on* a plate is rejected by the cap test instead, so a test written around one
    passes with the probe deleted and proves nothing about it. This one does not -- without the
    probe it reports a passage.
    """

    with BuildPart() as column:
        with BuildSketch(Plane.XY):
            RegularPolygon(10, 6)
        extrude(amount=30)
    joined = _block() + Pos(0, 0, 26) * _block() + Pos(0, 0, -4) * column.part

    assert recognise_passages(joined) == []


def test_the_side_count_is_the_polygon_and_not_a_class():
    """MFCAD++ names triangular, rectangular and six-sided passages separately; the geometry
    does not, so one recogniser reports the count and the caller reads it."""

    with BuildPart() as tri:
        with BuildSketch(Plane.XZ):
            Polygon((-8, -6), (8, -6), (0, 8))
        extrude(amount=60, both=True)
    triangular = _block() - tri.part

    found = recognise_passages(triangular)
    assert len(found) == 1
    assert found[0].sides == 3
    assert found[0].axis == "y"


def test_two_passages_on_one_part_are_reported_separately_and_in_order():
    with BuildPart() as bores:
        with BuildSketch(Plane.XY):
            RegularPolygon(7, 6)
            with Locations((22, 0)):
                RegularPolygon(6, 6)
        extrude(amount=40, both=True)
    part = _block() - bores.part
    found = recognise_passages(part)

    assert len(found) == 2
    assert found == sorted(found, key=lambda p: (p.axis, p.at))
    assert all(isinstance(p, Passage) for p in found)
    assert recognise_passages(part) == found


def test_a_passage_is_a_passage_at_any_scale():
    """No gate mentions the part, so scaling the model changes nothing but the numbers."""

    small = recognise_passages(_hexagonal_passage())
    with BuildPart() as big_bore:
        with BuildSketch(Plane.XY):
            RegularPolygon(180, 6)
        extrude(amount=800, both=True)
    big = recognise_passages(Box(1200, 800, 400) - big_bore.part)

    assert len(small) == len(big) == 1
    assert small[0].axis == big[0].axis and small[0].sides == big[0].sides
    assert round(big[0].length / 20, 3) == small[0].length


def test_a_part_with_no_void_has_no_passages():
    assert recognise_passages(_block()) == []


def test_a_shared_face_edge_memo_does_not_change_the_result():
    """``face_edges=`` is an optimisation, never a behaviour switch."""

    part = _hexagonal_passage()
    plain = recognise_passages(part)

    assert plain, "the fixture must reach the scan for this comparison to mean anything"
    assert plain == recognise_passages(part, face_edges=FaceEdges())


def test_a_blind_void_stays_a_pocket_when_its_floor_edge_is_blended():
    """A fillet or chamfer at the bottom of a pocket does not open it into a passage.

    The cap test originally looked only at planar axis-aligned neighbours, so breaking the
    floor edge removed the only candidate and an ordinary blind pocket came back as a through
    passage. `docs/capabilities.md` publishes capped voids as an exclusion; this is what makes
    that true for manufactured geometry rather than only for sharp corners.
    """

    with BuildPart() as bore:
        with BuildSketch(Plane.XY):
            RegularPolygon(9, 6)
        extrude(amount=14)
    blind = _block() - Pos(0, 0, -4) * bore.part
    floor_edges = [e for e in blind.edges() if abs(e.center().Z - (-4)) < 1e-6]
    assert floor_edges, "the fixture must have a floor edge to blend"

    assert recognise_passages(blind) == []
    assert recognise_passages(fillet(floor_edges, 2.0)) == []
    assert recognise_passages(chamfer(floor_edges, 1.5)) == []


def _twice_area(section) -> float:
    count = len(section)
    return sum(
        section[at][0] * section[(at + 1) % count][1]
        - section[(at + 1) % count][0] * section[at][1]
        for at in range(count)
    )


def _is_material(part, point, along) -> bool:
    probe = BRepClass3d_SolidClassifier(part.wrapped)
    probe.Perform(gp_Pnt(point[0], point[1], along), 1e-6)
    return probe.State() == TopAbs_IN


def test_the_cross_section_is_the_corners_a_consumer_can_dimension_from():
    """`sides` names the shape; `section` measures it.

    A record carrying only a side count cannot distinguish passages of different size, aspect
    or rotation, which is what made the first version a taxonomy label rather than a dimension.
    The corners are pinned against the sketch they were cut from, in part coordinates.
    """

    with BuildPart() as tri:
        with BuildSketch(Plane.XZ):
            Polygon((-8, -6), (8, -6), (0, 8))
        extrude(amount=60, both=True)
    (passage,) = recognise_passages(Box(120, 60, 40) - tri.part)

    assert passage.axis == "y"
    assert passage.sides == 3
    assert passage.section == ((-8.0, -6.0), (8.0, -6.0), (0.0, 8.0))
    # Canonical, so the kernel's traversal cannot reach the record: anticlockwise, from the
    # lexicographically smallest corner.
    assert passage.section[0] == min(passage.section)
    assert _twice_area(passage.section) > 0


def test_a_concave_cross_section_is_probed_from_a_point_inside_it():
    """The material test needs a point in the void, and an average is not one.

    A U-shaped passage's own area centroid falls in the material between its arms. Probing
    there answers "material inside the ring" and calls the void a prism -- so the fixture is
    built to prove the construction rather than to exercise it: the centroid is asserted to be
    in material while the passage is still reported.
    """

    with BuildPart() as slot_u:
        with BuildSketch(Plane.XY):
            Polygon(
                (-15, -15), (15, -15), (15, 15), (9, 15), (9, -9), (-9, -9), (-9, 15), (-15, 15)
            )
        extrude(amount=40, both=True)
    part = Box(60, 60, 20) - slot_u.part

    (passage,) = recognise_passages(part)
    assert passage.sides == 8
    assert _is_material(part, _centroid(passage.section), passage.at[2]), (
        "the fixture must be one the centroid gets wrong"
    )
    assert not _is_material(part, _interior_point(passage.section), passage.at[2])


def test_a_passage_records_the_ring_it_was_built_from():
    """The claim is the ring, and nothing it merely touched.

    Reconciliation reads these, so a claim over the end faces a passage opens onto would have
    it contest every feature at its mouth.
    """

    part = _hexagonal_passage()
    ledger = ClaimLedger(FaceGraph(part))
    (passage,) = recognise_passages(part, ledger=ledger)

    (claim,) = ledger.claims
    assert claim.claimant is passage
    assert len(claim.defining) == passage.sides
    for node in claim.defining:
        assert ledger.graph.is_planar(node)
        normal = ledger.graph.normal(node)
        assert abs(normal[2]) <= 0.01, "a wall runs along the passage, not across it"


def test_a_cross_section_that_is_not_a_simple_polygon_is_refused():
    """The corners are read from the kernel, so the walk must not assume they form a shape.

    Declining is what a decline looks like here: `_canonical` returns None and the ring is
    dropped, rather than a record being emitted with an area of zero or a corner counted twice.
    """

    assert _canonical([(0.0, 0.0), (1.0, 0.0), (0.0, 0.0)]) is None, "a repeated corner"
    assert _canonical([(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]) is None, "collinear corners"
    assert _canonical([(1.0, 1.0), (0.0, 0.0), (1.0, 0.0)]) == (
        (0.0, 0.0),
        (1.0, 0.0),
        (1.0, 1.0),
    ), "and a real triangle comes back anticlockwise from its smallest corner"


def test_an_interior_point_is_inside_the_polygon_and_not_merely_near_it():
    """Checked against the polygon itself, so the construction stands without a solid.

    The two branches are the ones that matter: a convex shape, where the ear is empty, and a
    concave one, where another corner intrudes into it and the diagonal is used instead.
    """

    triangle = ((-8.0, -6.0), (8.0, -6.0), (0.0, 8.0))
    u_shape = (
        (-15.0, -15.0),
        (15.0, -15.0),
        (15.0, 15.0),
        (9.0, 15.0),
        (9.0, -9.0),
        (-9.0, -9.0),
        (-9.0, 15.0),
        (-15.0, 15.0),
    )
    for polygon in (triangle, u_shape):
        assert _winds_around(polygon, _interior_point(polygon)), polygon
    # The centroid is the thing this replaces, and the U is where it fails.
    assert not _winds_around(u_shape, _centroid(u_shape))


def _winds_around(polygon, point) -> bool:
    """Crossing-number point-in-polygon, written out rather than reusing the module's own."""

    inside = False
    count = len(polygon)
    for at in range(count):
        (ux, uy), (vx, vy) = polygon[at], polygon[(at + 1) % count]
        if (uy > point[1]) != (vy > point[1]):
            crossing = ux + (point[1] - uy) * (vx - ux) / (vy - uy)
            if point[0] < crossing:
                inside = not inside
    return inside


def test_a_feature_cut_into_a_wall_partway_along_does_not_cap_the_passage():
    """A neighbour inside the run, touching neither end, is not a floor.

    The cap test asks whether something sits *across* an end of the span. A notch milled into
    one wall halfway along overlaps the span and reaches neither end, and rejecting it on
    proximity alone would lose the passage. This is the branch that says so.
    """

    part = Box(60, 40, 20) - Box(10, 10, 60) - Pos(7, 0, 0) * Box(6, 6, 4)
    (passage,) = recognise_passages(part)

    assert passage.axis == "z"
    assert passage.length == 20.0
    assert passage.section == ((-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0))


def test_a_ledger_built_from_another_part_is_refused_rather_than_answered():
    """A family that *walks* the graph is not refused for free, unlike one that resolves faces.

    Every other family turns a face into a node as it goes, so a graph paired with the wrong
    part raises on the first lookup. This one starts from the graph's own nodes and never asks
    it about *this* part at all -- so before the shared walk checked, it happily reported a
    record describing the other solid. Silently answering the wrong question is worse than
    refusing, which is the whole reason `require_node` exists.
    """

    part, twin = _hexagonal_passage(), _hexagonal_passage()
    assert recognise_passages(twin) == recognise_passages(part), "the twin is this part"

    foreign = ClaimLedger(FaceGraph(twin))
    try:
        recognise_passages(part, ledger=foreign)
    except ValueError as refusal:
        assert "built from a different part" in str(refusal)
    else:
        raise AssertionError("recognise_passages answered about another part's graph")
