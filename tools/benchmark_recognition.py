#!/usr/bin/env python3
"""Measure standalone recognition against the pinned Draftwright source baseline."""

from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from golden_support import canonicalize  # noqa: E402
from recognition_snapshot import recognition_snapshot  # noqa: E402

CASES = (
    "bolt_circle_and_rectangular_grid",
    "chamfers_fillets_and_flats",
    "plates_pads_levels_and_slanted_steps",
    "turned_steps_and_grooves",
)


def _fixture(name: str):
    path = ROOT / "tests" / "golden" / name / "fixture.py"
    spec = importlib.util.spec_from_file_location(f"benchmark_fixture_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _implementation(kind: str, baseline: Path | None):
    if kind == "package":
        import b123d_recognisers as recognition
        from b123d_recognisers import feature_census

        return recognition, feature_census

    if baseline is None:
        raise SystemExit("--baseline is required for --implementation draftwright")
    sys.path.insert(0, str(baseline / "src"))
    import draftwright.recognition as recognition
    from draftwright.score import feature_census

    return recognition, feature_census


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--implementation", choices=("package", "draftwright"), required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--iterations", type=int, default=3)
    args = parser.parse_args()

    recognition, feature_census = _implementation(args.implementation, args.baseline)
    fixtures = [(name, _fixture(name)) for name in CASES]

    # Construct a fresh BRep for each timed run. This includes the same fixture cost on both
    # sides and avoids rewarding mutable OCCT caches retained by a reused shape.
    samples = []
    digest = None
    for _ in range(args.iterations):
        started = time.perf_counter()
        snapshots = {
            name: recognition_snapshot(recognition, feature_census, fixture.build_fixture())
            for name, fixture in fixtures
        }
        samples.append(time.perf_counter() - started)
        canonical = canonicalize(snapshots)
        if digest is None:
            digest = canonical
        elif canonical != digest:
            raise RuntimeError("recognition output changed between benchmark iterations")

    print(
        json.dumps(
            {
                "implementation": args.implementation,
                "iterations": args.iterations,
                "cases": list(CASES),
                "seconds": samples,
                "median_seconds": statistics.median(samples),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
