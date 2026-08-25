#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the frozen F6a optional-sidecar performance gate."""

from __future__ import annotations

import json
import math
import platform
import resource
import statistics
import time

from build123d import Box, Cylinder, Polygon, Pos, Rot, extrude

from b123d_recognisers._correspondence import correspondence_snapshot
from b123d_recognisers.result import _take_inventory

SAMPLES = 5
MISS_RATIO_CEILING = 0.50
HIT_RATIO_CEILING = 0.05
RSS_RATIO_CEILING = 0.10


def _notched_round(repeats: int):
    part = Cylinder(20, 10)
    for index in range(repeats):
        part -= Rot(0, 0, 360 * index / repeats) * Pos(18, 0, 0) * Box(8, 3, 10)
    return part


def _line_profile(repeats: int = 8):
    points = []
    for index in range(2 * repeats):
        angle = 2 * math.pi * index / (2 * repeats)
        radius = 20 if index % 2 == 0 else 16
        points.append((radius * math.cos(angle), radius * math.sin(angle)))
    return extrude(Polygon(*points), 10)


def _matrix():
    return (_notched_round(5), _notched_round(7), _line_profile())


def _inventory_sample(parts) -> float:
    started = time.perf_counter()
    tuple(_take_inventory(part) for part in parts)
    return time.perf_counter() - started


def _miss_sample(parts) -> tuple[float, tuple]:
    products = tuple(_take_inventory(part) for part in parts)
    started = time.perf_counter()
    tuple(correspondence_snapshot(product) for product in products)
    return time.perf_counter() - started, products


def _hit_sample(products) -> float:
    started = time.perf_counter()
    tuple(correspondence_snapshot(product) for product in products)
    return time.perf_counter() - started


def main() -> int:
    parts = _matrix()
    _inventory_sample(parts)  # unmeasured process warm-up
    baseline = tuple(_inventory_sample(parts) for _ in range(SAMPLES))
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    miss_runs = tuple(_miss_sample(parts) for _ in range(SAMPLES))
    misses = tuple(item[0] for item in miss_runs)
    products = miss_runs[-1][1]
    hits = tuple(_hit_sample(products) for _ in range(SAMPLES))
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    baseline_median = statistics.median(baseline)
    miss_median = statistics.median(misses)
    hit_median = statistics.median(hits)
    rss_ratio = max(0.0, (rss_after - rss_before) / max(1, rss_before))
    evidence = {
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "baseline_seconds": baseline,
        "cache_miss_seconds": misses,
        "cache_hit_seconds": hits,
        "baseline_median": baseline_median,
        "cache_miss_median": miss_median,
        "cache_hit_median": hit_median,
        "cache_miss_ratio": miss_median / baseline_median,
        "cache_hit_ratio": hit_median / baseline_median,
        "rss_before": rss_before,
        "rss_after": rss_after,
        "rss_growth_ratio": rss_ratio,
        "ceilings": {
            "cache_miss_ratio": MISS_RATIO_CEILING,
            "cache_hit_ratio": HIT_RATIO_CEILING,
            "rss_growth_ratio": RSS_RATIO_CEILING,
        },
    }
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if (
        evidence["cache_miss_ratio"] <= MISS_RATIO_CEILING
        and evidence["cache_hit_ratio"] <= HIT_RATIO_CEILING
        and rss_ratio <= RSS_RATIO_CEILING
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
