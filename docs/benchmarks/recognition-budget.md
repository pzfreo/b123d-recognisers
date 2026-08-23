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

Measured on the development container at `51d388b`, which is a **shared** machine: these are
minimums over repeated samples rather than medians, because the median moves with whatever else
happens to be running and the minimum is the closest available reading of the machine's own
answer. Peak resident set is the whole process, so it includes the kernel's C++ allocations
that `tracemalloc` cannot see.

| Workload | Iterations | Minimum | Peak RSS |
| --- | ---: | ---: | ---: |
| `composite` | 5 | 1.927 s | 461 MB |
| `census` | 3 | 99.683 s | 484 MB |

The budget is **1.10** by default, and a workload may record its own. Two arms of very
different length cannot share one ceiling on a shared box:

| Workload | Budget | Why |
| --- | ---: | --- |
| `census` | 1.10 | a hundred seconds, stable here, and the arm the consolidation regression was about |
| `composite` | 1.40 | two seconds, and its minimum-of-five ranged 1.93 s to 2.66 s over one evening with nothing else obviously running |

The composite figure is loose because of the host, not because the code is allowed to be forty
percent slower. On a dedicated machine it would be the tighter of the two; here, a ceiling under
the observed spread reports the load rather than the code, and a check that cries wolf stops
being run. **The census arm is the one to trust for a regression**, and it is also the one the
one-inventory change actually cost.

**The `budget` fields in the JSON are the authority**: `--check` reads its ceiling from there --
a workload's own if it has one, the file's default otherwise -- so editing the policy changes
what is enforced. `--budget` on the command line overrides both for a one-off question and
defaults to not overriding.

## Running it

```
uv run python tools/benchmark_recognition.py --implementation package --workload census \
    --iterations 3 --check docs/benchmarks/recognition-budget.json
```

Exits non-zero when the measured minimum is over the ceiling, and prints both numbers either
way.

Peak RSS is reported but not checked. `getrusage` reports kibibytes on Linux and bytes on
macOS, so the macOS reading is converted to match the field name; Windows has no `resource`
module and the field comes back null there rather than wrong. The seconds are what the
budget is about.

**Not run in CI, deliberately.** A wall-clock assertion on a shared runner fails for reasons
that have nothing to do with the code, and a test that fails for unrelated reasons stops being
read. This is a tool to run when a change is expected to cost something, and a number to update
when it legitimately does — with the reason recorded in the commit that moves it.

The baseline is tied to the machine it was taken on. Re-measure both workloads on any other
box before comparing against it; the *ratio* between two arms measured back to back on the same
box is the portable part, not the seconds.

## Issue #173 post-consolidation A/B

Measured on the same shared development host, alternating the pre-epic baseline `ccf3b8c` and
post-epic `d73f612` processes. Two five-sample composite runs crossed directions: current was
3.5% faster by minimum in one pair (2.628 s versus 2.725 s) and 1.8% slower in the other
(2.938 s versus 2.887 s). That is host noise, not a reproducible regression.

The trustworthy census arm was also alternated. Current was faster in the first pair
(133.253 s versus 152.556 s) and effectively tied in the second (146.100 s versus 146.137 s).
No budget or implementation change is justified by these measurements.
