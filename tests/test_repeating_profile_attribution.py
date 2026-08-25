"""F5: repeating radial profiles own their exact opposed source faces."""

from __future__ import annotations

import ast
import inspect
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from build123d import Compound, Plane, Pos, Rot

import b123d_recognisers.repeating_profiles as module
from b123d_recognisers import recognise_repeating_radial_profiles
from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._registry import PHYSICAL_DEFINITIONS, FullyAttributed, NotCounted
from b123d_recognisers.result import _take_inventory
from tests.golden._common import toothed_prism

ROOT = Path(__file__).parents[1]


def _source_faces(part, graph: FaceGraph):
    """Independently select the two original planar Z-extremal profile faces."""

    bbox = part.bounding_box()
    lo = float(bbox.min.Z)
    hi = float(bbox.max.Z)
    metric_tol = max(1e-5, max(bbox.size.X, bbox.size.Y, bbox.size.Z) * 1e-5)
    lower = []
    upper = []
    for node in graph.nodes:
        if not graph.is_planar(node):
            continue
        normal = graph.normal(node)
        if normal is None or abs(normal[2]) < 0.999:
            continue
        z_lo, z_hi = graph.bounds(node)[2]
        if abs(z_lo - lo) <= metric_tol and abs(z_hi - lo) <= metric_tol:
            lower.append(node)
        if abs(z_lo - hi) <= metric_tol and abs(z_hi - hi) <= metric_tol:
            upper.append(node)
    assert len(lower) == len(upper) == 1
    assert graph.normal(lower[0])[2] < 0 and graph.normal(upper[0])[2] > 0
    return lower[0], upper[0]


def _assert_attributed(part, *, repeats: int):
    public = recognise_repeating_radial_profiles(part)
    product = _take_inventory(part)
    records = product.result.repeating_radial_profiles
    candidates = product.physical.candidate_set(FamilyId.REPEATING_RADIAL_PROFILES).candidates
    assert [record.to_dict() for record in records] == [record.to_dict() for record in public]
    assert len(records) == len(candidates) == 1
    candidate = candidates[0]
    record = records[0]
    assert candidate.record is record
    assert record.axis == "z"
    assert record.repeat_count == repeats
    assert record.edge_count == 2 * repeats
    expected = frozenset(_source_faces(part, product.context.graph))
    assert product.evidence.defining_of(candidate) == expected
    assert product.context.graph.common_valid_solid(expected) is not None
    return record


@pytest.mark.parametrize("repeats", [6, 8, 10])
def test_repeat_counts_own_exact_opposed_faces(repeats: int) -> None:
    _assert_attributed(toothed_prism(repeats=repeats), repeats=repeats)


def test_current_odd_repeat_fixture_behavior_is_unchanged() -> None:
    # The established straight-edge fixture recognises even counts only; accepting the odd
    # variants would be a predicate change, not attribution work. The pure reducer suite pins
    # the nominal minimum-five boundary independently.
    assert recognise_repeating_radial_profiles(toothed_prism(repeats=5)) == []
    assert recognise_repeating_radial_profiles(toothed_prism(repeats=11)) == []


@pytest.mark.parametrize(
    "part",
    [
        Pos(17, -13, 29) * toothed_prism(),
        Rot(0, 0, 37) * toothed_prism(),
        toothed_prism().mirror(Plane.YZ),
        toothed_prism().mirror(Plane.XZ),
        toothed_prism().scale(0.2),
        toothed_prism().scale(5),
    ],
)
def test_axis_preserving_transforms_keep_source_roles(part) -> None:
    _assert_attributed(part, repeats=8)


def test_equal_coincident_solids_remain_distinct_occurrences() -> None:
    first = toothed_prism()
    part = Compound([first, deepcopy(first)])
    ledger = ClaimLedger(FaceGraph(part))
    records = module._discover_repeating_radial_profiles(part, writer=ledger.writer)
    candidates = ledger.candidate_set(FamilyId.REPEATING_RADIAL_PROFILES).candidates
    assert len(records) == len(candidates) == 2
    assert records[0] == records[1] and records[0] is not records[1]
    assert candidates[0].record is records[0] and candidates[1].record is records[1]
    defining = [ledger.defining_of(candidate) for candidate in candidates]
    assert all(len(nodes) == 2 for nodes in defining)
    assert defining[0].isdisjoint(defining[1])
    assert ledger.graph.common_valid_solid(defining[0]) != ledger.graph.common_valid_solid(
        defining[1]
    )


def test_public_path_is_writer_free_and_value_stable(monkeypatch) -> None:
    part = toothed_prism()
    expected = [record.to_dict() for record in recognise_repeating_radial_profiles(part)]
    original = module._discover_repeating_radial_profiles
    seen = []

    def observed(*args, **kwargs):
        seen.append(kwargs.get("writer"))
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "_discover_repeating_radial_profiles", observed)
    actual = [record.to_dict() for record in module.recognise_repeating_radial_profiles(part)]
    assert actual == expected
    assert seen == [None]


@pytest.mark.parametrize("failure", ["same", "stale", "body", "late"])
def test_identity_and_body_failures_are_named_and_atomic(monkeypatch, failure: str) -> None:
    part = toothed_prism()
    ledger = ClaimLedger(FaceGraph(part))
    original = module._recognise_solid

    def corrupted(*args, **kwargs):
        proposal = original(*args, **kwargs)[0]
        if failure == "same":
            return [replace(proposal, upper_face=proposal.lower_face)]
        if failure == "stale":
            return [replace(proposal, upper_face=Pos(0, 0, 100) * proposal.upper_face)]
        if failure == "late":
            broken = replace(proposal, upper_face=Pos(0, 0, 100) * proposal.upper_face)
            return [proposal, broken]
        return [proposal]

    monkeypatch.setattr(module, "_recognise_solid", corrupted)
    if failure == "body":
        monkeypatch.setattr(ledger.graph, "common_valid_solid", lambda _nodes: None)
    with pytest.raises(module._RepeatingRadialAttributionError):
        module._discover_repeating_radial_profiles(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.REPEATING_RADIAL_PROFILES).candidates == ()


def test_registry_status_and_not_counted_disposition_are_exact() -> None:
    definition = next(
        item for item in PHYSICAL_DEFINITIONS if item.family is FamilyId.REPEATING_RADIAL_PROFILES
    )
    assert isinstance(definition.attribution, FullyAttributed)
    assert isinstance(definition.census, NotCounted)
    assert definition.census.reason == "correspondence evidence is not a distinct feature"


def test_private_core_and_constructor_rosters_are_closed() -> None:
    package = ROOT / "src/b123d_recognisers"
    sites = []
    constructors = []
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        aliases = set()
        for statement in tree.body:
            if isinstance(statement, ast.ImportFrom) and statement.module == (
                "b123d_recognisers.repeating_profiles"
            ):
                aliases.update(
                    alias.asname or alias.name
                    for alias in statement.names
                    if alias.name == "_discover_repeating_radial_profiles"
                )
        if path.name == "repeating_profiles.py":
            aliases.add("_discover_repeating_radial_profiles")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id in aliases:
                sites.append((path.name, node))
            name = node.func.id if isinstance(node.func, ast.Name) else ""
            if name == "RepeatingRadialProfile":
                constructors.append(path.name)
    assert {path for path, _call in sites} == {"repeating_profiles.py", "_registry.py"}
    registry_call = next(call for path, call in sites if path == "_registry.py")
    keywords = {keyword.arg: keyword.value for keyword in registry_call.keywords}
    assert isinstance(keywords["writer"], ast.Attribute)
    assert keywords["writer"].attr == "writer"
    public_call = next(call for path, call in sites if path == "repeating_profiles.py")
    assert all(keyword.arg != "writer" for keyword in public_call.keywords)
    assert constructors == ["repeating_profiles.py"]
    assert tuple(inspect.signature(recognise_repeating_radial_profiles).parameters) == (
        "part",
        "tol",
    )
