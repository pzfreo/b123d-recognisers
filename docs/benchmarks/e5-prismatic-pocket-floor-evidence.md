# E5 Prismatic Pocket floor evidence

Issue [#403](https://github.com/pzfreo/b123d-recognisers/issues/403) retains the exact cap nodes
already selected by the neutral ring proof and publishes them as `PrismaticPocket` constituent
evidence. It does not change records, defining evidence, claims, reconciliation or recognition.

## Contract and implementation

`Ring.cap_nodes` replaces the private boolean-only cap result. Its `caps` property preserves the
same boolean decision consumed by Passage and Prismatic Pocket filtering. The existing bounded
end-neighbour walk now retains every graph node that made that decision true; it performs no new
topology traversal, coordinate match or corpus-labelled selection.

An accepted Prismatic Pocket still defines and claims only its wall ring. Its constituent set is
the ring plus the selected closed-end cap patches. Through rings and both-capped cavities still
produce no Prismatic Pocket candidate. This is the ADR 0010 distinction between ownership and
physical membership, applied at the original decision site.

Authored triangle, rectangle and hexagon fixtures prove the wider set; mirrored and principal-axis
variants exercise both cap ends; existing through, both-capped, blended-floor, traversal, STEP,
compound and foreign-graph cases retain their acceptance/refusal behavior. The public evidence
test resolves four faces for a triangular pocket while defining evidence remains its three walls.

## MFCAD++-500 result

The immutable format-3 report is
[`effectiveness-mfcadpp-500-prismatic-floor-a61888a.json`](effectiveness-mfcadpp-500-prismatic-floor-a61888a.json).
It was regenerated at implementation commit `a61888a` with taxonomy v8 and the fixed lexical
selection:

```console
uv run python tools/run_effectiveness_baseline.py mfcadpp \
  /path/to/MFCAD++_dataset/step/test \
  --dataset-version "MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823" \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v8.json \
  --limit 500 \
  --output docs/benchmarks/effectiveness-mfcadpp-500-prismatic-floor-a61888a.json
```

All 500 models load and evaluate; invalid and empty counts remain zero. Compared with the
behavior-identical audit-only main baseline, exactly 200 models gain 284 covered labelled faces:

| Dataset class | Before | After | Delta |
| --- | ---: | ---: | ---: |
| 13 Triangular pocket | 515/732 (70.36%) | 664/732 (90.71%) | +149 |
| 14 Rectangular pocket | 659/907 (72.66%) | 670/907 (73.87%) | +11 |
| 15 Six-sided pocket | 860/1,133 (75.90%) | 980/1,133 (86.50%) | +120 |
| 16 Circular-end pocket | 664/973 (68.24%) | 667/973 (68.55%) | +3 |
| 4 Six-sided passage | 662/1,336 (49.55%) | 663/1,336 (49.63%) | +1 |
| **Supported/partial total** | **8,085/11,244 (71.91%)** | **8,369/11,244 (74.43%)** | **+284 / +2.53 points** |
| **All statuses** | **8,841/15,170 (58.28%)** | **9,125/15,170 (60.15%)** | **+284 / +1.87 points** |

The class-4 and class-16 increments are honest overlapping-label effects: the recogniser retains
cap geometry without consulting taxonomy. They are reported rather than suppressed.

After removing commit/timestamp/runtime and coverage fields, every model row and summary field is
exactly equal: physical records, defining precision/recall, mapped counts, reconciliation drops,
diagnostics and taxonomy mismatches do not move. A second exact regeneration after rebasing is
identical to the first after normalising only commit and runtime metadata.

## Runtime and compatibility

Immediate same-host raw runs measured 315.45 seconds for the unchanged baseline and 331.22 seconds
for this commit, a 1.050x ratio; medians were 0.596 and 0.615 seconds. The implementation adds set
retention inside an already-required neighbour loop and no kernel query or second scan. The ratio
is recorded as a conservative observed bound rather than attributed CPU cost.

No public record, signature, manifest schema or serialised value changes. The existing public
`RecognitionEvidence.constituent_faces()` operation returns a wider set for accepted Prismatic
Pockets under its already-versioned non-owning membership contract. MFInstSeg was not used or
inspected and remains reserved for the aggregate milestone.
