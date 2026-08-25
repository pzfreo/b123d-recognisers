"""F5: Polygonal Stock owns its complete original eight-face boundary."""

from __future__ import annotations

import ast
import math
from dataclasses import replace
from pathlib import Path

import pytest
from build123d import (
    Box,
    Compound,
    Plane,
    Pos,
    RegularPolygon,
    Rot,
    Shell,
    export_step,
    extrude,
    import_step,
)

import b123d_recognisers.polygonal_bosses as module
from b123d_recognisers import recognise_polygonal_stock
from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._registry import PHYSICAL_DEFINITIONS, FullyAttributed, NotCounted
from b123d_recognisers.polygonal_bosses import _discover_polygonal_stock
from b123d_recognisers.result import _take_inventory
from tests.golden.polygonal_stock.fixture import build_fixture

ROOT = Path(__file__).parents[1]


def _fresh_boundary(part, graph: FaceGraph):
    assert len(list(part.solids())) == 1 and len(graph.nodes) == 8
    sides = []
    caps = []
    for node in graph.nodes:
        assert graph.is_planar(node)
        normal = graph.normal(node)
        assert normal is not None
        if abs(normal[2]) <= 0.02:
            sides.append(node)
        elif abs(normal[2]) >= 0.999:
            caps.append(node)
    assert len(sides) == 6 and len(caps) == 2
    ordered = tuple(
        sorted(
            sides,
            key=lambda node: math.atan2(graph.normal(node)[1], graph.normal(node)[0]),
        )
    )
    angles = [
        math.atan2(graph.normal(node)[1], graph.normal(node)[0]) % (2 * math.pi) for node in ordered
    ]
    gaps = [(angles[(i + 1) % 6] - angles[i]) % (2 * math.pi) for i in range(6)]
    assert all(gap == pytest.approx(math.pi / 3, abs=math.radians(2)) for gap in gaps)
    lower, upper = sorted(caps, key=lambda node: sum(graph.bounds(node)[2]) / 2)
    expected = frozenset((*ordered, lower, upper))
    solid = graph.common_valid_solid(expected)
    assert expected == frozenset(graph.nodes) and solid is not None
    return expected, solid


def _claim(part, **kwargs):
    ledger = ClaimLedger(FaceGraph(part))
    expected, solid = _fresh_boundary(part, ledger.graph)
    public = recognise_polygonal_stock(part, **kwargs)
    records = _discover_polygonal_stock(part, graph=ledger.graph, writer=ledger.writer, **kwargs)
    assert [record.to_dict() for record in records] == [record.to_dict() for record in public]
    candidates = ledger.candidate_set(FamilyId.POLYGONAL_STOCK).candidates
    assert len(records) == len(candidates) == 1
    assert candidates[0].record is records[0]
    assert ledger.defining_of(candidates[0]) == expected
    assert ledger.graph.common_valid_solid(expected) == solid
    return records, candidates, ledger


def test_canonical_stock_owns_complete_graph_inventory() -> None:
    records, candidates, ledger = _claim(build_fixture())
    assert len(ledger.defining_of(candidates[0])) == 8
    assert records[0].side_count == 6 and records[0].axis == "z"


@pytest.mark.parametrize(
    "part",
    [
        Pos(17, -11, 9) * build_fixture(),
        Rot(0, 0, 43) * build_fixture(),
        build_fixture().mirror(Plane.YZ),
        build_fixture().mirror(Plane.XZ),
        build_fixture().scale(0.2),
        build_fixture().scale(5),
    ],
)
def test_supported_transforms_keep_complete_boundary(part) -> None:
    _claim(part, tol=0.04 if part.bounding_box().size.Z < 10 else None)


def test_step_and_reversed_traversal_keep_identity(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "stock.step"
    assert export_step(build_fixture(), path)
    _claim(import_step(path))

    part = build_fixture()
    kind = type(part)
    original = kind.faces
    monkeypatch.setattr(kind, "faces", lambda self: type(original(self))(reversed(original(self))))
    _claim(part)


@pytest.mark.parametrize(
    "part",
    [
        Box(20, 20, 20),
        extrude(RegularPolygon(20, 5), 30),
        extrude(RegularPolygon(20, 8), 30),
        Rot(0, 90, 0) * build_fixture(),
        Compound([build_fixture(), Pos(100, 0, 0) * build_fixture()]),
        Shell(build_fixture().faces()),
    ],
)
def test_excluded_shapes_issue_no_stock_candidate(part) -> None:
    ledger = ClaimLedger(FaceGraph(part))
    assert recognise_polygonal_stock(part) == []
    assert _discover_polygonal_stock(part, writer=ledger.writer) == []
    assert ledger.candidate_set(FamilyId.POLYGONAL_STOCK).candidates == ()


def test_wrong_graph_writer_inventory_and_body_fail_before_issue(monkeypatch) -> None:
    part = build_fixture()
    local = FaceGraph(part)
    foreign = ClaimLedger(FaceGraph(Pos(100, 0, 0) * part))
    with pytest.raises(ValueError, match="one authority"):
        _discover_polygonal_stock(part, graph=local, writer=foreign.writer)
    assert foreign.candidate_set(FamilyId.POLYGONAL_STOCK).candidates == ()

    ledger = ClaimLedger(local)
    original = module._recognise_one

    def incomplete(*args, **kwargs):
        proposals = original(*args, **kwargs)
        return [replace(proposals[0], lower_cap=proposals[0].side_faces[0])]

    monkeypatch.setattr(module, "_recognise_one", incomplete)
    with pytest.raises(ValueError, match="complete eight-face"):
        _discover_polygonal_stock(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.POLYGONAL_STOCK).candidates == ()

    monkeypatch.setattr(module, "_recognise_one", original)
    monkeypatch.setattr(ledger.graph, "common_valid_solid", lambda _nodes: None)
    with pytest.raises(ValueError, match="one valid solid"):
        _discover_polygonal_stock(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.POLYGONAL_STOCK).candidates == ()


def test_terminal_status_identity_and_not_counted_census_are_truthful() -> None:
    product = _take_inventory(build_fixture())
    candidates = product.physical.candidate_set(FamilyId.POLYGONAL_STOCK).candidates
    assert len(candidates) == len(product.result.polygonal_stock) == 1
    assert candidates[0].record is product.result.polygonal_stock[0]
    assert len(product.evidence.defining_of(candidates[0])) == 8
    definition = next(
        item for item in PHYSICAL_DEFINITIONS if item.family is FamilyId.POLYGONAL_STOCK
    )
    assert isinstance(definition.attribution, FullyAttributed)
    assert isinstance(definition.census, NotCounted)


def test_private_core_constructor_and_cap_identity_paths_are_closed() -> None:
    package = ROOT / "src/b123d_recognisers"
    core_sites = []
    constructors = []
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            else:
                name = ""
            if name == "_discover_polygonal_stock":
                core_sites.append((path.name, node))
            if name == "PolygonalStock":
                constructors.append((path.name, node))
    assert {path for path, _call in core_sites} == {"polygonal_bosses.py", "_registry.py"}
    registry_call = next(call for path, call in core_sites if path == "_registry.py")
    keywords = {keyword.arg: keyword.value for keyword in registry_call.keywords}
    assert isinstance(keywords["writer"], ast.Attribute) and keywords["writer"].attr == "writer"
    assert isinstance(keywords["graph"], ast.Attribute) and keywords["graph"].attr == "graph"
    public_call = next(call for path, call in core_sites if path == "polygonal_bosses.py")
    assert all(keyword.arg != "writer" for keyword in public_call.keywords)
    assert constructors == []  # construction remains through the closed local record_type path

    source = (package / "polygonal_bosses.py").read_text(encoding="utf-8")
    assert "graph.face(base.node)" in source and "graph.face(top.node)" in source
    assert "leftover" not in source and "EvidenceIndex" not in source
