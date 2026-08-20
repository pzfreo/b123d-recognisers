#!/usr/bin/env python3
"""Measure standalone recognition: against the pinned Draftwright baseline, or against ours.

Two workloads, because one of them alone misleads (see `_take_inventory`'s docstring). The
**composite** workload is the release contract -- results and a census over four golden
fixtures, the shape the Draftwright comparison was made on. The **census** workload is
`feature_census` alone over the vendored NIST and real-part STEP, which is what a corpus sweep
costs and where the one-inventory consolidation was paid for.

Reports the **minimum** of its samples, not the median. On a shared box the median moves with
whatever else is running and the minimum is the closest thing to the machine's own answer;
`docs/benchmarks/recognition-budget.md` records what that answer was and what it is allowed
to become.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
import time
from pathlib import Path

try:
    import resource
except ModuleNotFoundError:  # pragma: no cover - the module does not exist on Windows
    resource = None  # type: ignore[assignment]

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


#: The census workload: every vendored STEP that is a real or benchmark part rather than a
#: fixture this project authored. Excluded from the sdist, so this is a development tool.
CENSUS_CORPORA = ("nist", "gramel")


def _census_parts():
    from build123d import import_step

    paths = sorted(
        path
        for corpus in CENSUS_CORPORA
        for path in (ROOT / "tests" / "corpus" / corpus).glob("*.st*p")
    )
    if not paths:
        raise SystemExit("the census workload needs tests/corpus; it is excluded from the sdist")
    return [(path.name, import_step(path)) for path in paths]


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


def _load_budget(path: Path, workload: str, override: float | None):
    """Return the recorded workload and its ceiling multiplier.

    The checked-in JSON is the policy source of truth.  ``override`` exists for an
    intentional one-off experiment; leaving it out must follow the file rather than a
    second default that can silently drift from it.
    """

    payload = json.loads(path.read_text(encoding="utf-8"))
    recorded = payload["workloads"][workload]
    # A workload may carry its own multiplier, because how much noise a measurement has to
    # tolerate depends on how long it runs: a two-second arm on a shared box moves by more
    # than a hundred-second one, and one ceiling for both either misses regressions on the
    # long arm or reports the load on the short one.
    multiplier = recorded.get("budget", payload["budget"]) if override is None else override
    return recorded, float(multiplier)


def _peak_rss_kb() -> int | None:
    """Return the process high-water mark where the standard library exposes it.

    In the unit the field name promises, which takes a conversion: `ru_maxrss` is kibibytes on
    Linux and **bytes** on macOS. Left raw it would make the same process look 1024 times
    larger on one platform than the other, which is a regression that is not there.
    """

    if resource is None:
        return None
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak // 1024 if sys.platform == "darwin" else peak


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--implementation", choices=("package", "draftwright"), required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--workload", choices=("composite", "census"), default="composite")
    parser.add_argument("--check", type=Path, help="a recorded budget to measure against")
    parser.add_argument(
        "--budget",
        type=float,
        help="override the multiplier recorded in the --check JSON for this run",
    )
    args = parser.parse_args()

    recognition, feature_census = _implementation(args.implementation, args.baseline)

    if args.workload == "census":
        # Imported once: `import_step` is most of the wall clock and is not what is being
        # measured. The composite arm rebuilds instead, for the reason below.
        parts = _census_parts()
        cases = [name for name, _ in parts]

        def run():
            return {name: feature_census(part) for name, part in parts}

    else:
        # Construct a fresh BRep for each timed run. This includes the same fixture cost on
        # both sides and avoids rewarding mutable OCCT caches retained by a reused shape.
        fixtures = [(name, _fixture(name)) for name in CASES]
        cases = list(CASES)

        def run():
            return {
                name: recognition_snapshot(recognition, feature_census, fixture.build_fixture())
                for name, fixture in fixtures
            }

    samples = []
    digest = None
    for _ in range(args.iterations):
        started = time.perf_counter()
        produced = run()
        samples.append(time.perf_counter() - started)
        canonical = canonicalize(produced)
        if digest is None:
            digest = canonical
        elif canonical != digest:
            raise RuntimeError("recognition output changed between benchmark iterations")

    result = {
        "implementation": args.implementation,
        "workload": args.workload,
        "iterations": args.iterations,
        "cases": cases,
        "seconds": samples,
        "median_seconds": statistics.median(samples),
        "min_seconds": min(samples),
        # Peak resident set of the whole process, so it includes the kernel's C++ allocations
        # that `tracemalloc` cannot see. A high-water mark, so it never falls back.
        "peak_rss_kb": _peak_rss_kb(),
    }
    print(json.dumps(result, sort_keys=True))

    if args.check is None:
        return 0
    recorded, multiplier = _load_budget(args.check, args.workload, args.budget)
    ceiling = recorded["min_seconds"] * multiplier
    over = result["min_seconds"] > ceiling
    print(
        f"{args.workload}: {result['min_seconds']:.3f}s against a {ceiling:.3f}s ceiling "
        f"({recorded['min_seconds']:.3f}s x {multiplier}) -- {'OVER' if over else 'within'}",
        file=sys.stderr,
    )
    return 1 if over else 0


if __name__ == "__main__":
    raise SystemExit(main())
