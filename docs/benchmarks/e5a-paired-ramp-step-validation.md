# E5a paired-ramp side-step validation

This is development evidence for issue #297, not blind transfer evidence. MFCAD++ was inspected
and used to shape the deterministic predicate. MFInstSeg remains the separately tracked baseline
transfer dataset and was unavailable in this workspace.

## Reproduction

The canonical report was produced from implementation commit `72dd9c9`:

```bash
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --limit 500 \
  --dataset-version \
  'MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823' \
  --output docs/benchmarks/effectiveness-mfcadpp-500-e5a-72dd9c9.json
```

Selection is the same first 500 unique model IDs in lexical order as the E0 report. The report
contains the exact selection hash, source hashes, environment, per-model rows and runtime data.

## Result

- 500 loaded and evaluated; zero invalid and zero empty inventories.
- 39 accepted `PairedRampStep` records across 38 models.
- All 78 defining-face occurrences are MFCAD++ class 9 (`2-sided through step`): defining-face
  precision 100% on this development selection.
- 78 of 592 class-9 faces are defining evidence: 13.18% face recall. MFCAD++ has no instance
  relation, so no instance-recall claim is made.
- Removing the new family, class-9 taxonomy row, runtime and derived mismatch counters makes every
  per-model row identical to E0. Existing physical-family output is unchanged.
- An explicit aggregate evidence scan over the 39 occurrences found zero shared defining faces
  with every other physical family, including Chamfer, Plate and Raised Pad. No reconciliation
  rule is therefore added.

The supported subset is intentionally narrow: horizontal mirror pairs with an original linear
shared ridge, one convex solid-envelope opening, and one concave unsmoothed three- or five-sided
terminal. Z-running pairs are top-opening triangular pockets and are rejected. Asymmetric pairs,
seven-sided/subdivided terminals and the remaining rectangular/slanted through-step classes stay
open roadmap scope.

Runtime is recorded as median 0.406 s/model and p95 0.762 s/model for the complete inventory. The
historical E0 run recorded 0.453 s and 0.923 s respectively, but this is not treated as a speedup:
the runs were not interleaved and host load was uncontrolled. The relevant bounded conclusion is
that the full 500-model run completed without a measured regression signal.
