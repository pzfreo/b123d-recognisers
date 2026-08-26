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

from build123d import Align, Box, Compound, Polygon, Pos, Rot, extrude

from b123d_recognisers._correspondence import correspondence_snapshot
from b123d_recognisers._correspondence_match import correspondence_changes
from b123d_recognisers.result import _take_inventory

SAMPLES = 5
MEDIAN_RATIO_CEILING = 0.25
RSS_GROWTH_CEILING = 0.05
F6B2_MEDIAN_RATIO_CEILING = 0.50


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


def _partition_profile(height: float, start: float = 0.0, *, phase: float = 13.0):
    points = []
    for sector in range(5):
        for offset, radius in enumerate((20.0, 16.0, 20.0, 18.0)):
            angle = 2.0 * math.pi * (sector / 5 + offset / 20)
            points.append((radius * math.cos(angle), radius * math.sin(angle)))
    return Pos(0, 0, start) * Rot(0, 0, phase) * extrude(Polygon(*points), height)


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


def _partition_pair_shapes():
    return (
        (
            _partition_profile(10.0),
            Compound([_partition_profile(4.0), _partition_profile(6.0, 4.0)]),
        ),
        (
            _partition_profile(10.0),
            Compound(
                [
                    _partition_profile(2.0),
                    _partition_profile(3.0, 2.0),
                    _partition_profile(5.0, 5.0),
                ]
            ),
        ),
        (
            Compound([_partition_profile(4.0), _partition_profile(6.0, 4.0)]),
            _partition_profile(10.0),
        ),
        (
            _partition_profile(10.0, phase=0.0),
            Compound(
                [
                    _partition_profile(4.0, phase=0.0),
                    _partition_profile(6.0, 4.0, phase=0.0),
                ]
            ),
        ),
    )


def _products(shapes):
    return tuple((_take_inventory(before), _take_inventory(after)) for before, after in shapes)


def _snapshot_sample(shapes) -> float:
    products = _products(shapes)
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
    ordinary_shapes = _pair_shapes()
    partition_shapes = _partition_pair_shapes()
    ordinary_products = _products(ordinary_shapes)
    partition_products = _products(partition_shapes)
    for pair in (*ordinary_products, *partition_products):
        for product in pair:
            correspondence_snapshot(product)
    _comparison_sample(ordinary_products)
    _comparison_sample(partition_products)
    ordinary_baseline = tuple(_snapshot_sample(ordinary_shapes) for _ in range(SAMPLES))
    partition_baseline = tuple(_snapshot_sample(partition_shapes) for _ in range(SAMPLES))
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    ordinary_comparisons = tuple(_comparison_sample(ordinary_products) for _ in range(SAMPLES))
    partition_comparisons = tuple(_comparison_sample(partition_products) for _ in range(SAMPLES))
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    ordinary_ratio = statistics.median(ordinary_comparisons) / statistics.median(ordinary_baseline)
    partition_ratio = statistics.median(partition_comparisons) / statistics.median(
        partition_baseline
    )
    rss_growth = max(0.0, (rss_after - rss_before) / max(1, rss_before))
    evidence = {
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "f6b1_matrix": ("unchanged", "moved", "resized", "equal-tie"),
        "f6b2_matrix": (
            "split2",
            "split3",
            "merge",
            "ambiguous-partition",
        ),
        "warmups": 1,
        "f6b1_snapshot_materialization_seconds": ordinary_baseline,
        "f6b1_comparison_seconds": ordinary_comparisons,
        "f6b1_median_ratio": ordinary_ratio,
        "f6b2_snapshot_materialization_seconds": partition_baseline,
        "f6b2_comparison_seconds": partition_comparisons,
        "f6b2_median_ratio": partition_ratio,
        "rss_before": rss_before,
        "rss_after": rss_after,
        "rss_growth_ratio": rss_growth,
        "ceilings": {
            "median_ratio": MEDIAN_RATIO_CEILING,
            "f6b2_median_ratio": F6B2_MEDIAN_RATIO_CEILING,
            "rss_growth_ratio": RSS_GROWTH_CEILING,
        },
        "passed": ordinary_ratio <= MEDIAN_RATIO_CEILING
        and partition_ratio <= F6B2_MEDIAN_RATIO_CEILING
        and rss_growth <= RSS_GROWTH_CEILING,
    }
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
