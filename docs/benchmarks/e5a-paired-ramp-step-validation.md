# E5a paired-ramp side-step validation

This is development evidence for issue #297, not blind transfer evidence. MFCAD++ was inspected
and used to shape the deterministic predicate. MFInstSeg remains the separately tracked baseline
transfer dataset and was unavailable in this workspace.

## Reproduction

The final canonical report was produced from implementation commit `e813c99`:

```bash
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --limit 500 \
  --dataset-version \
  'MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823' \
  --output docs/benchmarks/effectiveness-mfcadpp-500-e5a-e813c99.json
```

Selection is the same first 500 unique model IDs in lexical order as the E0 report. The report
contains the exact selection hash, source hashes, environment, per-model rows and runtime data.

## Result

- 500 loaded and evaluated; zero invalid and zero empty inventories.
- 49 accepted `PairedRampStep` records across 46 models.
- 144 of 147 defining-face occurrences are MFCAD++ class 9 (`2-sided through step`): 97.96%
  defining-face precision on this development selection.
- The one occurrence landing outside class 9 is `11251.step`, with labels `(4, 24, 24)` (one
  six-sided-passage face and two Stock faces). It has the same proved ramp/terminal geometry; this
  model is the existing documented example of single-assignment labels splitting one physical
  passage boundary, so comparison data does not delete it.
- 144 of 592 class-9 faces are defining evidence: 24.32% face recall.
- MFCAD++ provides no native instance relation. Reapplying the issue's deterministic connected
  same-label face-component derivation gives 171 class-9 components, of which 48 are touched by a
  class-9 defining set: 28.07% derived component recall. This is explicitly not a native-instance
  metric and is not written into the format-1 report's `instance_recall` field.
- Removing the new family, class-9 taxonomy row, runtime and derived mismatch counters makes every
  per-model row identical to E0. Existing physical-family output is unchanged.
- Plate records remain 234, Chamfer 87 and Raised Pad 2 before and after. Exact evidence overlap is
  limited to seven closing terminals also used by Plate and one also used by Raised Pad; no ramp
  face overlaps another family. Those structural records describe their bodies and issue #297
  explicitly forbids suppressing a whole record merely because it shares the closing terminal, so
  no reconciliation rule is added. Total taxonomy-mismatch defining faces move from 922 to 961,
  including the newly supported class-9 accounting and the one mixed-label occurrence above.

The supported subset is intentionally narrow: principal-axis mirror pairs with an original linear
shared ridge, one convex solid-envelope opening, and one concave unsmoothed three- or five-sided
terminal. Rigid X/Y/Z permutations remain the same record; corpus taxonomy cannot make identical
geometry orientation-dependent. Asymmetric pairs, seven-sided/subdivided terminals and the
remaining rectangular/slanted through-step classes stay open roadmap scope.

The concrete downstream projection is a paired-ramp dimension at the original shared-ridge
anchor: `2 × angle`, plus `length` along `axis`. The authored contract test constructs that exact
consumer value, so the outcome is not merely a family count.

Runtime is recorded as median 0.470 s/model and p95 0.965 s/model for the complete inventory. The
historical E0 run recorded 0.453 s and 0.923 s respectively: +17 ms median and +42 ms p95. The runs
were not interleaved and host load was uncontrolled, so this is descriptive rather than a causal
cost estimate; it is nevertheless reported as a modest observed increase, not called a speedup or
silently rounded away.
