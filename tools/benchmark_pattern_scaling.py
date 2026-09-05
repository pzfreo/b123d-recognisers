#!/usr/bin/env python3
"""Benchmark complete rectangular hole grids without constructing OCCT geometry."""

from __future__ import annotations

import argparse
import json
import statistics
import time

from quiddity import HoleRecord, RectGrid, recognise_hole_patterns

GRID_SIDES = (5, 7, 10, 14, 20)


def _grid(side: int) -> list[HoleRecord]:
    return [
        HoleRecord(
            axis=(0.0, 0.0, -1.0),
            location=(float(column * 10), float(row * 12), 0.0),
            diameter=5.0,
            depth=10.0,
            bottom="through",
        )
        for row in range(side)
        for column in range(side)
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=5)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be positive")

    results = []
    for side in GRID_SIDES:
        holes = _grid(side)
        samples = []
        for _ in range(args.iterations):
            started = time.perf_counter()
            patterns = recognise_hole_patterns(holes)
            samples.append(time.perf_counter() - started)
            assert len(patterns) == 1
            assert isinstance(patterns[0], RectGrid)
            assert len(patterns[0].holes) == len(holes)
        results.append(
            {
                "holes": len(holes),
                "median_seconds": statistics.median(samples),
                "seconds": samples,
            }
        )

    print(json.dumps({"iterations": args.iterations, "results": results}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
