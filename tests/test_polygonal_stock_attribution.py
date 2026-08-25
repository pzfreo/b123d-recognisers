"""F5: Polygonal Stock owns its complete original eight-face boundary."""

from __future__ import annotations

import ast
import inspect
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
from b123d_recognisers._adjacency import FaceGraph, FaceNode
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._registry import PHYSICAL_DEFINITIONS, FullyAttributed, NotCounted
from b123d_recognisers.polygonal_bosses import PolygonalStock, _discover_polygonal_stock
from b123d_recognisers.result import _take_inventory
from tests.golden._common import hex_prism
from tests.golden.polygonal_stock.fixture import build_fixture

ROOT = Path(__file__).parents[1]


def _fresh_oracle(part, graph: FaceGraph):
    """Reconstruct the complete stock record and ownership before Candidate reads.

    This deliberately does not call any production polygon/ring/cap helper.  It starts from a
    fresh graph inventory, proves the side cycle and cap roles, solves the three opposed
    midplanes, and independently projects every serialized field.
    """

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
    assert all(
        len(set(graph.neighbours(side)) & set(ordered)) == 2 for side in ordered
    )
    lower, upper = sorted(caps, key=lambda node: sum(graph.bounds(node)[2]) / 2)
    assert graph.normal(lower)[2] <= -0.999
    assert graph.normal(upper)[2] >= 0.999
    assert all(
        lower in graph.neighbours(side) and upper in graph.neighbours(side) for side in ordered
    )

    opposite = 3
    centres = [graph.face(node).center() for node in ordered]
    offsets = [
        graph.normal(node)[0] * float(point.X) + graph.normal(node)[1] * float(point.Y)
        for node, point in zip(ordered, centres, strict=True)
    ]
    midplanes = [
        (
            graph.normal(ordered[i])[0],
            graph.normal(ordered[i])[1],
            (offsets[i] - offsets[i + opposite]) / 2,
        )
        for i in range(opposite)
    ]
    sxx = sum(nx * nx for nx, _ny, _offset in midplanes)
    sxy = sum(nx * ny for nx, ny, _offset in midplanes)
    syy = sum(ny * ny for _nx, ny, _offset in midplanes)
    bx = sum(nx * offset for nx, _ny, offset in midplanes)
    by = sum(ny * offset for _nx, ny, offset in midplanes)
    determinant = sxx * syy - sxy * sxy
    cx = (bx * syy - by * sxy) / determinant
    cy = (sxx * by - sxy * bx) / determinant
    supports = [
        offset - graph.normal(node)[0] * cx - graph.normal(node)[1] * cy
        for node, offset in zip(ordered, offsets, strict=True)
    ]
    opposed_widths = [supports[i] + supports[i + opposite] for i in range(opposite)]
    across = sum(opposed_widths) / opposite
    assert min(supports) > module._TOL
    assert all(value == pytest.approx(across, abs=module._TOL) for value in opposed_widths)
    assert all(value == pytest.approx(across / 2, abs=module._TOL) for value in supports)
    base = sum(graph.bounds(lower)[2]) / 2
    top = sum(graph.bounds(upper)[2]) / 2
    record = PolygonalStock(
        axis="z",
        center=(round(cx, 4), round(cy, 4), round((base + top) / 2, 4)),
        side_count=6,
        across_flats=round(across, 4),
        base=round(base, 4),
        top=round(top, 4),
        flat_directions=tuple(
            (round(graph.normal(node)[0], 3), round(graph.normal(node)[1], 3), 0.0)
            for node in ordered
        ),
        flat_centres=tuple(
            (round(float(point.X), 3), round(float(point.Y), 3), round(float(point.Z), 3))
            for point in centres
        ),
    )
    expected = frozenset((*ordered, lower, upper))
    solid = graph.common_valid_solid(expected)
    assert expected == frozenset(graph.nodes) and solid is not None
    return record, expected, solid


def _claim(part, **kwargs):
    ledger = ClaimLedger(FaceGraph(part))
    expected_record, expected, solid = _fresh_oracle(part, ledger.graph)
    public = recognise_polygonal_stock(part, **kwargs)
    records = _discover_polygonal_stock(part, graph=ledger.graph, writer=ledger.writer, **kwargs)
    assert public == [expected_record]
    assert records == [expected_record]
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


@pytest.mark.parametrize(
    "part",
    [
        Pos(0, 0, -41) * hex_prism(height=120),
        Pos(13, -17, 23) * hex_prism(height=0.21),
        (Pos(7, 9, 31) * hex_prism(height=11)).mirror(Plane.XY),
    ],
)
def test_deep_shallow_translated_and_reversed_cap_roles_reconstruct_exactly(part) -> None:
    _claim(part)


def test_height_at_or_below_tol_is_not_stock_but_just_above_is() -> None:
    assert recognise_polygonal_stock(hex_prism(height=module._TOL)) == []
    assert recognise_polygonal_stock(hex_prism(height=module._TOL - 1e-8)) == []
    _claim(hex_prism(height=module._TOL + 1e-8))


class _ThresholdGraph:
    def __init__(self, *, normal_z: float, z_bounds: tuple[float, float]) -> None:
        self.nodes = (FaceNode(0),)
        self._normal_z = normal_z
        self._z_bounds = z_bounds

    def is_planar(self, _node):
        return True

    def normal(self, _node):
        return (1.0, 0.0, self._normal_z)

    def bounds(self, _node):
        return ((0.0, 1.0), (0.0, 1.0), self._z_bounds)


def test_cap_and_side_threshold_equalities_are_frozen() -> None:
    assert module._TOL == 0.2
    assert module._SIDE_VERTICAL_COS == 0.02
    node = FaceNode(0)
    cap = _ThresholdGraph(
        normal_z=module.AXIS_ALIGNED_COS,
        z_bounds=(4.0 - module._TOL / 2, 4.0 + module._TOL / 2),
    )
    assert module._cap_z(
        cap, node, module._TOL, positive=True, lower_than=4.0, higher_than=4.0
    ) == pytest.approx(4.0)
    assert module._cap_z(
        _ThresholdGraph(
            normal_z=module.AXIS_ALIGNED_COS - 1e-8,
            z_bounds=(4.0, 4.0 + module._TOL),
        ),
        node,
        module._TOL,
        positive=True,
        lower_than=None,
        higher_than=None,
    ) is None
    assert module._cap_z(
        _ThresholdGraph(
            normal_z=module.AXIS_ALIGNED_COS,
            z_bounds=(4.0, 4.0 + module._TOL + 1e-8),
        ),
        node,
        module._TOL,
        positive=True,
        lower_than=None,
        higher_than=None,
    ) is None

    at_vertical_limit = _ThresholdGraph(
        normal_z=module._SIDE_VERTICAL_COS, z_bounds=(0.0, module._TOL + 1e-8)
    )
    selected = module._vertical_side_faces(at_vertical_limit, module._TOL)
    assert len(selected) == 1 and selected[0] is at_vertical_limit.nodes[0]
    too_slanted = _ThresholdGraph(
        normal_z=module._SIDE_VERTICAL_COS + 1e-8, z_bounds=(0.0, module._TOL + 1e-8)
    )
    assert module._vertical_side_faces(too_slanted, module._TOL) == []
    exactly_shallow = _ThresholdGraph(
        normal_z=module._SIDE_VERTICAL_COS, z_bounds=(0.0, module._TOL)
    )
    assert module._vertical_side_faces(exactly_shallow, module._TOL) == []


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


def test_foreign_translated_graph_and_late_cap_binding_fail_without_prefix(monkeypatch) -> None:
    part = build_fixture()
    foreign = ClaimLedger(FaceGraph(Pos(100, 0, 0) * part))
    with pytest.raises(ValueError, match="different part|does not exactly match|does not belong"):
        _discover_polygonal_stock(part, graph=foreign.graph, writer=foreign.writer)
    assert foreign.candidate_set(FamilyId.POLYGONAL_STOCK).candidates == ()

    ledger = ClaimLedger(FaceGraph(part))
    original = ledger.graph.require_node
    calls = 0

    def fail_on_last_cap(face):
        nonlocal calls
        calls += 1
        if calls == 8:
            raise ValueError("late cap identity failure")
        return original(face)

    monkeypatch.setattr(ledger.graph, "require_node", fail_on_last_cap)
    with pytest.raises(ValueError, match="late cap identity"):
        _discover_polygonal_stock(part, graph=ledger.graph, writer=ledger.writer)
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
        direct_aliases = (
            {"_discover_polygonal_stock"} if path.name == "polygonal_bosses.py" else set()
        )
        module_aliases = set()
        for statement in tree.body:
            if isinstance(statement, ast.ImportFrom) and statement.module == (
                "b123d_recognisers.polygonal_bosses"
            ):
                direct_aliases.update(
                    alias.asname or alias.name
                    for alias in statement.names
                    if alias.name == "_discover_polygonal_stock"
                )
            elif isinstance(statement, ast.Import):
                module_aliases.update(
                    alias.asname or alias.name
                    for alias in statement.names
                    if alias.name == "b123d_recognisers.polygonal_bosses"
                )
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            else:
                name = ""
            calls_core = (
                isinstance(node.func, ast.Name) and node.func.id in direct_aliases
            ) or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "_discover_polygonal_stock"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in module_aliases
            )
            if calls_core:
                core_sites.append((path.name, node))
            if name == "PolygonalStock":
                constructors.append((path.name, node))
    assert {path for path, _call in core_sites} == {"polygonal_bosses.py", "_registry.py"}
    registry_call = next(call for path, call in core_sites if path == "_registry.py")
    keywords = {keyword.arg: keyword.value for keyword in registry_call.keywords}
    assert isinstance(keywords["writer"], ast.Attribute) and keywords["writer"].attr == "writer"
    assert isinstance(keywords["writer"].value, ast.Name)
    assert keywords["writer"].value.id == "s"
    assert isinstance(keywords["graph"], ast.Attribute) and keywords["graph"].attr == "graph"
    assert isinstance(keywords["graph"].value, ast.Attribute)
    assert keywords["graph"].value.attr == "context"
    assert isinstance(keywords["graph"].value.value, ast.Name)
    assert keywords["graph"].value.value.id == "s"
    public_call = next(call for path, call in core_sites if path == "polygonal_bosses.py")
    assert all(keyword.arg != "writer" for keyword in public_call.keywords)
    public_keywords = {keyword.arg: keyword.value for keyword in public_call.keywords}
    assert isinstance(public_keywords["graph"], ast.Name)
    assert public_keywords["graph"].id == "graph"
    signature = inspect.signature(recognise_polygonal_stock)
    assert tuple(signature.parameters) == ("part", "tol", "angle_tol", "graph")
    assert signature.parameters["part"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert all(
        signature.parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
        for name in ("tol", "angle_tol", "graph")
    )
    assert signature.parameters["tol"].default is None
    assert signature.parameters["angle_tol"].default == math.radians(2)
    assert signature.parameters["graph"].default is None
    assert signature.return_annotation == "list[PolygonalStock]"
    assert constructors == []  # construction remains through the closed local record_type path

    core_path = package / "polygonal_bosses.py"
    source = core_path.read_text(encoding="utf-8")
    assert "graph.face(base.node)" in source and "graph.face(top.node)" in source
    tree = ast.parse(source)
    prohibited = {
        "CandidateSet",
        "EvidenceIndex",
        "InventoryProduct",
        "IncompleteAttribution",
        "FullyAttributed",
        "reconcile",
    }
    assert not ({node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} & prohibited)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }
    assert not (imported & prohibited)

    raw_readers = []

    class RawReaderVisitor(ast.NodeVisitor):
        def __init__(self):
            self.functions = []

        def visit_FunctionDef(self, node):
            self.functions.append(node.name)
            self.generic_visit(node)
            self.functions.pop()

        def visit_Call(self, node):
            if isinstance(node.func, ast.Attribute) and node.func.attr in {"faces", "solids"}:
                raw_readers.append((self.functions[-1], node.func.attr))
            self.generic_visit(node)

    RawReaderVisitor().visit(tree)
    assert raw_readers == [
        ("_recognise_one", "faces"),
        ("_discover_polygonal_bosses", "solids"),
        ("_discover_polygonal_stock", "solids"),
        ("_discover_polygonal_stock", "faces"),
    ]
