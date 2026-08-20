# Recognition runtime budget

Two numbers this package is allowed to get slower than, and the workloads they are measured on.
Recorded because the one-inventory consolidation made `feature_census` about 35% slower and the
release workload about 4% slower, and a regression that size is only visible if there is
something to compare it with.

## The two workloads, and why there are two

| Workload | What it runs | Who pays it |
| --- | --- | --- |
| `composite` | two recognition results and one census over four golden fixtures | the release contract, and the shape the Draftwright comparison in `migration/PARITY.md` was made on |
| `census` | `feature_census` over the ten vendored NIST parts and three real gramel parts | a corpus sweep, and where the consolidation was paid for |

Quoting only the composite figure understates what a `feature_census` caller pays; quoting only
the census figure overstates what a consumer of the library pays. Both are recorded, and a claim
about performance that names one should say which.

## The recorded baseline

Measured on the development container at `4bd8b3b`, which is a **shared** machine: these are
minimums over repeated samples rather than medians, because the median moves with whatever else
happens to be running and the minimum is the closest available reading of the machine's own
answer. Peak resident set is the whole process, so it includes the kernel's C++ allocations
that `tracemalloc` cannot see.

| Workload | Iterations | Minimum | Peak RSS |
| --- | ---: | ---: | ---: |
| `composite` | 5 | 1.996 s | 461 MB |
| `census` | 3 | 99.683 s | 484 MB |

The budget is **1.10** — ten percent, which is wider than the run-to-run spread on this box and
narrower than any regression worth arguing about.

## Running it

```
uv run python tools/benchmark_recognition.py --implementation package --workload census \
    --iterations 3 --check docs/benchmarks/recognition-budget.json
```

Exits non-zero when the measured minimum is over the ceiling, and prints both numbers either
way.

**Not run in CI, deliberately.** A wall-clock assertion on a shared runner fails for reasons
that have nothing to do with the code, and a test that fails for unrelated reasons stops being
read. This is a tool to run when a change is expected to cost something, and a number to update
when it legitimately does — with the reason recorded in the commit that moves it.

The baseline is tied to the machine it was taken on. Re-measure both workloads on any other
box before comparing against it; the *ratio* between two arms measured back to back on the same
box is the portable part, not the seconds.
