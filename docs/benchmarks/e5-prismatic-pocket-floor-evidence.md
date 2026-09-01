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

The original immutable format-3 report
[`effectiveness-mfcadpp-500-prismatic-floor-a61888a.json`](effectiveness-mfcadpp-500-prismatic-floor-a61888a.json)
is retained, but its inventory is not reproducible from its recorded production source. Its
taxonomy-v8 hash and class statuses are internally consistent; the discrepancy is not an axis or
taxonomy-revision difference. An exact replay whose `src/` tree equals `a61888a` produces different
records and scores. The old runner could observe a worktree transition during a long run while
recording only its final commit, so the historical +284 claim is not comparison authority.

The corrected comparison uses two immutable reports produced by the #405 source-pinned runner:

- [`effectiveness-mfcadpp-500-prismatic-floor-parent-39d7028.json`](effectiveness-mfcadpp-500-prismatic-floor-parent-39d7028.json)
  is current main with only the two #403 production edits removed;
- [`effectiveness-mfcadpp-500-prismatic-floor-corrected-8dde6f5.json`](effectiveness-mfcadpp-500-prismatic-floor-corrected-8dde6f5.json)
  is the matching current-source implementation report.

The two report commits differ in production code only in `_rings.py` and
`prismatic_pockets.py`, the #403 implementation. A separate audit commit whose `src/` tree exactly
equals historical implementation commit `a61888a` produces the same normalized model evidence as
the current-source implementation report; it is retained as reproducibility evidence rather than
used as the parent/child comparison.

Both use taxonomy v8 and the same fixed lexical selection:

```console
uv run python tools/run_effectiveness_baseline.py mfcadpp \
  /path/to/MFCAD++_dataset/step/test \
  --dataset-version "MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823" \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v8.json \
  --limit 500 \
  --output /tmp/source-pinned-report.json
```

All 500 models load and evaluate; invalid and empty counts remain zero. Compared with the
production parent, exactly 205 models gain 295 covered labelled faces:

| Dataset class | Before | After | Delta |
| --- | ---: | ---: | ---: |
| 13 Triangular pocket | 489/732 (66.80%) | 642/732 (87.70%) | +153 |
| 14 Rectangular pocket | 654/907 (72.11%) | 665/907 (73.32%) | +11 |
| 15 Six-sided pocket | 845/1,133 (74.58%) | 972/1,133 (85.79%) | +127 |
| 16 Circular-end pocket | 637/973 (65.47%) | 640/973 (65.78%) | +3 |
| 4 Six-sided passage | 659/1,336 (49.33%) | 660/1,336 (49.40%) | +1 |
| **Supported/partial total** | **7,940/11,244 (70.62%)** | **8,235/11,244 (73.24%)** | **+295 / +2.62 points** |
| **All statuses** | **8,732/15,170 (57.56%)** | **9,027/15,170 (59.51%)** | **+295 / +1.94 points** |

The class-4 and class-16 increments are honest overlapping-label effects: the recogniser retains
cap geometry without consulting taxonomy. They are reported rather than suppressed.

After removing commit/runtime and coverage fields, every model row and summary field is exactly
equal: physical records, defining precision/recall, mapped counts, reconciliation drops,
diagnostics and taxonomy mismatches do not move. The implementation report is also normalized-equal
to an independent fresh taxonomy-v8 run on current source, which separately checks stable import
pairing and recogniser inventory.

## Runtime and compatibility

The final-runner same-host runs measured 309.11 seconds for the production parent and 311.61
seconds for the implementation, a 1.008x raw ratio; medians were 0.586 seconds for both. The implementation adds set
retention inside an already-required neighbour loop and no kernel query or second scan. The ratio
is recorded as a conservative observed bound rather than attributed CPU cost.

No public record, signature, manifest schema or serialised value changes. The existing public
`RecognitionEvidence.constituent_faces()` operation returns a wider set for accepted Prismatic
Pockets under its already-versioned non-owning membership contract. MFInstSeg was not used or
inspected and remains reserved for the aggregate milestone.
