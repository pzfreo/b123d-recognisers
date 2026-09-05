#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Measure and compare the frozen F6a.2 schema-two/schema-three sidecar gate."""

from __future__ import annotations

import argparse
import json
import math
import platform
import resource
import statistics
import time
from pathlib import Path

from build123d import Box, Cylinder, Polygon, Pos, Rot, extrude

from quiddity._correspondence import correspondence_snapshot
from quiddity.result import _take_inventory

SAMPLES = 5
MEDIAN_RATIO_CEILING = 1.25
RSS_RATIO_CEILING = 1.10


def _notched_round(repeats: int):
    part = Cylinder(20, 10)
    for index in range(repeats):
        part -= Rot(0, 0, 360 * index / repeats) * Pos(18, 0, 0) * Box(8, 3, 10)
    return part


def _line_profile(repeats: int):
    points = []
    for sector in range(repeats):
        for offset, radius in enumerate((20.0, 16.0, 20.0, 18.0)):
            angle = 2 * math.pi * (sector / repeats + offset / (4 * repeats))
            points.append((radius * math.cos(angle), radius * math.sin(angle)))
    return extrude(Polygon(*points), 10)


def _matrix():
    return (_line_profile(5), _notched_round(7), _line_profile(8))


def _sample(parts) -> tuple[float, int]:
    products = tuple(_take_inventory(part) for part in parts)
    started = time.perf_counter()
    snapshots = tuple(correspondence_snapshot(product) for product in products)
    elapsed = time.perf_counter() - started
    return elapsed, snapshots[0].schema_version


def measure() -> dict[str, object]:
    parts = _matrix()
    _sample(parts)
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    samples = tuple(_sample(parts) for _ in range(SAMPLES))
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    versions = {version for _elapsed, version in samples}
    if len(versions) != 1:
        raise RuntimeError("correspondence benchmark observed mixed snapshot schemas")
    seconds = tuple(elapsed for elapsed, _version in samples)
    return {
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "schema_version": versions.pop(),
        "samples": seconds,
        "median_seconds": statistics.median(seconds),
        "peak_rss": rss_after,
        "rss_before": rss_before,
        "matrix": ("5-line", "7-mixed", "8-line"),
        "warmups": 1,
    }


def compare(before: dict[str, object], after: dict[str, object]) -> dict[str, object]:
    before_median = float(before["median_seconds"])
    after_median = float(after["median_seconds"])
    before_rss = int(before["peak_rss"])
    after_rss = int(after["peak_rss"])
    median_ratio = after_median / before_median
    rss_ratio = after_rss / max(1, before_rss)
    passed = median_ratio <= MEDIAN_RATIO_CEILING and rss_ratio <= RSS_RATIO_CEILING
    return {
        "before": before,
        "after": after,
        "median_ratio": median_ratio,
        "rss_ratio": rss_ratio,
        "ceilings": {
            "median_ratio": MEDIAN_RATIO_CEILING,
            "rss_ratio": RSS_RATIO_CEILING,
        },
        "passed": passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compare", nargs=2, metavar=("SCHEMA2_JSON", "SCHEMA3_JSON"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.compare:
        result = compare(
            json.loads(Path(args.compare[0]).read_text()),
            json.loads(Path(args.compare[1]).read_text()),
        )
    else:
        result = measure()
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload)
    else:
        print(payload, end="")
    return 0 if not args.compare or bool(result["passed"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
