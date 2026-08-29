# E5a paired-ramp side-step validation

This is development evidence for issue #297, not blind transfer evidence. MFCAD++ was inspected
and used to shape the deterministic predicate. MFInstSeg remains the separately tracked baseline
transfer dataset and was unavailable in this workspace.

## Reproduction

The final canonical report was produced from implementation commit `67395b6`:

```bash
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --limit 500 \
  --dataset-version \
  'MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823' \
  --output docs/benchmarks/effectiveness-mfcadpp-500-e5a-67395b6.json
```

Selection is the same first 500 unique model IDs in lexical order as the E0 report. The report
contains the exact selection hash, source hashes, environment, per-model rows and runtime data.

## Result

- 500 loaded and evaluated; zero invalid and zero empty inventories.
- 21 accepted `PairedRampStep` records across 21 models.
- All 63 defining-face occurrences are MFCAD++ class 9 (`2-sided through step`): 100% defining-face
  precision on this development selection. There are no off-class defining labels.
- 63 of 592 class-9 faces are defining evidence: 10.64% face recall.
- MFCAD++ provides no native instance relation. Reapplying the issue's deterministic connected
  same-label face-component derivation gives 171 class-9 components, of which 21 are touched by a
  class-9 defining set: 12.28% derived component recall. This is explicitly not a native-instance
  metric and is not written into the format-1 report's `instance_recall` field.
- Removing the new family, class-9 taxonomy row, runtime and derived mismatch counters makes every
  per-model row identical to E0. Existing physical-family output is unchanged.
- Plate records remain 234, Chamfer 87 and Raised Pad 2 before and after. Exact evidence overlap is
  limited to three closing terminals also used by Plate; there is no Raised Pad overlap and no
  ramp face overlaps another family. Those structural records describe their bodies and issue #297
  explicitly forbids suppressing a whole record merely because it shares the closing terminal, so
  no reconciliation rule is added. Total taxonomy-mismatch defining faces move from 922 to 960,
  including the newly supported class-9 accounting.

The supported subset is intentionally narrow: principal-axis mirror pairs with an original linear
shared ridge, one convex solid-envelope opening, and one concave unsmoothed three- or five-sided
terminal. A cut along the solid's unique thickness direction is refused as a top-opening
triangular pocket; this stock-relative rule remains invariant under rigid X/Y/Z permutations.
That explicit precision boundary reduced development recall from the earlier 24.32% prototype to
10.64%, rather than freezing a known authored-pocket false positive. Asymmetric pairs,
seven-sided/subdivided terminals and the remaining rectangular/slanted through-step classes stay
open roadmap scope.

The concrete downstream projection is a paired-ramp dimension at the original shared-ridge
anchor: `2 × angle`, plus `length` along `axis`. The authored contract test constructs that exact
consumer value, so the outcome is not merely a family count.

Runtime is recorded as median 0.407 s/model and p95 0.808 s/model for the complete inventory. The
historical E0 run recorded 0.453 s and 0.923 s respectively. The runs were not interleaved and host
load was uncontrolled, so the lower observation is descriptive rather than claimed as a speedup.
