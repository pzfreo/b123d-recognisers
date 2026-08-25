"""Issue #236 Pocket evidence lifecycle and closed failure boundaries."""

from __future__ import annotations

import ast
import inspect
import math
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from build123d import (
    Box,
    Compound,
    Cylinder,
    Edge,
    GeomType,
    Plane,
    Pos,
    Rot,
    Shell,
    export_step,
    import_step,
)
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepFeat import BRepFeat_SplitShape
from OCP.GeomAbs import GeomAbs_Cylinder

from b123d_recognisers._adjacency import FaceEdges, FaceGraph, FaceNode
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._recess_core import (
    _bounds_one_void,
    _pocket_proposals_one,
    _uninterrupted_long_span,
)
from b123d_recognisers._recess_faces import (
    _AXIS_ALIGNED_TOL,
    _FLOOR_COVER_FRAC,
    _FLOOR_TOL,
    _MERGE_TOL,
    _dominant_axis,
    _end_capped,
    _Face,
    _is_wall,
)
from b123d_recognisers._recess_features import _discover_pockets, _PocketAttributionError
from b123d_recognisers._recess_obround import (
    _extend_obround_proposals,
    _obround_ends,
    _recognise_obround_from_ends,
)
from b123d_recognisers._recess_records import Pocket
from b123d_recognisers._recess_reduce import _RecessProposal
from b123d_recognisers._registry import PHYSICAL_DEFINITIONS, FullyAttributed
from b123d_recognisers._run import start
from b123d_recognisers.result import _discover_all

ROOT = Path(__file__).parents[1]
AXIS = {"x": 0, "y": 1, "z": 2}


def _body_key(solid):
    box = solid.bounding_box()
    return (*tuple(box.min), *tuple(box.max), float(solid.volume), float(solid.area))


def _fresh_occurrences(part):
    """Topology-first Pocket inventory; deliberately uses no recess implementation helper."""
    aggregate = FaceGraph(part)
    solids = list(part.solids())
    sources = solids if len(solids) > 1 else [part]
    body_keys = [_body_key(solid) for solid in sources]
    out = []
    for solid, raw_key in zip(sources, body_keys, strict=True):
        graph = FaceGraph(solid)
        box = solid.bounding_box()
        extent = (box.size.X, box.size.Y, box.size.Z)
        planes = []
        cylinders = []
        for node in graph.nodes:
            if not graph.is_planar(node):
                adaptor = BRepAdaptor_Surface(graph.face(node).wrapped)
                if adaptor.GetType() == GeomAbs_Cylinder:
                    cylinder = adaptor.Cylinder()
                    direction = cylinder.Axis().Direction()
                    vector = (abs(direction.X()), abs(direction.Y()), abs(direction.Z()))
                    axis = max(range(3), key=vector.__getitem__)
                    if vector[axis] >= 0.999999:
                        point = cylinder.Location()
                        cylinders.append(
                            (
                                node,
                                axis,
                                cylinder.Radius(),
                                (point.X(), point.Y(), point.Z()),
                                graph.bounds(node),
                            )
                        )
                continue
            normal = graph.normal(node)
            if normal is None:
                continue
            axis = max(range(3), key=lambda i: abs(normal[i]))
            if abs(normal[axis]) >= 0.999999:
                planes.append((node, axis, normal[axis], graph.bounds(node)))
        records = []
        for i, left in enumerate(planes):
            for right in planes[i + 1 :]:
                ln, wi, ls, lb = left
                rn, ri, rs, rb = right
                if wi != ri or ls * rs >= 0:
                    continue
                la, ra = sum(lb[wi]) / 2, sum(rb[wi]) / 2
                if (ra - la) * ls <= 0:
                    ln, rn, ls, lb, rb, la, ra = rn, ln, rs, rb, lb, ra, la
                if (ra - la) * ls <= 0:
                    continue
                others = [a for a in range(3) if a != wi]
                ranges = {a: (max(lb[a][0], rb[a][0]), min(lb[a][1], rb[a][1])) for a in others}
                if any(hi <= lo for lo, hi in ranges.values()):
                    continue
                for di in others:
                    li = next(a for a in others if a != di)
                    lo, hi = ranges[li]
                    dlo, dhi = ranges[di]
                    width, length = abs(ra - la), hi - lo
                    if width > length or length >= 0.9 * extent[li]:
                        continue
                    # Exactly one planar boundary spans the footprint at a depth end.
                    caps = []
                    for end, sign in ((dlo, 1), (dhi, -1)):
                        matches = [
                            n
                            for n, a, ns, b in planes
                            if a == di
                            and ns * sign > 0
                            and abs(sum(b[di]) / 2 - end) <= 1e-6
                            and b[wi][0] <= min(la, ra) + 1e-6
                            and b[wi][1] >= max(la, ra) - 1e-6
                            and b[li][0] <= lo + 1e-6
                            and b[li][1] >= hi - 1e-6
                        ]
                        caps.append(matches)
                    if bool(caps[0]) == bool(caps[1]):
                        continue
                    rec = Pocket(
                        "xyz"[wi],
                        "xyz"[li],
                        round(width, 2),
                        round(length, 2),
                        round(dhi - dlo, 2),
                        round((la + ra) / 2, 2),
                        round(lo, 2),
                        round(hi, 2),
                        round(dlo, 2),
                        round(dhi, 2),
                        1 if caps[0] else -1,
                        False,
                        raw_key if body_keys.count(raw_key) == 1 else None,
                    )
                    nodes = frozenset((ln, rn))
                    records.append((rec, nodes))
        # Corner route: three mutually perpendicular inward faces, represented by a bounded floor.
        for floor, di, fs, fb in planes:
            if di != 2:  # Frozen public corner grammar; axis redesign is under review.
                continue
            envelope = ((box.min.X, box.max.X), (box.min.Y, box.max.Y), (box.min.Z, box.max.Z))
            if min(abs(sum(fb[di]) / 2 - end) for end in envelope[di]) <= 1e-6:
                continue
            footprint = [axis for axis in range(3) if axis != di]
            if not all(
                abs(fb[axis][0] - envelope[axis][0]) <= 1e-6
                or abs(fb[axis][1] - envelope[axis][1]) <= 1e-6
                for axis in footprint
            ):
                continue
            wall_groups = []
            for axis in footprint:
                other = next(item for item in footprint if item != axis)
                lo, hi = fb[axis]
                inner = hi if abs(lo - envelope[axis][0]) <= 1e-6 else lo
                wall_groups.append(
                    [
                        (node, bounds)
                        for node, wall_axis, _sign, bounds in planes
                        if wall_axis == axis
                        and abs(sum(bounds[axis]) / 2 - inner) <= 1e-6
                        and bounds[other][0] <= fb[other][0] + 1e-6
                        and bounds[other][1] >= fb[other][1] - 1e-6
                    ]
                )
            if any(len(group) != 1 for group in wall_groups):
                continue
            first, second = footprint
            sizes = {axis: fb[axis][1] - fb[axis][0] for axis in footprint}
            wa, li = (first, second) if sizes[first] <= sizes[second] else (second, first)
            width, length = sizes[wa], sizes[li]
            wc = sum(fb[wa]) / 2
            lo, hi = fb[li]
            dlo = max(group[0][1][di][0] for group in wall_groups)
            dhi = min(group[0][1][di][1] for group in wall_groups)
            rec = Pocket(
                "xyz"[wa],
                "xyz"[li],
                round(width, 2),
                round(length, 2),
                round(dhi - dlo, 2),
                round(wc, 2),
                round(lo, 2),
                round(hi, 2),
                round(dlo, 2),
                round(dhi, 2),
                1 if fs > 0 else -1,
                True,
                raw_key if body_keys.count(raw_key) == 1 else None,
            )
            records.append((rec, frozenset((floor, *(group[0][0] for group in wall_groups)))))
        # Blind obrounds are established by two equal cylindrical endpoint regions.
        for i, left in enumerate(cylinders):
            for right in cylinders[i + 1 :]:
                ln, di, radius, lc, lb = left
                rn, rdi, rr, rc, rb = right
                if di != rdi or abs(radius - rr) > 1e-7 or lb[di] != rb[di]:
                    continue
                delta = [abs(rc[a] - lc[a]) for a in range(3)]
                li = max(range(3), key=delta.__getitem__)
                if li == di or delta[li] <= 1e-7:
                    continue
                wi = next(a for a in range(3) if a not in (li, di))
                if abs(lc[wi] - rc[wi]) > 1e-6:
                    continue
                dlo, dhi = lb[di]
                lo = min(lc[li], rc[li]) - radius
                hi = max(lc[li], rc[li]) + radius
                floor_nodes = [
                    (n, s, b)
                    for n, a, s, b in planes
                    if a == di
                    and (
                        (abs(sum(b[di]) / 2 - dlo) <= 1e-6 and s > 0)
                        or (abs(sum(b[di]) / 2 - dhi) <= 1e-6 and s < 0)
                    )
                    and b[li][1] > lo
                    and b[li][0] < hi
                ]
                if not floor_nodes:
                    continue
                rec = Pocket(
                    "xyz"[wi],
                    "xyz"[li],
                    round(2 * radius, 2),
                    round(hi - lo, 2),
                    round(dhi - dlo, 2),
                    round((lc[wi] + rc[wi]) / 2, 2),
                    round(lo, 2),
                    round(hi, 2),
                    round(dlo, 2),
                    round(dhi, 2),
                    1 if floor_nodes[0][1] > 0 else -1,
                    False,
                    raw_key if body_keys.count(raw_key) == 1 else None,
                )
                # Elongated routes also own their two planar side walls; stubby routes do not.
                walls = {
                    n
                    for n, a, _s, b in planes
                    if a == wi
                    and abs(abs(sum(b[wi]) / 2 - rec.w_center) - rec.width / 2) <= 1e-6
                    and b[li][0] >= lo - 1e-6
                    and b[li][1] <= hi + 1e-6
                    and b[di] == (dlo, dhi)
                }
                nodes = frozenset(({ln, rn} | walls) if rec.length >= 2 * rec.width else {ln, rn})
                records = [
                    item
                    for item in records
                    if not (
                        item[0].width_axis == rec.width_axis
                        and item[0].long_axis == rec.long_axis
                        and item[0].width == rec.width
                        and item[0].w_center == rec.w_center
                        and item[0].d_lo == rec.d_lo
                        and item[0].d_hi == rec.d_hi
                        and abs((item[0].lo + item[0].hi - rec.lo - rec.hi) / 2) <= 0.1
                    )
                ]
                records.append((rec, nodes))
        for record, nodes in records:
            out.append((record, frozenset(aggregate.require_node(graph.face(n)) for n in nodes)))
    out.sort(key=lambda item: (item[0].width, item[0].location))
    return aggregate, out


def _obround(length: float, width: float, depth: float):
    end = Cylinder(width / 2, depth)
    return Box(length, width, depth) + Pos(-length / 2, 0, 0) * end + Pos(length / 2, 0, 0) * end


def _fresh_expected_nodes(graph: FaceGraph, expected, *, edge_anchored: bool):
    """Reconstruct exact route roles from fresh topology before writer/Candidate access."""

    wa, la, width, length, _depth, wc, lo, hi, dlo, dhi, sign, _anchored = expected
    wi, li = AXIS[wa], AXIS[la]
    di = next(index for index in range(3) if index not in (wi, li))
    selected = set()
    for node in graph.nodes:
        bounds = graph.bounds(node)
        if graph.is_planar(node):
            normal = graph.normal(node)
            if normal is None:
                continue
            axis = max(range(3), key=lambda index: abs(normal[index]))
            at = sum(bounds[axis]) / 2
            wall = (
                axis == wi
                and abs(abs(at - wc) - width / 2) <= 1e-6
                and bounds[li][0] >= lo - 1e-6
                and bounds[li][1] <= hi + 1e-6
                and bounds[di][0] == pytest.approx(dlo)
                and bounds[di][1] == pytest.approx(dhi)
            )
            corner_wall = (
                edge_anchored
                and axis == li
                and (at == pytest.approx(lo) or at == pytest.approx(hi))
                and bounds[wi][1] > wc - width / 2
                and bounds[wi][0] < wc + width / 2
                and bounds[di][0] == pytest.approx(dlo)
                and bounds[di][1] == pytest.approx(dhi)
            )
            floor_at = dlo if sign > 0 else dhi
            floor = (
                edge_anchored
                and axis == di
                and at == pytest.approx(floor_at)
                and bounds[wi][1] > wc - width / 2
                and bounds[wi][0] < wc + width / 2
                and bounds[li][1] > lo
                and bounds[li][0] < hi
            )
            if wall or corner_wall or floor:
                selected.add(node)
            continue
        adaptor = BRepAdaptor_Surface(graph.face(node).wrapped)
        if adaptor.GetType() != GeomAbs_Cylinder:
            continue
        cylinder = adaptor.Cylinder()
        direction = cylinder.Axis().Direction()
        vector = (abs(direction.X()), abs(direction.Y()), abs(direction.Z()))
        if (
            vector[di] == pytest.approx(1.0)
            and cylinder.Radius() == pytest.approx(width / 2)
            and bounds[di][0] == pytest.approx(dlo)
            and bounds[di][1] == pytest.approx(dhi)
        ):
            selected.add(node)
    if length < 2 * width and any(not graph.is_planar(node) for node in selected):
        selected = {node for node in selected if not graph.is_planar(node)}
    return frozenset(selected)


@pytest.mark.parametrize(
    ("part", "planar", "curved", "expected"),
    [
        (
            Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8),
            2,
            0,
            ("y", "x", 12.0, 20.0, 6.0, 0.0, -10.0, 10.0, 0.0, 6.0, 1, False),
        ),
        (
            Box(60, 40, 12) - Pos(25, 15, 4) * Box(20, 20, 8),
            3,
            0,
            ("x", "y", 15.0, 15.0, 6.0, 22.5, 5.0, 20.0, 0.0, 6.0, 1, True),
        ),
        (
            Box(80, 50, 14) - Pos(0, 0, 4) * _obround(30, 10, 10),
            2,
            2,
            ("y", "x", 10.0, 40.0, 8.0, 0.0, -20.0, 20.0, -1.0, 7.0, 1, False),
        ),
        (
            Box(60, 40, 12) - Pos(0, 0, 4) * _obround(3, 10, 8),
            0,
            2,
            ("y", "x", 10.0, 13.0, 6.0, 0.0, -6.5, 6.5, 0.0, 6.0, 1, False),
        ),
    ],
)
def test_route_selected_sources_are_complete_and_one_body(part, planar, curved, expected) -> None:
    graph, fresh = _fresh_occurrences(part)
    assert len(fresh) == 1
    fresh_record, expected_nodes = fresh[0]
    assert sum(graph.is_planar(node) for node in expected_nodes) == planar
    assert sum(not graph.is_planar(node) for node in expected_nodes) == curved
    ledger = ClaimLedger(graph)
    records = _discover_pockets(part, writer=ledger.writer)
    candidates = ledger.candidate_set(FamilyId.POCKETS).candidates
    assert len(records) == len(candidates) == 1
    assert candidates[0].record is records[0]
    record = records[0]
    assert record == fresh_record
    assert (
        record.width_axis,
        record.long_axis,
        record.width,
        record.length,
        record.depth,
        record.w_center,
        record.lo,
        record.hi,
        record.d_lo,
        record.d_hi,
        record.open_sign,
        record.edge_anchored,
    ) == expected
    nodes = ledger.defining_of(candidates[0])
    assert nodes == expected_nodes
    assert sum(ledger.graph.is_planar(node) for node in nodes) == planar
    assert sum(not ledger.graph.is_planar(node) for node in nodes) == curved
    assert ledger.graph.common_valid_solid(nodes) is not None


def test_equal_coincident_bodies_remain_distinct_occurrences() -> None:
    pocket = Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)
    part = Compound([pocket, deepcopy(pocket)])
    ledger = ClaimLedger(FaceGraph(part))
    records = _discover_pockets(part, writer=ledger.writer)
    candidates = ledger.candidate_set(FamilyId.POCKETS).candidates
    assert len(records) == len(candidates) == 2
    assert all(
        candidate.record is record for candidate, record in zip(candidates, records, strict=True)
    )


@pytest.mark.parametrize(
    "foreign", [lambda part: deepcopy(part), lambda part: Pos(100, 0, 0) * part]
)
def test_deep_and_translated_foreign_graph_refuse_without_prefix(foreign) -> None:
    part = Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)
    ledger = ClaimLedger(FaceGraph(foreign(part)))
    with pytest.raises(_PocketAttributionError, match="identity"):
        _discover_pockets(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.POCKETS).candidates == ()


def test_unexpected_geometry_value_error_is_not_relabelled(monkeypatch) -> None:
    import b123d_recognisers._recess_features as module

    part = Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)
    ledger = ClaimLedger(FaceGraph(part))

    def fail(*args, **kwargs):
        raise ValueError("geometry defect")

    monkeypatch.setattr(module, "_body_scoped_proposals", fail)
    with pytest.raises(ValueError, match="geometry defect"):
        _discover_pockets(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.POCKETS).candidates == ()


@pytest.mark.parametrize(
    "part",
    [
        Pos(17, -23, 11) * (Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)),
        Rot(90, 0, 0) * (Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)),
        Rot(0, 90, 0) * (Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)),
        (Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)).mirror(Plane.YZ),
        (Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)).scale(0.2),
        (Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)).scale(5),
    ],
)
def test_axis_transform_mirror_and_scale_keep_writer_parity(part) -> None:
    ledger = ClaimLedger(FaceGraph(part))
    written = _discover_pockets(part, writer=ledger.writer)
    plain = _discover_pockets(part)
    assert [item.to_dict() for item in written] == [item.to_dict() for item in plain]
    assert len(written) == len(ledger.candidate_set(FamilyId.POCKETS).candidates) == 1


@pytest.mark.parametrize(
    "part",
    [
        Box(60, 40, 12) - Box(20, 12, 12),  # through Slot: zero floors
        Box(60, 40, 12) - Cylinder(5, 12),  # full cylinder
        Box(60, 40, 12),
        Box(60, 40, 12) - Pos(0, 0, 4) * Box(60, 12, 8),  # full-span Channel
    ],
)
def test_non_pocket_routes_have_no_candidate_or_prefix(part) -> None:
    ledger = ClaimLedger(FaceGraph(part))
    assert _discover_pockets(part, writer=ledger.writer) == []
    assert ledger.candidate_set(FamilyId.POCKETS).candidates == ()


@pytest.mark.parametrize(
    ("part", "sign"),
    [
        (Box(60, 40, 12) - Pos(0, 0, -4) * Box(20, 12, 8), -1),
        (Box(40, 30, 20) - Pos(0, 0, 6) * Box(8, 6, 16), 1),
        *[
            (Box(60, 40, 12) - Pos(x, y, 4) * Box(20, 20, 8), 1)
            for x in (-25, 25)
            for y in (-15, 15)
        ],
    ],
)
def test_open_sign_deep_and_all_corner_routes_publish_complete_occurrences(part, sign) -> None:
    fresh_graph, expected = _fresh_occurrences(part)
    assert expected
    ledger = ClaimLedger(FaceGraph(part))
    records = _discover_pockets(part, writer=ledger.writer)
    candidates = ledger.candidate_set(FamilyId.POCKETS).candidates
    assert records == [record for record, _nodes in expected]
    assert all(record.open_sign == sign for record in records)
    for candidate, (_record, expected_nodes) in zip(candidates, expected, strict=True):
        actual = [ledger.graph.face(node) for node in ledger.defining_of(candidate)]
        want = [fresh_graph.face(node) for node in expected_nodes]
        assert all(any(face.is_same(expected_face) for face in actual) for expected_face in want)


def test_supplied_face_edges_and_generic_step_keep_exact_writer_projection(tmp_path: Path) -> None:
    part = Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)
    path = tmp_path / "pocket.step"
    assert export_step(part, path)
    imported = import_step(path)
    graph = FaceGraph(imported)
    ledger = ClaimLedger(graph)
    supplied = FaceEdges()
    records = _discover_pockets(imported, face_edges=supplied, writer=ledger.writer)
    assert [record.to_dict() for record in records] == [
        record.to_dict() for record in _discover_pockets(imported, face_edges=supplied)
    ]
    assert len(records) == len(ledger.candidate_set(FamilyId.POCKETS).candidates) == 1


@pytest.mark.parametrize(
    "part",
    [
        Box(60, 40, 12) - Pos(0, 0, 0) * Box(20, 12, 6),  # sealed/two-floor void
        Box(60, 40, 12) - Pos(0, 0, 4) * Cylinder(5, 8),
        Box(60, 40, 12) - Pos(0, 0, 4) * (Cylinder(5, 8) + Pos(3, 0, 0) * Box(6, 10, 8)),
        Box(60, 40, 12) - Pos(0, 0, 4) * (Rot(0, 0, 17) * Box(20, 12, 8)),
    ],
)
def test_sealed_rib_and_incomplete_cap_shapes_do_not_leak_evidence(part) -> None:
    ledger = ClaimLedger(FaceGraph(part))
    assert _discover_pockets(part, writer=ledger.writer) == []
    assert ledger.candidate_set(FamilyId.POCKETS).candidates == ()


def test_open_shell_geometry_cannot_publish_pocket_evidence() -> None:
    solid = Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)
    shell = Shell(solid.faces())
    ledger = ClaimLedger(FaceGraph(shell))
    with pytest.raises(_PocketAttributionError, match="one valid solid"):
        _discover_pockets(shell, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.POCKETS).candidates == ()


def test_pocket_shared_predicate_thresholds_and_aag_boundaries_are_exact() -> None:
    assert (_AXIS_ALIGNED_TOL, _MERGE_TOL, _FLOOR_TOL, _FLOOR_COVER_FRAC) == (
        1e-3,
        0.5,
        0.3,
        0.5,
    )
    axis_at = 1 - _AXIS_ALIGNED_TOL
    assert _dominant_axis((math.nextafter(axis_at, 1), 0, 0)) == "x"
    assert _dominant_axis((math.nextafter(axis_at, 0), 0, 0)) is None
    assert round(1.2349, 2) == 1.23
    assert round(1.2351, 2) == 1.24

    class FakeEdge:
        def __init__(self, kind) -> None:
            self.geom_type = kind

    class FakeFace:
        def __init__(self, kinds) -> None:
            self._edges = [FakeEdge(kind) for kind in kinds]

        def edges(self):
            return self._edges

    assert not _is_wall(FakeFace([]))
    assert _is_wall(FakeFace([GeomType.LINE, GeomType.CIRCLE]))
    assert not _is_wall(FakeFace([GeomType.CIRCLE, GeomType.CIRCLE]))
    assert not _is_wall(FakeFace([GeomType.LINE, GeomType.BSPLINE]))

    reference = Box(10, 10, 1).faces().sort_by().last
    bb = reference.bounding_box()
    centre = sum((bb.min.Z, bb.max.Z)) / 2
    foot = {"x": (-5, 5), "y": (-5, 5)}
    plus = _Face((0, 0, 1), "z", bb, True)
    minus = _Face((0, 0, -1), "z", bb, True)
    assert _end_capped([plus], foot, 100, "z", centre, 1)
    assert not _end_capped([minus], foot, 100, "z", centre, 1)
    assert _end_capped([minus], foot, 100, "z", centre, -1)
    assert _end_capped([plus], foot, 200, "z", centre, 1)
    assert not _end_capped([plus], foot, math.nextafter(200, math.inf), "z", centre, 1)
    assert _end_capped([plus], foot, 100, "z", math.nextafter(centre + _FLOOR_TOL, centre), 1)
    assert not _end_capped([plus], foot, 100, "z", math.nextafter(centre + _FLOOR_TOL, math.inf), 1)

    left, right, curved, a, b = object(), object(), object(), object(), object()
    face_box = Box(1, 1, 1).bounding_box()
    fa = _Face((1, 0, 0), "x", face_box, True, cast(FaceNode, left))
    fb = _Face((-1, 0, 0), "x", face_box, True, cast(FaceNode, right))

    class Graph:
        def __init__(self, common=(), arcs=None, regions=None, bounds=None):
            self.common = set(common)
            self.arcs = arcs or {}
            self.regions = regions or {}
            self.node_bounds = bounds or {}

        def neighbours(self, node):
            return self.common or ({a} if node is left else {b})

        def is_planar(self, _node):
            return False

        def arc(self, first, second):
            return self.arcs[first, second]

        def smooth_region(self, node):
            return self.regions.get(node, frozenset({node}))

        def bounds(self, node):
            return self.node_bounds[node]

    shared = frozenset({a, b})
    fragmented = Graph(
        arcs={(left, a): "concave", (right, b): "concave"}, regions={a: shared, b: shared}
    )
    assert _bounds_one_void(fa, fb, cast(FaceGraph, fragmented))
    trimming = Graph(
        common={curved},
        arcs={(left, curved): "convex", (right, curved): "concave"},
        bounds={curved: ((0, 0), (0, 0), (0, 2))},
    )
    assert _uninterrupted_long_span("z", (0, 10), fa, fb, cast(FaceGraph, trimming)) == (2, 10)
    collapsed = Graph(
        common={curved},
        arcs={(left, curved): "convex", (right, curved): "concave"},
        bounds={curved: ((0, 0), (0, 0), (0, 10))},
    )
    assert _uninterrupted_long_span("z", (0, 10), fa, fb, cast(FaceGraph, collapsed)) is None


@pytest.mark.parametrize("mutation", ["missing", "one", "axis", "radius", "depth"])
def test_blind_pocket_cap_contract_refuses_every_mismatched_endpoint(monkeypatch, mutation) -> None:
    import b123d_recognisers._recess_obround as module

    part = Box(80, 50, 14) - Pos(0, 0, 4) * _obround(30, 10, 10)
    graph = FaceGraph(part)
    extended = _pocket_proposals_one(part, graph=graph)[0]
    radius = extended.record.width / 2
    raw = _RecessProposal(
        replace(
            extended.record,
            lo=extended.record.lo + radius,
            hi=extended.record.hi - radius,
            length=extended.record.length - 2 * radius,
        ),
        extended.planar,
    )
    ends = _obround_ends(part, graph)
    if mutation == "missing":
        changed = []
    elif mutation == "one":
        changed = ends[:1]
    else:
        target = ends[0]
        index, value = {
            "axis": (2, "x" if target[2] != "x" else "y"),
            "radius": (3, target[3] * 1.1),
            "depth": (8, target[8] + 1.0),
        }[mutation]
        changed = [(*target[:index], value, *target[index + 1 :]), *ends[1:]]
    monkeypatch.setattr(module, "_obround_ends", lambda _part, _graph: changed)
    assert _extend_obround_proposals([raw], part, graph) == [raw]


def test_merge_tolerance_and_max_span_boundaries_drive_pocket_lifecycle(monkeypatch) -> None:
    import b123d_recognisers._recess_obround as module

    below = _MERGE_TOL - 1e-6
    above = _MERGE_TOL + 1e-6
    base = Box(60, 40, 12) - Pos(0, 0, 4) * _obround(3, 10, 8)
    graph = FaceGraph(base)
    ends = _obround_ends(base, graph)
    monkeypatch.setattr(module, "_has_side_walls", lambda _faces, _record: True)
    monkeypatch.setattr(module, "_floor_ends", lambda _faces, _record: 1)
    for run, accepted in ((below, False), (_MERGE_TOL, False), (above, True)):
        changed = [
            (*ends[0][:5], -run / 2, *ends[0][6:]),
            (*ends[1][:5], run / 2, *ends[1][6:]),
        ]
        monkeypatch.setattr(module, "_obround_ends", lambda _part, _graph, value=changed: value)
        records = _recognise_obround_from_ends(base, [], blind=True, graph=graph, proposals=True)
        assert bool(records) is accepted

    monkeypatch.undo()
    for length, accepted in ((53.99, True), (54.0, False)):
        part = Box(60, 40, 12) - Pos(0, 0, 4) * Box(length, 10, 8)
        ledger = ClaimLedger(FaceGraph(part))
        records = _discover_pockets(part, writer=ledger.writer)
        assert bool(records) is accepted
        assert bool(ledger.candidate_set(FamilyId.POCKETS).candidates) is accepted


def test_stubby_cap_direction_is_mandatory(monkeypatch) -> None:
    import b123d_recognisers._recess_obround as module

    part = Box(60, 40, 12) - Pos(0, 0, 4) * _obround(3, 10, 8)
    graph = FaceGraph(part)
    ends = _obround_ends(part, graph)
    changed = [(*ends[0][:6], -ends[0][6], *ends[0][7:]), *ends[1:]]
    monkeypatch.setattr(module, "_obround_ends", lambda _part, _graph: changed)
    assert _recognise_obround_from_ends(part, [], blind=True, graph=graph, proposals=True) == []


def test_private_writer_roster_and_prohibited_reads_are_closed_alias_aware() -> None:
    package = ROOT / "src/b123d_recognisers"
    calls = []
    importers = []
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        aliases = {"_discover_pockets"}
        modules = set()
        for statement in tree.body:
            if isinstance(statement, ast.ImportFrom) and statement.module:
                for alias in statement.names:
                    if alias.name == "_discover_pockets":
                        aliases.add(alias.asname or alias.name)
                        importers.append(path.name)
            elif isinstance(statement, ast.Import):
                for alias in statement.names:
                    if alias.name == "b123d_recognisers._recess_features":
                        modules.add(alias.asname or alias.name)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            direct = isinstance(node.func, ast.Name) and node.func.id in aliases
            qualified = (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "_discover_pockets"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in modules
            )
            if direct or qualified:
                calls.append((path.name, node))
    assert importers == ["_registry.py"]
    assert {path for path, _call in calls} == {"_registry.py", "_recess_features.py"}
    registry_call = next(call for path, call in calls if path == "_registry.py")
    keywords = {keyword.arg: keyword.value for keyword in registry_call.keywords}
    writer = keywords["writer"]
    assert isinstance(writer, ast.Attribute) and writer.attr == "writer"
    assert isinstance(writer.value, ast.Name) and writer.value.id == "s"
    assert tuple(inspect.signature(_discover_pockets).parameters) == (
        "part",
        "face_edges",
        "graph",
        "writer",
        "_wrap_errors",
    )


def test_pocket_constructor_reducer_and_read_boundaries_are_closed() -> None:
    package = ROOT / "src/b123d_recognisers"

    def bindings(tree):
        names = {}
        modules = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    names[alias.asname or alias.name] = alias.name
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    modules[alias.asname or alias.name.split(".")[0]] = alias.name
        return names, modules

    def leaf(node, names, modules):
        if isinstance(node, ast.Name):
            return names.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return node.attr
        return ""

    watched = {
        "_pocket_proposals_one",
        "_body_scoped_proposals",
        "_RecessProposal",
        "_merge_proposals",
        "_extend_obround_proposals",
    }
    sites = {name: [] for name in watched}
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names, modules = bindings(tree)

        class Visitor(ast.NodeVisitor):
            def __init__(self, source, imported_names, imported_modules):
                self.functions = []
                self.source = source
                self.names = imported_names
                self.modules = imported_modules

            def visit_FunctionDef(self, node):
                self.functions.append(node.name)
                self.generic_visit(node)
                self.functions.pop()

            def visit_Call(self, node):
                name = leaf(node.func, self.names, self.modules)
                if name in sites:
                    sites[name].append((self.source, self.functions[-1]))
                self.generic_visit(node)

        Visitor(path.name, names, modules).visit(tree)
    assert sites["_pocket_proposals_one"] == [("_recess_core.py", "_recognise_pockets_one")]
    assert ("_recess_features.py", "_discover_pockets") in sites["_body_scoped_proposals"]
    assert {path for path, _function in sites["_RecessProposal"]} == {
        "_recess_core.py",
        "_recess_obround.py",
        "_recess_reduce.py",
    }
    assert ("_recess_core.py", "_pocket_proposals_one") in sites["_merge_proposals"]
    assert ("_recess_core.py", "_pocket_proposals_one") in sites["_extend_obround_proposals"]
    prohibited = {
        "CandidateSet",
        "EvidenceIndex",
        "InventoryProduct",
        "ReconciliationResult",
        "CompletedInputs",
        "candidate_set",
        "accepted_set",
        "disposition",
    }
    for name in ("_recess_core.py", "_recess_faces.py", "_recess_obround.py", "_recess_reduce.py"):
        tree = ast.parse((package / name).read_text(encoding="utf-8"))
        names, _modules = bindings(tree)
        references = {
            names.get(node.id, node.id) for node in ast.walk(tree) if isinstance(node, ast.Name)
        } | {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        assert prohibited.isdisjoint(references), (name, prohibited & references)
    definition = next(item for item in PHYSICAL_DEFINITIONS if item.family is FamilyId.POCKETS)
    assert isinstance(definition.attribution, FullyAttributed)
    source = (package / "_recess_features.py").read_text(encoding="utf-8")
    for forbidden in (
        "CandidateSet",
        "EvidenceIndex",
        "InventoryProduct",
        "ReconciliationResult",
        "CompletedInputs",
    ):
        assert forbidden not in source


def test_step_split_obround_cap_publishes_every_original_patch(tmp_path: Path) -> None:
    """Select the physical cap from fresh topology before writer/Candidate inspection."""

    part = Box(80, 50, 14) - Pos(0, 0, 4) * _obround(30, 10, 10)
    graph = FaceGraph(part)
    curved = [node for node in graph.nodes if not graph.is_planar(node)]
    assert len(curved) == 2
    cap = max(curved, key=lambda node: graph.bounds(node)[0][1])
    face = graph.face(cap)
    bounds = face.bounding_box()
    seam = Edge.make_line((20, 0, bounds.min.Z), (20, 0, bounds.max.Z))
    splitter = BRepFeat_SplitShape(part.wrapped)
    splitter.Add(seam.wrapped, face.wrapped)
    splitter.Build()
    assert splitter.IsDone()
    split = type(part).cast(splitter.Shape())
    path = tmp_path / "pocket-split-cap.step"
    assert export_step(split, path)
    imported = import_step(path)
    fresh = FaceGraph(imported)
    expected_curved = frozenset(node for node in fresh.nodes if not fresh.is_planar(node))
    assert len(expected_curved) == 3
    ledger = ClaimLedger(fresh)
    (record,) = _discover_pockets(imported, writer=ledger.writer)
    (candidate,) = ledger.candidate_set(FamilyId.POCKETS).candidates
    defining = ledger.defining_of(candidate)
    assert candidate.record is record
    assert expected_curved.issubset(defining)
    assert sum(fresh.is_planar(node) for node in defining) == 2


def test_reversed_face_traversal_preserves_records_and_roles(monkeypatch) -> None:
    part = Box(60, 40, 12) - Pos(25, 15, 4) * Box(20, 20, 8)

    def run():
        ledger = ClaimLedger(FaceGraph(part))
        records = _discover_pockets(part, writer=ledger.writer)
        roles = [
            frozenset(ledger.graph.face(node) for node in ledger.defining_of(candidate))
            for candidate in ledger.candidate_set(FamilyId.POCKETS).candidates
        ]
        return records, roles

    before_records, before_roles = run()
    original = type(part).faces
    monkeypatch.setattr(type(part), "faces", lambda self: list(reversed(original(self))))
    after_records, after_roles = run()
    assert [record.to_dict() for record in after_records] == [
        record.to_dict() for record in before_records
    ]
    assert len(before_roles) == len(after_roles)
    for before, after in zip(before_roles, after_roles, strict=True):
        assert all(any(face.is_same(other) for other in after) for face in before)


def test_checked_1000_shared_walls_are_distinct_same_solid_occurrences() -> None:
    part = import_step(ROOT / "tests/corpus/mfcadpp/1000.step")
    ledger = ClaimLedger(FaceGraph(part))
    public = _discover_pockets(part)
    records = _discover_pockets(part, writer=ledger.writer)
    candidates = ledger.candidate_set(FamilyId.POCKETS).candidates
    assert len(records) == len(candidates) == 11
    assert [record.to_dict() for record in records] == [record.to_dict() for record in public]
    assert all(
        candidate.record is record for candidate, record in zip(candidates, records, strict=True)
    )
    roles = [ledger.defining_of(candidate) for candidate in candidates]
    overlaps = {
        (left, right): roles[left] & roles[right]
        for left in range(len(roles))
        for right in range(left + 1, len(roles))
        if roles[left] & roles[right]
    }
    assert set(overlaps) == {(0, 9), (2, 9), (3, 10), (5, 10)}
    assert all(len(nodes) == 1 for nodes in overlaps.values())
    owners = [ledger.graph.common_valid_solid(nodes) for nodes in roles]
    assert owners[0] is not None and all(owner == owners[0] for owner in owners)


def test_same_record_competing_bound_role_sets_refuse_without_prefix(monkeypatch) -> None:
    import b123d_recognisers._recess_features as module
    from b123d_recognisers._recess_reduce import _RecessProposal

    part = Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)
    graph = FaceGraph(part)
    record = _discover_pockets(part)[0]
    planar = [node for node in graph.nodes if graph.is_planar(node)]
    proposals = [
        _RecessProposal(record, frozenset(planar[:2])),
        _RecessProposal(record, frozenset(planar[2:4])),
    ]
    monkeypatch.setattr(module, "_body_scoped_proposals", lambda *_args, **_kwargs: proposals)
    ledger = ClaimLedger(graph)
    with pytest.raises(_PocketAttributionError, match="competing source assignments"):
        _discover_pockets(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.POCKETS).candidates == ()


def test_graph_identical_duplicate_returns_and_issues_one_exact_record(monkeypatch) -> None:
    import b123d_recognisers._recess_features as module
    from b123d_recognisers._recess_reduce import _RecessProposal

    part = Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)
    graph = FaceGraph(part)
    record = _discover_pockets(part)[0]
    nodes = frozenset(node for node in graph.nodes if graph.is_planar(node))
    proposal = _RecessProposal(record, nodes)
    monkeypatch.setattr(
        module, "_body_scoped_proposals", lambda *_args, **_kwargs: [proposal, proposal]
    )
    ledger = ClaimLedger(graph)
    returned = _discover_pockets(part, writer=ledger.writer)
    candidates = ledger.candidate_set(FamilyId.POCKETS).candidates
    assert returned == [record]
    assert len(candidates) == 1 and candidates[0].record is returned[0]
    assert ledger.defining_of(candidates[0]) == nodes


def test_aggregate_identical_duplicate_completes_one_occurrence_and_capability(monkeypatch) -> None:
    import b123d_recognisers._recess_features as module
    from b123d_recognisers._recess_reduce import _RecessProposal

    part = Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)
    context = start(part)
    record = _discover_pockets(part)[0]
    nodes = frozenset(node for node in context.graph.nodes if context.graph.is_planar(node))
    proposal = _RecessProposal(record, nodes)
    real = module._body_scoped_proposals

    def staged(sources, recognise_one):
        return (
            [proposal, proposal]
            if recognise_one.func is module._pocket_proposals_one
            else real(sources, recognise_one)
        )

    monkeypatch.setattr(module, "_body_scoped_proposals", staged)
    ledger = ClaimLedger(context.graph, definitions=PHYSICAL_DEFINITIONS)
    _discover_all(context, ledger)
    assert len(ledger.candidate_set(FamilyId.POCKETS).candidates) == 1
    assert FamilyId.POCKETS in ledger._issuer._completed
    assert len(ledger._issuer._completed_occurrences[FamilyId.POCKETS]) == 1


def test_aggregate_competing_same_record_has_no_completion_or_capability(monkeypatch) -> None:
    import b123d_recognisers._recess_features as module
    from b123d_recognisers._recess_reduce import _RecessProposal

    part = Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)
    context = start(part)
    record = _discover_pockets(part)[0]
    planar = [node for node in context.graph.nodes if context.graph.is_planar(node)]
    real = module._body_scoped_proposals

    def staged(sources, recognise_one):
        if recognise_one.func is not module._pocket_proposals_one:
            return real(sources, recognise_one)
        return [
            _RecessProposal(record, frozenset(planar[:2])),
            _RecessProposal(record, frozenset(planar[2:4])),
        ]

    monkeypatch.setattr(
        module,
        "_body_scoped_proposals",
        staged,
    )
    ledger = ClaimLedger(context.graph, definitions=PHYSICAL_DEFINITIONS)
    with pytest.raises(_PocketAttributionError, match="competing source assignments"):
        _discover_all(context, ledger)
    assert ledger.candidate_set(FamilyId.POCKETS).candidates == ()
    assert FamilyId.POCKETS not in ledger._issuer._completed
    assert FamilyId.POCKETS not in ledger._issuer._completed_occurrences


def test_public_ledger_raw_writer_and_plain_projection_are_identical() -> None:
    part = Box(80, 50, 14) - Pos(0, 0, 4) * _obround(30, 10, 10)
    plain = _discover_pockets(part)
    public_ledger = ClaimLedger(FaceGraph(part))
    public = _discover_pockets(part, writer=public_ledger.writer)
    raw_ledger = ClaimLedger(FaceGraph(part))
    raw = _discover_pockets(part, writer=raw_ledger.writer)
    assert [record.to_dict() for record in public] == [record.to_dict() for record in plain]
    assert [record.to_dict() for record in raw] == [record.to_dict() for record in plain]
    assert len(public_ledger.claims) == len(raw_ledger.claims) == len(plain)


def test_same_body_multiple_pockets_keep_geometry_order_and_exact_identity() -> None:
    part = Box(100, 60, 16) - Pos(-25, 0, 5) * Box(18, 10, 8) - Pos(25, 0, 5) * Box(24, 12, 8)
    fresh_graph, expected = _fresh_occurrences(part)
    assert len(expected) == 2
    ledger = ClaimLedger(FaceGraph(part))
    records = _discover_pockets(part, writer=ledger.writer)
    candidates = ledger.candidate_set(FamilyId.POCKETS).candidates
    assert len(records) == len(candidates) == 2
    assert [record.width for record in records] == sorted(record.width for record in records)
    assert records == [record for record, _nodes in expected]
    assert all(
        candidate.record is record for candidate, record in zip(candidates, records, strict=True)
    )
    for candidate, (_record, nodes) in zip(candidates, expected, strict=True):
        actual_faces = [ledger.graph.face(node) for node in ledger.defining_of(candidate)]
        expected_faces = [fresh_graph.face(node) for node in nodes]
        assert all(any(face.is_same(want) for face in actual_faces) for want in expected_faces)


def test_late_second_body_failure_has_no_pocket_prefix(monkeypatch) -> None:
    first = Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)
    part = Compound([first, Pos(100, 0, 0) * deepcopy(first)])
    context = start(part)
    ledger = ClaimLedger(context.graph, definitions=PHYSICAL_DEFINITIONS)
    real = ledger.graph.common_valid_solid
    owners = []

    def fail_second(nodes):
        owner = real(nodes)
        if owner is not None and owner not in owners:
            owners.append(owner)
        return None if len(owners) > 1 else owner

    monkeypatch.setattr(ledger.graph, "common_valid_solid", fail_second)
    with pytest.raises(_PocketAttributionError, match="one valid solid"):
        _discover_all(context, ledger)
    assert ledger.candidate_set(FamilyId.POCKETS).candidates == ()
    assert FamilyId.POCKETS not in ledger._issuer._completed
    assert FamilyId.POCKETS not in ledger._issuer._completed_occurrences


def test_shared_node_across_distinct_solidrefs_refuses_atomically(monkeypatch) -> None:
    import b123d_recognisers._recess_features as module
    from b123d_recognisers._recess_reduce import _RecessProposal

    first = Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)
    part = Compound([first, Pos(100, 0, 0) * deepcopy(first)])
    context = start(part)
    ledger = ClaimLedger(context.graph, definitions=PHYSICAL_DEFINITIONS)
    proposals = module._body_scoped_proposals(
        list(part.solids()),
        lambda solid: module._pocket_proposals_one(solid, graph=context.graph),
    )
    assert len(proposals) == 2
    shared = next(iter(proposals[0].planar))
    mixed = _RecessProposal(
        proposals[1].record,
        proposals[1].planar | {shared},
        proposals[1].caps,
    )
    real = module._body_scoped_proposals
    monkeypatch.setattr(
        module,
        "_body_scoped_proposals",
        lambda sources, recognise_one: (
            [proposals[0], mixed]
            if recognise_one.func is module._pocket_proposals_one
            else real(sources, recognise_one)
        ),
    )
    with pytest.raises(_PocketAttributionError, match="one valid solid"):
        _discover_all(context, ledger)
    assert ledger.candidate_set(FamilyId.POCKETS).candidates == ()
    assert FamilyId.POCKETS not in ledger._issuer._completed


def test_empty_roles_and_cap_ambiguity_are_atomic_without_completion(monkeypatch) -> None:
    import b123d_recognisers._recess_features as module
    from b123d_recognisers._recess_reduce import _RecessProposal

    part = Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)
    plain = _discover_pockets(part)[0]
    real = module._body_scoped_proposals
    for failure, message in (
        (lambda *_args, **_kwargs: [_RecessProposal(plain, frozenset(), ())], "no defining"),
        (
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                ValueError("obround cap clusters compete at one endpoint")
            ),
            "cap ownership is ambiguous",
        ),
    ):
        context = start(part)
        ledger = ClaimLedger(context.graph, definitions=PHYSICAL_DEFINITIONS)
        monkeypatch.setattr(
            module,
            "_body_scoped_proposals",
            lambda sources, recognise_one, fail=failure: (
                fail(sources, recognise_one)
                if recognise_one.func is module._pocket_proposals_one
                else real(sources, recognise_one)
            ),
        )
        with pytest.raises(_PocketAttributionError, match=message):
            _discover_all(context, ledger)
        assert ledger.candidate_set(FamilyId.POCKETS).candidates == ()
        assert FamilyId.POCKETS not in ledger._issuer._completed
        assert FamilyId.POCKETS not in ledger._issuer._completed_occurrences
