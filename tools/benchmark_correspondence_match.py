#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Run the frozen private F6b1 comparison-only performance gate."""

from __future__ import annotations

import json
import math
import platform
import resource
import statistics
import time

from build123d import Align, Box, Compound, Polygon, Pos, extrude

from b123d_recognisers._correspondence import correspondence_snapshot
from b123d_recognisers._correspondence_match import correspondence_changes
from b123d_recognisers.result import _take_inventory

SAMPLES = 5
MEDIAN_RATIO_CEILING = 0.25
RSS_GROWTH_CEILING = 0.05


def _line_profile(repeats: int):
    points = []
    for sector in range(repeats):
        for offset, radius in enumerate((20.0, 16.0, 20.0, 18.0)):
            angle = 2.0 * math.pi * (sector / repeats + offset / (4 * repeats))
            points.append((radius * math.cos(angle), radius * math.sin(angle)))
    return extrude(Polygon(*points), 10)


def _asymmetric_profile():
    return _line_profile(5) + Pos(18, 0, 5) * Box(
        4, 3, 2, align=(Align.CENTER, Align.CENTER, Align.CENTER)
    )


def _pair_shapes():
    source = _asymmetric_profile()
    return (
        (source, source),
        (source, Pos(11, -7, 3) * source),
        (source, (Pos(11, -7, 3) * source).scale(2.0)),
        (
            Compound([_line_profile(5), _line_profile(5)]),
            Pos(11, -7, 3) * Compound([_line_profile(5), _line_profile(5)]),
        ),
    )


def _products():
    return tuple(
        (_take_inventory(before), _take_inventory(after))
        for before, after in _pair_shapes()
    )


def _snapshot_sample() -> float:
    products = _products()
    started = time.perf_counter()
    for before, after in products:
        correspondence_snapshot(before)
        correspondence_snapshot(after)
    return time.perf_counter() - started


def _comparison_sample(products) -> float:
    started = time.perf_counter()
    for before, after in products:
        correspondence_changes(before, after)
    return time.perf_counter() - started


def main() -> int:
    products = _products()
    for pair in products:
        for product in pair:
            correspondence_snapshot(product)
    _comparison_sample(products)
    baseline = tuple(_snapshot_sample() for _ in range(SAMPLES))
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    comparisons = tuple(_comparison_sample(products) for _ in range(SAMPLES))
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    baseline_median = statistics.median(baseline)
    comparison_median = statistics.median(comparisons)
    ratio = comparison_median / baseline_median
    rss_growth = max(0.0, (rss_after - rss_before) / max(1, rss_before))
    evidence = {
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "matrix": ("unchanged", "moved", "resized", "equal-tie"),
        "warmups": 1,
        "snapshot_materialization_seconds": baseline,
        "comparison_seconds": comparisons,
        "snapshot_materialization_median": baseline_median,
        "comparison_median": comparison_median,
        "median_ratio": ratio,
        "rss_before": rss_before,
        "rss_after": rss_after,
        "rss_growth_ratio": rss_growth,
        "ceilings": {
            "median_ratio": MEDIAN_RATIO_CEILING,
            "rss_growth_ratio": RSS_GROWTH_CEILING,
        },
        "passed": ratio <= MEDIAN_RATIO_CEILING and rss_growth <= RSS_GROWTH_CEILING,
    }
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
