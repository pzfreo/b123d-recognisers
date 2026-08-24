"""F5: Channels own exactly their opposed original planar side walls."""

from __future__ import annotations

import ast
import copy
from dataclasses import replace
from pathlib import Path

import pytest
from build123d import Compound, Plane, Pos, Rot, export_step, import_step

import b123d_recognisers._recess_features as feature_module
from b123d_recognisers import recognise_channels
from b123d_recognisers._adjacency import FaceEdges, FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._recess_features import _discover_channels
from b123d_recognisers.result import _take_inventory
from tests.golden.open_channels.fixture import build_fixture

ROOT = Path(__file__).parents[1]


def _assert_roles(part, **kwargs):
    public = recognise_channels(part, **kwargs)
    ledger = ClaimLedger(FaceGraph(part, face_edges=kwargs.get("face_edges")))
    records = _discover_channels(part, writer=ledger.writer, **kwargs)
    assert [record.to_dict() for record in records] == [record.to_dict() for record in public]
    candidates = ledger.candidate_set(FamilyId.CHANNELS).candidates
    assert len(records) == len(candidates)
    for record, candidate in zip(records, candidates, strict=True):
        assert candidate.record is record
        nodes = ledger.defining_of(candidate)
        assert len(nodes) == 2
        assert ledger.graph.common_valid_solid(nodes) is not None
        centres = []
        signs = []
        axis = "xyz".index(record.width_axis)
        for node in nodes:
            face = ledger.graph.face(node)
            assert ledger.graph.is_planar(node)
            centre = face.center()
            centres.append((centre.X, centre.Y, centre.Z)[axis])
            signs.append(ledger.graph.normal(node)[axis])
        ordered = sorted(zip(centres, signs, strict=True))
        assert ordered[0][0] == pytest.approx(record.w_center - record.width / 2)
        assert ordered[1][0] == pytest.approx(record.w_center + record.width / 2)
        assert ordered[0][1] > 0 and ordered[1][1] < 0
    return records, candidates, ledger


def test_canonical_channel_owns_only_two_opposed_walls() -> None:
    records, candidates, ledger = _assert_roles(build_fixture())
    assert len(records) == 1
    assert len(ledger.defining_of(candidates[0])) == 2


def test_public_ledger_remains_graph_only_and_writer_free() -> None:
    part = build_fixture()
    ledger = ClaimLedger(FaceGraph(part))
    assert recognise_channels(part, ledger=ledger) == recognise_channels(part)
    assert ledger.candidate_set(FamilyId.CHANNELS).candidates == ()


@pytest.mark.parametrize(
    "part",
    [
        Pos(13, -9, 7) * build_fixture(),
        Rot(0, 0, 90) * build_fixture(),
        build_fixture().mirror(Plane.YZ),
        build_fixture().scale(0.2),
        build_fixture().scale(5),
    ],
)
def test_axis_preserving_transforms_keep_exact_wall_roles(part) -> None:
    _assert_roles(part)


def test_multiple_bodies_keep_occurrence_and_body_identity() -> None:
    part = Compound([Pos(-80, 0, 0) * build_fixture(), Pos(80, 0, 0) * build_fixture()])
    records, candidates, ledger = _assert_roles(part)
    assert len(records) == 2
    defining = [ledger.defining_of(candidate) for candidate in candidates]
    assert defining[0].isdisjoint(defining[1])
    assert ledger.graph.common_valid_solid(defining[0]) != ledger.graph.common_valid_solid(
        defining[1]
    )


def test_step_traversal_and_supplied_edges_preserve_roles(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "channel.step"
    assert export_step(build_fixture(), target)
    _assert_roles(import_step(target))

    part = build_fixture()
    solid_type = type(part)
    original = solid_type.faces

    def reversed_faces(self):
        faces = original(self)
        return type(faces)(reversed(faces))

    monkeypatch.setattr(solid_type, "faces", reversed_faces)
    _assert_roles(part, face_edges=FaceEdges())


def test_ambiguous_pair_and_reused_wall_refuse_without_prefix(monkeypatch) -> None:
    part = build_fixture()
    ledger = ClaimLedger(FaceGraph(part))
    original = feature_module._channel_proposals_one

    def ambiguous(*args, **kwargs):
        proposals = original(*args, **kwargs)
        other = next(
            node
            for node in ledger.graph.nodes
            if node
            not in {
                proposals[0].low_wall,
                proposals[0].high_wall,
            }
        )
        return [*proposals, replace(proposals[0], high_wall=other)]

    monkeypatch.setattr(feature_module, "_channel_proposals_one", ambiguous)
    with pytest.raises(ValueError, match="ambiguous"):
        _discover_channels(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.CHANNELS).candidates == ()

    monkeypatch.setattr(feature_module, "_channel_proposals_one", original)
    proposals = original(part, None, ledger.graph)

    def reused(*_args, **_kwargs):
        second = replace(
            proposals[0],
            record=replace(proposals[0].record, d_hi=proposals[0].record.d_hi + 1),
        )
        return [proposals[0], second]

    monkeypatch.setattr(feature_module, "_channel_proposals_one", reused)
    with pytest.raises(ValueError, match="reuse"):
        _discover_channels(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.CHANNELS).candidates == ()


def test_foreign_graph_copied_node_and_late_body_failure_are_atomic(monkeypatch) -> None:
    part = build_fixture()
    foreign = ClaimLedger(FaceGraph(Pos(100, 0, 0) * build_fixture()))
    with pytest.raises(ValueError):
        _discover_channels(part, writer=foreign.writer)
    assert foreign.candidate_set(FamilyId.CHANNELS).candidates == ()

    ledger = ClaimLedger(FaceGraph(part))
    original = feature_module._channel_proposals_one

    def copied(*args, **kwargs):
        proposals = original(*args, **kwargs)
        return [replace(proposals[0], low_wall=copy.copy(proposals[0].low_wall))]

    monkeypatch.setattr(feature_module, "_channel_proposals_one", copied)
    with pytest.raises(ValueError):
        _discover_channels(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.CHANNELS).candidates == ()

    monkeypatch.setattr(feature_module, "_channel_proposals_one", original)
    monkeypatch.setattr(ledger.graph, "common_valid_solid", lambda _nodes: None)
    with pytest.raises(ValueError, match="one valid solid"):
        _discover_channels(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.CHANNELS).candidates == ()


def test_terminal_inventory_retains_channel_identity() -> None:
    product = _take_inventory(build_fixture())
    candidates = product.physical.candidate_set(FamilyId.CHANNELS).candidates
    assert len(candidates) == len(product.result.channels) == 1
    assert candidates[0].record is product.result.channels[0]
    assert len(product.evidence.defining_of(candidates[0])) == 2


def test_channel_private_core_and_registry_writer_route_are_closed() -> None:
    sites = []
    for path in (ROOT / "src/b123d_recognisers").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and (
                isinstance(node.func, ast.Name) and node.func.id == "_discover_channels"
            ):
                sites.append((path.name, node))
    assert {name for name, _call in sites} == {"_recess_features.py", "_registry.py"}
    registry = next(call for name, call in sites if name == "_registry.py")
    writer = {keyword.arg: keyword.value for keyword in registry.keywords}["writer"]
    assert isinstance(writer, ast.Attribute) and writer.attr == "writer"

    feature_tree = ast.parse(
        (ROOT / "src/b123d_recognisers/_recess_features.py").read_text(encoding="utf-8")
    )
    public = next(
        node
        for node in feature_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "recognise_channels"
    )
    call = next(node for node in ast.walk(public) if isinstance(node, ast.Call))
    assert all(keyword.arg != "writer" for keyword in call.keywords)
