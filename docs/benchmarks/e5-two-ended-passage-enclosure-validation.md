# E5 — two-ended Passage enclosure validation

Issue #

Issue #Why

IssueThisEnded Passage detection required every planar wall to form one equal-span cycle. Feature
intersections can shorten or split a wall while leaving an unamb through-passage with an unchanged
polygonal mouth at each end. Issue #The reference comparison identifies passages as 9,186 of the
remaining in-scope face gap, led by six-sided passages.

IssueState

WHY This validation is pinned to implementation commit `40eeac48dc052b1ae4759816f2c9db8df4f29d02`.
MFCAD++ labels are evaluation evidence only and never participate in proposal construction.

## Rule

The existing complete equal-span wall cycle remains preferred. The fallback requires:

- exactly two complete inner-wire mouths whose transitions to their wall seeds are all convex;
- opposed planar opening faces and at least three original planar wall seeds per mouth;
- congruent straight-edged polygonal mouth sections;
- one concave-or-smooth enclosure region on one valid solid; and
- the existing empty-prism and open-at-both-ends material proof.

Mouth-adjacent planar walls are defining evidence. The exact traversed region is constituent
membership. Opening stock faces remain consulted context. Blind, circular, branched/multi-mouth,
cross-solid, curved-mouth and materially obstructed cavities fail closed.

Authored tests cover interrupted triangular, rectangular and six-sided passages, arbitrary rigid
transforms, equal occurrences on separate solids, exact Candidate constituent publication, and
blind/circular/branched negatives. They also disable the fallback to prove the historical cycle
cannot recover those positives.

## Label-blind topology audit

Across all 2,500 lexical MFCAD++ test models, the unrestricted two-mouth enclosure substrate finds
3,038 regions and reaches 10,535/14,257 passage faces (73.89%), including 4,956/6,663 six-sided
faces. It reaches zero faces from pocket classes 13–16. Its raw face purity is 91.21% because 770
regions are circular through-bores and intersecting features may contribute non-passage faces.
The production planar-polygonal and matching-section gates exclude the circular family and bound
publication more tightly than this diagnostic ceiling.

Machine evidence:
[`mfcadpp-two-ended-enclosure-audit-40eeac4.json`](mfcadpp-two-ended-enclosure-audit-40eeac4.json),
SHA-256 `c1a720c9d59b4bf7f9c9ef78dea8b1f23475c0932226c19b21e2beaeb141cb13`.

## Production effectiveness

The full taxonomy-v10 run evaluates 2,493 valid models and records the seven known invalid models
under the same explicit `--allow-invalid` policy as prior full reports. Against
[`effectiveness-mfcadpp-2500-toroidal-blends-6d449d2.json`](effectiveness-mfcadpp-2500-toroidal-blends-6d449d2.json),
whose Passage source is byte-identical to the parent of this change:

| Measure | Parent | Two-mouth | Change |
| --- | ---: | ---: | ---: |
| physical Passage records | 1,426 | 1,580 | +154 |
| triangular mapped records | 507 | 625 | +118 |
| rectangular mapped records | 456 | 471 | +15 |
| six-sided mapped records | 480 | 503 | +23 |
| triangular face coverage | 0.5823 | 0.6822 | +0.0999 |
| rectangular face coverage | 0.7476 | 0.7576 | +0.0100 |
| six-sided face coverage | 0.4956 | 0.5172 | +0.0217 |
| unmapped records, all families | 14,707 | 14,707 | 0 |

The safe rule therefore validates Direction 01 and materially improves Passage detection, but its
largest immediate benefit is triangular rather than six-sided. The broader audit ceiling must not
be reported as production recall.

Machine evidence:
[`effectiveness-mfcadpp-2500-passage-enclosure-40eeac4.json`](effectiveness-mfcadpp-2500-passage-enclosure-40eeac4.json),
SHA-256 `c040c85125d5e98131d462f64f38b4c287ab200a611c3b8ee8f1cdc65f60315e`.

Generate the reports with:

```console
uv run python tools/audit_mfcadpp_two_ended_enclosures.py \
  /path/to/MFCAD++_dataset/step/test --limit 2500 \
  --output /tmp/mfcadpp-two-ended-enclosure-audit.json

uv run python tools/run_effectiveness_baseline.py mfcadpp \
  /path/to/MFCAD++_dataset/step/test \
  --dataset-version \
  "MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823" \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v10.json \
  --limit 2500 --allow-invalid \
  --output /tmp/effectiveness-mfcadpp-2500-passage-enclosure.json
```
