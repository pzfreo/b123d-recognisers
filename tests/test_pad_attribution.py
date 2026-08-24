"""F5: each RaisedPad owns its accepted top and four perimeter-wall roles."""

from __future__ import annotations

import ast
import copy
import math
from dataclasses import dataclass
from pathlib import Path

import pytest
from build123d import Box, Compound, Cylinder, Plane, Pos, Rot, Shell, export_step, import_step
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.GeomAbs import GeomAbs_Plane
from OCP.GProp import GProp_GProps

from b123d_recognisers import recognise_rectangular_pads
from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers.pads import RaisedPad, _discover_rectangular_pads
from b123d_recognisers.result import _take_inventory

ROOT = Path(__file__).parents[1]


def _qualified_calls(tree: ast.AST) -> list[tuple[str, ast.Call]]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    def qualified(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return f"{qualified(node.value)}.{node.attr}"
        return ""

    return [(qualified(node.func), node) for node in ast.walk(tree) if isinstance(node, ast.Call)]


def _pad():
    return Box(80, 60, 10) + Pos(0, 0, 7) * Box(30, 20, 4)


def _perforated_pad(radius: float):
    island = Box(30, 20, 4) - Pos(0, 0, -2) * Cylinder(radius, 8)
    return Box(80, 60, 10) + Pos(0, 0, 7) * island


@dataclass(frozen=True)
class _ExpectedPad:
    record: RaisedPad
    faces: tuple[object, ...]


def _fresh_expected(part, *, tol: float | None = None) -> list[_ExpectedPad]:
    """Rebuild pad occurrences from fresh topology before Candidate inspection."""

    threshold = 0.2 if tol is None else tol
    solids = list(part.solids())
    sources = solids if len(solids) > 1 else [part]
    occurrences: list[_ExpectedPad] = []
    for solid in sources:
        bb = solid.bounding_box()
        tops = []
        vertical = []
        for face in solid.faces():
            surface = BRepAdaptor_Surface(face.wrapped)
            if surface.GetType() != GeomAbs_Plane:
                continue
            try:
                normal = face.normal_at()
            except Exception:  # noqa: BLE001 - independently skip degenerate topology
                continue
            bounds = face.bounding_box()
            if normal.Z >= 0.99:
                dx = bounds.max.X - bounds.min.X
                dy = bounds.max.Y - bounds.min.Y
                properties = GProp_GProps()
                BRepGProp.SurfaceProperties_s(face.wrapped, properties)
                full_x = (
                    bb.min.X + threshold >= bounds.min.X
                    and bb.max.X - threshold <= bounds.max.X
                )
                full_y = (
                    bb.min.Y + threshold >= bounds.min.Y
                    and bb.max.Y - threshold <= bounds.max.Y
                )
                if (
                    dx > threshold
                    and dy > threshold
                    and bb.min.Z + threshold < bounds.max.Z
                    and abs(properties.Mass() - dx * dy)
                    <= max(threshold * threshold, 0.005 * dx * dy)
                    and not full_x
                    and not full_y
                ):
                    tops.append(
                        (
                            round(bounds.min.X, 3),
                            round(bounds.max.X, 3),
                            round(bounds.min.Y, 3),
                            round(bounds.max.Y, 3),
                            round(bounds.max.Z, 3),
                            face,
                        )
                    )
            if abs(normal.Z) <= 0.01:
                vertical.append((face, bounds, normal))

        raw_regions = [RaisedPad(x0, x1, y0, y1, z1, z1) for x0, x1, y0, y1, z1, _ in tops]
        proposals = []
        for x0, x1, y0, y1, z1, top in tops:
            role_specs = (
                ("x", x0, y0, y1),
                ("x", x1, y0, y1),
                ("y", y0, x0, x1),
                ("y", y1, x0, x1),
            )
            selected = []
            for axis, position, lo, hi in role_specs:
                matches = []
                for face, bounds, normal in vertical:
                    component = abs(normal.X) if axis == "x" else abs(normal.Y)
                    plane_position = (
                        (bounds.min.X + bounds.max.X) / 2
                        if axis == "x"
                        else (bounds.min.Y + bounds.max.Y) / 2
                    )
                    cross_lo = bounds.min.Y if axis == "x" else bounds.min.X
                    cross_hi = bounds.max.Y if axis == "x" else bounds.max.X
                    if (
                        component >= 0.99
                        and abs(plane_position - position) <= threshold
                        and abs(bounds.max.Z - z1) <= threshold
                        and z1 - threshold > bounds.min.Z
                        and cross_lo <= lo + threshold
                        and cross_hi >= hi - threshold
                    ):
                        matches.append((float(bounds.min.Z), face))
                if not matches:
                    selected = []
                    break
                base = max(item[0] for item in matches)
                maxima = [face for candidate_base, face in matches if candidate_base == base]
                unique = []
                for face in maxima:
                    if not any(face.wrapped.IsSame(other.wrapped) for other in unique):
                        unique.append(face)
                if len(unique) != 1:
                    selected = []
                    break
                selected.append((base, unique[0]))
            if len(selected) != 4:
                continue
            record = RaisedPad(x0, x1, y0, y1, round(max(base for base, _ in selected), 3), z1)
            touches_tier = any(
                abs(other.z1 - record.z0) <= threshold
                and min(record.x1, other.x1) - max(record.x0, other.x0) >= -threshold
                and min(record.y1, other.y1) - max(record.y0, other.y0) >= -threshold
                for other in raw_regions
            )
            if not touches_tier:
                proposals.append(_ExpectedPad(record, (top, *(face for _, face in selected))))

        grouped: dict[RaisedPad, list[_ExpectedPad]] = {}
        for proposal in proposals:
            grouped.setdefault(proposal.record, []).append(proposal)
        for record, group in grouped.items():
            reference = group[0].faces
            assert all(
                len(proposal.faces) == len(reference)
                and all(
                    actual.wrapped.IsSame(expected.wrapped)
                    for actual, expected in zip(proposal.faces, reference, strict=True)
                )
                for proposal in group
            )
            occurrences.append(_ExpectedPad(record, group[0].faces))
    occurrences.sort(key=lambda occurrence: occurrence.record)
    return occurrences


def _claim(part, **kwargs):
    expected = _fresh_expected(part, **kwargs)
    ledger = ClaimLedger(FaceGraph(part))
    public = recognise_rectangular_pads(part, **kwargs)
    assert [record.to_dict() for record in public] == [
        occurrence.record.to_dict() for occurrence in expected
    ]
    records = _discover_rectangular_pads(part, writer=ledger.writer, **kwargs)
    assert [record.to_dict() for record in records] == [record.to_dict() for record in public]
    candidates = ledger.candidate_set(FamilyId.PADS).candidates
    assert len(candidates) == len(records)
    assert all(
        candidate.record is record for candidate, record in zip(candidates, records, strict=True)
    )
    for occurrence, candidate in zip(expected, candidates, strict=True):
        expected_nodes = frozenset(ledger.graph.require_node(face) for face in occurrence.faces)
        assert ledger.defining_of(candidate) == expected_nodes
    return records, candidates, ledger


def _assert_role(record, candidate, ledger) -> None:
    defining = ledger.defining_of(candidate)
    assert len(defining) == 5
    assert ledger.graph.common_valid_solid(defining) is not None
    top = [
        node
        for node in defining
        if ledger.graph.is_planar(node) and ledger.graph.normal(node)[2] > 0.999
    ]
    walls = [node for node in defining if node not in top]
    assert len(top) == 1 and len(walls) == 4
    top_bounds = ledger.graph.bounds(top[0])
    assert top_bounds[0] == pytest.approx((record.x0, record.x1), abs=0.001)
    assert top_bounds[1] == pytest.approx((record.y0, record.y1), abs=0.001)
    assert top_bounds[2][1] == pytest.approx(record.z1, abs=0.001)
    assert max(ledger.graph.bounds(node)[2][0] for node in walls) == pytest.approx(
        record.z0, abs=0.001
    )
    assert all(
        ledger.graph.is_planar(node)
        and abs(ledger.graph.normal(node)[2]) < 1e-4
        for node in walls
    )


def test_simple_pad_has_exact_top_and_four_wall_roles() -> None:
    (record,), (candidate,), ledger = _claim(_pad())
    _assert_role(record, candidate, ledger)


def test_equal_records_on_coincident_valid_solids_remain_distinct() -> None:
    original = _pad()
    part = Compound([original, copy.deepcopy(original)])
    records, candidates, ledger = _claim(part)
    assert len(records) == 2 and records[0] == records[1] and records[0] is not records[1]
    first, second = (ledger.defining_of(candidate) for candidate in candidates)
    assert first.isdisjoint(second)
    assert ledger.graph.common_valid_solid(first) != ledger.graph.common_valid_solid(second)
    for record, candidate in zip(records, candidates, strict=True):
        _assert_role(record, candidate, ledger)


@pytest.mark.parametrize("unequal", [False, True])
def test_disjoint_same_solid_pad_occurrences_keep_exact_roles(unequal: bool) -> None:
    base = Box(140, 80, 10)
    left = Pos(-40, 0, 7) * Box(24, 18, 4)
    right = Pos(40, 0, 7.5 if unequal else 7) * Box(30 if unequal else 24, 18, 5 if unequal else 4)
    records, candidates, ledger = _claim(base + left + right)
    assert len(records) == 2
    if not unequal:
        assert records[0].z0 == records[1].z0 and records[0].z1 == records[1].z1
    for record, candidate in zip(records, candidates, strict=True):
        _assert_role(record, candidate, ledger)
    assert ledger.defining_of(candidates[0]).isdisjoint(ledger.defining_of(candidates[1]))


def test_intervening_levels_do_not_change_body_local_pad_base() -> None:
    base = Box(120, 70, 8)
    wall = Pos(-50, 0, 20) * Box(10, 70, 32)
    lower_step = Pos(10, 0, 8) * Box(45, 50, 8)
    raised_pad = Pos(30, 0, 20) * Box(24, 18, 16)
    (record,), (candidate,), ledger = _claim(base + wall + lower_step + raised_pad)
    assert record == RaisedPad(18, 42, -9, 9, 12, 28)
    _assert_role(record, candidate, ledger)


def test_later_body_failure_leaves_family_empty(monkeypatch) -> None:
    part = Compound([Pos(-60, 0, 0) * _pad(), Pos(60, 0, 0) * _pad()])
    ledger = ClaimLedger(FaceGraph(part))
    original = ledger.graph.common_valid_solid
    calls = 0

    def fail_second(nodes):
        nonlocal calls
        calls += 1
        return None if calls == 2 else original(nodes)

    monkeypatch.setattr(ledger.graph, "common_valid_solid", fail_second)
    with pytest.raises(ValueError, match="one valid solid"):
        _discover_rectangular_pads(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.PADS).candidates == ()


def test_equal_value_role_permutation_refuses_before_publication(monkeypatch) -> None:
    import b123d_recognisers.pads as module

    part = _pad()
    ledger = ClaimLedger(FaceGraph(part))
    original = module._recognise_rectangular_pads_one

    def permuted(source, *, tol):
        (proposal,) = original(source, tol=tol)
        roles = proposal.wall_roles
        return [
            proposal,
            module._PadProposal(
                proposal.record,
                proposal.top_face,
                (roles[1], roles[0], roles[2], roles[3]),
            ),
        ]

    monkeypatch.setattr(module, "_recognise_rectangular_pads_one", permuted)
    with pytest.raises(ValueError, match="ambiguous defining occurrences"):
        _discover_rectangular_pads(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.PADS).candidates == ()


def test_repeated_shallow_wrappers_collapse_to_same_ordered_roles(monkeypatch) -> None:
    import b123d_recognisers.pads as module

    part = _pad()
    original = module._recognise_rectangular_pads_one

    def repeated(source, *, tol):
        (proposal,) = original(source, tol=tol)
        wrapped = module._PadProposal(
            proposal.record,
            copy.copy(proposal.top_face),
            tuple((copy.copy(role[0]),) for role in proposal.wall_roles),
        )
        return [proposal, wrapped]

    monkeypatch.setattr(module, "_recognise_rectangular_pads_one", repeated)
    (record,), (candidate,), ledger = _claim(part)
    _assert_role(record, candidate, ledger)


def test_late_binding_failure_leaves_family_empty(monkeypatch) -> None:
    part = Compound([Pos(-60, 0, 0) * _pad(), Pos(60, 0, 0) * _pad()])
    ledger = ClaimLedger(FaceGraph(part))
    original = ledger.graph.require_node
    calls = 0

    def fail_later(face):
        nonlocal calls
        calls += 1
        if calls > 5:
            raise ValueError("later Pad binding failed")
        return original(face)

    monkeypatch.setattr(ledger.graph, "require_node", fail_later)
    with pytest.raises(ValueError, match="later Pad binding failed"):
        _discover_rectangular_pads(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.PADS).candidates == ()


def test_foreign_writer_refuses_before_publication() -> None:
    foreign = ClaimLedger(FaceGraph(Pos(200, 0, 0) * _pad()))
    with pytest.raises(ValueError):
        _discover_rectangular_pads(_pad(), writer=foreign.writer)
    assert foreign.candidate_set(FamilyId.PADS).candidates == ()


def test_supported_transforms_preserve_writer_lifecycle() -> None:
    original = _pad()
    for part in (
        Pos(17, -9, 4) * original,
        Rot(0, 0, 90) * original,
        original.mirror(Plane.YZ),
        original.scale(0.2),
        original.scale(5),
    ):
        records, candidates, ledger = _claim(part)
        assert records
        for record, candidate in zip(records, candidates, strict=True):
            _assert_role(record, candidate, ledger)


def test_step_round_trip_preserves_pad_role_correspondence(tmp_path) -> None:
    source_records, source_candidates, source_ledger = _claim(_pad())
    target = tmp_path / "pad.step"
    assert export_step(_pad(), target)
    imported_records, imported_candidates, imported_ledger = _claim(import_step(target))
    assert [record.to_dict() for record in imported_records] == [
        record.to_dict() for record in source_records
    ]
    assert [len(source_ledger.defining_of(candidate)) for candidate in source_candidates] == [5]
    assert [len(imported_ledger.defining_of(candidate)) for candidate in imported_candidates] == [5]


def test_reversed_face_traversal_preserves_pad_occurrence_roles(monkeypatch) -> None:
    part = Compound([Pos(-60, 0, 0) * _pad(), Pos(60, 0, 0) * _pad()])
    baseline = [record.to_dict() for record in recognise_rectangular_pads(part)]
    solid_type = type(part.solids()[0])
    original = solid_type.faces

    def reversed_faces(self):
        faces = original(self)
        return type(faces)(reversed(faces))

    monkeypatch.setattr(solid_type, "faces", reversed_faces)
    records, _candidates, _ledger = _claim(part)
    assert [record.to_dict() for record in records] == baseline


def test_open_shell_keeps_public_behavior_but_refuses_aggregate() -> None:
    shell = Shell(_pad().faces())
    assert recognise_rectangular_pads(shell)
    ledger = ClaimLedger(FaceGraph(shell))
    with pytest.raises(ValueError, match="one valid solid"):
        _discover_rectangular_pads(shell, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.PADS).candidates == ()


@pytest.mark.parametrize(
    "part",
    [
        Box(80, 60, 10),
        Box(80, 60, 10) + Pos(0, 0, 7) * Box(80, 20, 4),
        Box(80, 60, 10) - Pos(0, 0, 8) * Box(30, 20, 4),
    ],
)
def test_stock_ledge_and_recess_issue_no_pad(part) -> None:
    assert recognise_rectangular_pads(part) == []
    ledger = ClaimLedger(FaceGraph(part))
    assert _discover_rectangular_pads(part, writer=ledger.writer) == []
    assert ledger.candidate_set(FamilyId.PADS).candidates == ()


def test_custom_tolerance_preserves_full_lifecycle() -> None:
    records, candidates, ledger = _claim(_pad(), tol=0.1)
    assert records
    _assert_role(records[0], candidates[0], ledger)


@pytest.mark.parametrize(
    ("radius", "accepted"),
    [
        (math.sqrt(3 / math.pi) * 0.99, True),
        (math.sqrt(3 / math.pi), True),
        (math.sqrt(3 / math.pi) * 1.01, False),
    ],
)
def test_top_area_deficit_boundary_preserves_current_semantics(radius, accepted) -> None:
    part = _perforated_pad(radius)
    if accepted:
        records, candidates, ledger = _claim(part)
        assert len(records) == 1
        _assert_role(records[0], candidates[0], ledger)
    else:
        assert recognise_rectangular_pads(part) == []
        ledger = ClaimLedger(FaceGraph(part))
        assert _discover_rectangular_pads(part, writer=ledger.writer) == []
        assert ledger.candidate_set(FamilyId.PADS).candidates == ()


def test_stock_envelope_wall_remains_defining_below_local_base() -> None:
    part = Box(80, 60, 10) + Pos(25, 0, 7) * Box(30, 20, 4)
    (record,), (candidate,), ledger = _claim(part)
    defining = ledger.defining_of(candidate)
    walls = [node for node in defining if abs(ledger.graph.normal(node)[2]) <= 0.01]
    assert record.z0 == 5
    assert min(ledger.graph.bounds(node)[2][0] for node in walls) == pytest.approx(
        part.bounding_box().min.Z
    )
    assert max(ledger.graph.bounds(node)[2][0] for node in walls) == pytest.approx(record.z0)


@pytest.mark.parametrize(("height", "accepted"), [(0.199, False), (0.2, False), (0.201, True)])
def test_absolute_height_threshold_is_strict(height: float, accepted: bool) -> None:
    part = Box(80, 60, 10) + Pos(0, 0, 5 + height / 2) * Box(30, 20, height)
    if accepted:
        records, candidates, ledger = _claim(part)
        assert len(records) == 1
        _assert_role(records[0], candidates[0], ledger)
    else:
        assert recognise_rectangular_pads(part) == []
        ledger = ClaimLedger(FaceGraph(part))
        assert _discover_rectangular_pads(part, writer=ledger.writer) == []
        assert ledger.candidate_set(FamilyId.PADS).candidates == ()


@pytest.mark.parametrize(("width", "accepted"), [(0.199, False), (0.2, False), (0.201, True)])
def test_footprint_width_threshold_is_strict(width: float, accepted: bool) -> None:
    part = Box(20, 20, 2) + Pos(0, 0, 2) * Box(width, 2, 2)
    if accepted:
        records, candidates, ledger = _claim(part)
        assert len(records) == 1
        _assert_role(records[0], candidates[0], ledger)
    else:
        assert recognise_rectangular_pads(part) == []
        ledger = ClaimLedger(FaceGraph(part))
        assert _discover_rectangular_pads(part, writer=ledger.writer) == []
        assert ledger.candidate_set(FamilyId.PADS).candidates == ()


@pytest.mark.parametrize(
    ("width", "accepted"), [(19.598, True), (19.6, False), (19.602, False)]
)
def test_full_span_margin_boundary_is_inclusive(width: float, accepted: bool) -> None:
    part = Box(20, 20, 2) + Pos(0, 0, 2) * Box(width, 2, 2)
    if accepted:
        records, candidates, ledger = _claim(part)
        assert len(records) == 1
        _assert_role(records[0], candidates[0], ledger)
    else:
        assert recognise_rectangular_pads(part) == []
        ledger = ClaimLedger(FaceGraph(part))
        assert _discover_rectangular_pads(part, writer=ledger.writer) == []
        assert ledger.candidate_set(FamilyId.PADS).candidates == ()


def test_small_pad_on_large_part_remains_attributed() -> None:
    part = Box(10_000, 10_000, 10) + Pos(0, 0, 6) * Box(1, 1, 2)
    (record,), (candidate,), ledger = _claim(part)
    _assert_role(record, candidate, ledger)


@pytest.mark.parametrize("tol", [-0.1, float("nan"), float("inf")])
def test_existing_invalid_tolerance_behavior_remains_empty(tol: float) -> None:
    part = _pad()
    assert recognise_rectangular_pads(part, tol=tol) == []
    ledger = ClaimLedger(FaceGraph(part))
    assert _discover_rectangular_pads(part, tol=tol, writer=ledger.writer) == []
    assert ledger.candidate_set(FamilyId.PADS).candidates == ()


@pytest.mark.parametrize(
    "part",
    [Rot(8, 0, 0) * _pad(), Box(80, 60, 10) + Pos(0, 0, 7) * Cylinder(8, 4)],
)
def test_non_z_and_curved_top_shapes_issue_no_pad(part) -> None:
    assert recognise_rectangular_pads(part) == []
    ledger = ClaimLedger(FaceGraph(part))
    assert _discover_rectangular_pads(part, writer=ledger.writer) == []
    assert ledger.candidate_set(FamilyId.PADS).candidates == ()


@pytest.mark.parametrize("mode", ["role_alias", "tied_maximum", "deep_top", "stale_top"])
def test_invalid_role_snapshots_refuse_before_publication(monkeypatch, mode: str) -> None:
    import b123d_recognisers.pads as module

    part = _pad()
    ledger = ClaimLedger(FaceGraph(part))
    original = module._recognise_rectangular_pads_one

    def changed(source, *, tol):
        (proposal,) = original(source, tol=tol)
        roles = proposal.wall_roles
        if mode == "role_alias":
            roles = (roles[0], roles[0], roles[2], roles[3])
        elif mode == "tied_maximum":
            roles = ((roles[0][0], roles[1][0]), roles[1], roles[2], roles[3])
        top = proposal.top_face
        if mode in {"deep_top", "stale_top"}:
            top = copy.deepcopy(top)
            if mode == "stale_top":
                top = Pos(1, 0, 0) * top
        return [module._PadProposal(proposal.record, top, roles)]

    monkeypatch.setattr(module, "_recognise_rectangular_pads_one", changed)
    with pytest.raises(ValueError):
        _discover_rectangular_pads(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.PADS).candidates == ()


def test_cross_occurrence_role_reuse_refuses_before_publication(monkeypatch) -> None:
    import b123d_recognisers.pads as module

    part = Compound([Pos(-60, 0, 0) * _pad(), Pos(60, 0, 0) * _pad()])
    ledger = ClaimLedger(FaceGraph(part))
    original = module._recognise_rectangular_pads_one
    first_roles = None

    def reused(source, *, tol):
        nonlocal first_roles
        proposals = original(source, tol=tol)
        if first_roles is None:
            first_roles = proposals[0].wall_roles
            return proposals
        proposal = proposals[0]
        return [module._PadProposal(proposal.record, proposal.top_face, first_roles)]

    monkeypatch.setattr(module, "_recognise_rectangular_pads_one", reused)
    with pytest.raises(ValueError):
        _discover_rectangular_pads(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.PADS).candidates == ()


def test_private_core_has_one_production_writer_caller_and_two_record_paths() -> None:
    core_sites: list[tuple[str, ast.Call]] = []
    constructors: list[tuple[str, ast.Call]] = []
    for path in (ROOT / "src/b123d_recognisers").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for qualified, call in _qualified_calls(tree):
            if qualified.endswith("._discover_rectangular_pads") or qualified == (
                "_discover_rectangular_pads"
            ):
                core_sites.append((path.name, call))
            if qualified.endswith(".RaisedPad") or qualified == "RaisedPad":
                constructors.append((path.name, call))

    assert {path for path, _call in core_sites} == {"pads.py", "_registry.py"}
    registry_call = next(call for path, call in core_sites if path == "_registry.py")
    keywords = {keyword.arg: keyword.value for keyword in registry_call.keywords}
    writer = keywords["writer"]
    assert isinstance(writer, ast.Attribute) and writer.attr == "writer"
    assert isinstance(writer.value, ast.Name) and writer.value.id == "s"
    assert [(path, len(call.args)) for path, call in constructors] == [
        ("pads.py", 6),
        ("pads.py", 6),
    ]


def test_terminal_inventory_retains_nonempty_pad_identity() -> None:
    product = _take_inventory(_pad())
    candidates = product.physical.candidate_set(FamilyId.PADS).candidates
    assert len(candidates) == len(product.result.pads) == 1
    assert candidates[0].record is product.result.pads[0]
    assert len(product.evidence.defining_of(candidates[0])) == 5
