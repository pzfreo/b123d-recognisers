"""Pinned authored boundary-blend evidence for Epic #290 / issue #277."""

from __future__ import annotations

import json

import pytest

from tools.blend_boundary_sweep import (
    BASELINE_COMMIT,
    JSON_REPORT,
    MARKDOWN_REPORT,
    PERFORMANCE_BUDGET_SECONDS,
    PERFORMANCE_MEASUREMENT,
    markdown,
    sweep,
)


@pytest.fixture(scope="module")
def report():
    return sweep()


def test_checked_in_blend_boundary_evidence_is_current(report) -> None:

    assert report == json.loads(JSON_REPORT.read_text(encoding="utf-8"))
    assert markdown(report) == MARKDOWN_REPORT.read_text(encoding="utf-8")


def test_sweep_separates_survival_loss_and_reclassification(report) -> None:
    assert report["schema"] == 1
    assert report["baseline_commit"] == BASELINE_COMMIT == (
        "5569f1405c87be8156e20726152d481623fee6c0"
    )
    assert report["radii_role"] == "authored input geometry, not recognition thresholds"
    assert report["performance_budget_seconds"] == PERFORMANCE_BUDGET_SECONDS == 30.0
    assert report["performance_measurement"] == PERFORMANCE_MEASUREMENT
    assert PERFORMANCE_MEASUREMENT["median_seconds"] == 11.518
    assert report["totals"] == {
        "cases": 5,
        "variants": 15,
        "same-family": 3,
        "changed-record": 6,
        "reclassified": 3,
        "absent": 3,
    }


def test_sweep_identifies_pad_as_the_second_consumer_candidate(report) -> None:
    pad = report["cases"]["rectangular-pad-side-boundary"]
    assert {variant["outcome"] for variant in pad["variants"]} == {"absent"}
    assert all(variant["removed_families"] == ["pads"] for variant in pad["variants"])

    boss = report["cases"]["polygonal-boss-side-boundary"]
    assert {variant["outcome"] for variant in boss["variants"]} == {"same-family"}
    assert all(
        variant["expected_records"] == boss["plain_records"]["polygonal_bosses"]
        for variant in boss["variants"]
    )


def test_pocket_reclassification_is_not_reported_as_simple_loss(report) -> None:
    pocket = report["cases"]["blind-pocket-floor-perimeter"]

    assert {variant["outcome"] for variant in pocket["variants"]} == {"reclassified"}
    assert all(
        variant["introduced_families"] == ["prismatic_pockets"]
        for variant in pocket["variants"]
    )
