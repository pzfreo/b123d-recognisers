# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

from __future__ import annotations

import ast
import sys
from pathlib import Path

from build123d import (
    Box,
    BuildPart,
    BuildSketch,
    Cylinder,
    Plane,
    Pos,
    RegularPolygon,
    Rot,
    extrude,
)

from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._registry import PHYSICAL_DEFINITIONS, FullyAttributed
from b123d_recognisers.result import _take_inventory

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))

from per_face_scan import _scan_part, inventory_attribution  # noqa: E402


def test_generic_attribution_report_covers_all_physical_families_from_one_product() -> None:
    product = _take_inventory(Box(20, 20, 10) - Pos(0, 0, -5) * Cylinder(3, 20))
    report = inventory_attribution(product)

    assert set(report) == {family.value for family in FamilyId if family is not FamilyId.LEGACY}
    assert all(
        set(row)
        == {
            "records",
            "candidates",
            "accepted",
            "attributed_candidates",
            "attributed_accepted",
            "defining_face_occurrences",
            "distinct_defining_faces",
            "status",
            "reason",
        }
        for row in report.values()
    )
    assert all(row["attributed_candidates"] <= row["candidates"] for row in report.values())
    assert all(row["attributed_accepted"] <= row["accepted"] for row in report.values())
    assert all(
        report[definition.family.value]["attributed_candidates"]
        == report[definition.family.value]["candidates"]
        for definition in PHYSICAL_DEFINITIONS
        if isinstance(definition.attribution, FullyAttributed)
    )
    assert report[FamilyId.HOLES.value]["status"] == "fully_attributed"


def test_generic_report_counts_partial_attribution_without_calling_it_complete() -> None:
    # A straight through slot follows the measured paired-wall path; the family remains globally
    # incomplete because its separate cap-recovered path has no defining ownership proof yet.
    part = Box(30, 30, 10) - Box(12, 5, 20)
    report = inventory_attribution(_take_inventory(part))
    slots = report[FamilyId.SLOTS.value]

    assert slots["status"] == "incomplete_attribution"
    assert slots["attributed_candidates"] <= slots["candidates"]


def test_generic_report_keeps_rejected_physical_attribution_separate() -> None:
    wedge = 5.657
    part = Box(60, 40, 12) - Pos(-20, 20, 6) * Rot(45, 0, 0) * Box(30, wedge, wedge)
    chamfers = inventory_attribution(_take_inventory(part))[FamilyId.CHAMFERS.value]

    assert chamfers["candidates"] == chamfers["attributed_candidates"] == 1
    assert chamfers["accepted"] == chamfers["attributed_accepted"] == 0
    claimed, _records, _covered, _generic = _scan_part(part, [0] * len(part.faces()))
    assert "Chamfer" not in claimed


def test_generic_report_distinguishes_projected_records_from_inventory() -> None:
    with BuildPart() as bore:
        with BuildSketch(Plane.XY):
            RegularPolygon(9, 6)
        extrude(amount=40, both=True)
    product = _take_inventory(Box(60, 40, 20) - bore.part, rotational=True)
    passages = inventory_attribution(product)[FamilyId.PASSAGES.value]

    assert passages["records"] == 0
    assert passages["candidates"] == passages["accepted"] == 1
    assert passages["attributed_candidates"] == passages["attributed_accepted"] == 1


def test_per_face_tool_has_one_inventory_path_and_no_recogniser_rerun() -> None:
    tree = ast.parse(
        (Path(__file__).parents[1] / "tools" / "per_face_scan.py").read_text(encoding="utf-8")
    )
    calls = [node.func for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert sum(isinstance(call, ast.Name) and call.id == "_take_inventory" for call in calls) == 1
    assert not any(
        (isinstance(call, ast.Name) and call.id.startswith("recognise_"))
        or (isinstance(call, ast.Attribute) and call.attr.startswith("recognise_"))
        for call in calls
    )
