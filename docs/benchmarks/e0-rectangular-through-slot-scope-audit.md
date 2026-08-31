# E0 rectangular through-slot scope audit

Issue [#358](https://github.com/pzfreo/b123d-recognisers/issues/358) audits the historical mapping
from MFCAD++/MFInstSeg class 6, `Rectangular through slot`, to the package `Slot` family. The
result is a scope correction, not an effectiveness gain or a production change.

## Why the names are not enough

The package `Slot` is an enclosed through recess established by two opposed walls, with no floor
and no open longitudinal end. `SectionPassage` owns a complete closed section open at both run
ends. `Channel` is a floored rectangular recess open at both longitudinal ends. None represents a
three-wall U-shaped cut entering from one stock edge.

The corpus class uses `Rectangular through slot` for several topologies, dominated by exactly that
open-ended U motif. Treating the shared English word “slot” as a geometric equivalence made the
entire class look supported and turned both legitimate refusals and occasional nearby readings
into misleading precision/recall figures.

## Complete lexical-500 audit

The same published test archive and exact lexical selection used by the preceding Slot reports
contains 50 models / 237 class-6 faces. Connected components are formed only through exact B-Rep
edge adjacency between faces carrying label 6. All 67 components were inspected:

| component geometry | count | current contract |
| --- | ---: | --- |
| Three principal planes: one opposed pair plus one perpendicular terminal | 45 | U-shaped edge slot; outside `Slot`, `SectionPassage`, and `Channel` |
| Four internally oblique planes forming a closed ring | 4 | overlaps the free-axis schema gap in #310; not expressible by the current axis-letter `Slot` |
| Four principal planes forming a closed ring | 3 | a supported narrow closed-section subset, but not representative of the mixed corpus class |
| Intersected, split, or label-union components | 15 | cannot be assigned to instances from MFCAD++ single-face labels alone |

The audit therefore does not pretend the class is uniformly absent. It proves the opposite: the
single class mixes a small supported closed subset, a free-axis subset, a dominant unsupported
edge-slot geometry and intersection fragments. Taxonomy v4 therefore adds a `partial` state: it
retains the legitimate `Slot` matches and full denominator while qualifying that unmatched faces
do not all belong to the mapped family contract.

As descriptive observations only, 17/50 labelled models emit any aggregate `Slot`, and 13/50 have
at least one matched class-6 defining face under taxonomy v3. These are not instance-recall figures:
MFCAD++ supplies no instance relation, and one model may contain multiple connected components or
intersections. No individual MFInstSeg geometry was inspected.

## Immutable taxonomy result

[`effectiveness-taxonomy-v4.json`](effectiveness-taxonomy-v4.json), SHA-256
`b5bd44072b64563926fea65a00587adbfbd0e71316c86656b680a161743f784b`, differs from v3 only at
class 6 status: `slots` remains mapped and `supported` becomes `partial`. Earlier versions and
reports remain immutable. The scorer treats partial mappings as measurable for matched evidence,
record projection and mismatch accounting; the status qualifies interpretation rather than
erasing genuine support. This does not decide whether an explicit rectangular edge-slot family
would be valuable, and it does not close #310's independently reproduced Draftwright need for an
enclosed free-axis Slot.

The exact v4 report is
[`effectiveness-mfcadpp-500-class6-scope-8faa759.json`](effectiveness-mfcadpp-500-class6-scope-8faa759.json),
SHA-256 `b1f20ac6c6fa9c1ecf0ddf8c0eb072540a80d7dcfc43e9d16ff6dd30708e3480`, generated at the
scorer/taxonomy commit named in its filename using:

```bash
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version published-test-split \
  --limit 500 \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v4.json \
  --output docs/benchmarks/effectiveness-mfcadpp-500-class6-scope-8faa759.json
```

Compared with the v3 report at `a8b5cdf`:

- all physical records, predicate observations, reconciliation drops, unsupported diagnostics,
  source hashes and non-mapping, non-runtime per-model fields are exactly equal;
- `Slot` remains 45 accepted records;
- class 6 retains 31/88 precision, 31/237 recall, 16 mapped records, and 3,237 total taxonomy
  mismatches, while its status changes from `supported` to `partial`;
- total runtime is 251.121 seconds versus 256.000 seconds (ratio 0.9809), descriptive only because
  production behavior is unchanged.

MFInstSeg inherits the same 25-class mapping. Its earlier rounded Slot summary combines class 6
and class 7 under the now-rejected taxonomy, so it must be regenerated from the canonical model
rows under v4. Exact corrected values cannot be reconstructed from the prose summary.
