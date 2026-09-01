# E2 Plate maximum-thickness covariance

Issue [#383](https://github.com/pzfreo/b123d-recognisers/issues/383) fixes a
presentation-dependent Plate at the strict `max_thick_frac` boundary. The same stepped solid,
prepared before and after an arbitrary rigid transform, previously gained a local-Z Plate only in
the moved presentation. That false Plate changed downstream family ownership in Draftwright even
though the physical FaceLevel geometry was invariant.

## Geometric authority

`max_thick_frac` is a dimensionless strict ceiling. A Plate thickness must be meaningfully below
`max_thick_frac * body_extent`; an exact tie and insignificant reconstruction noise around it are
refused. Both the early eligibility filter and final proposal gate use the existing
`clears_threshold(maximum_thickness, thickness)` authority. The absolute `_TOL` remains the
separate minimum-evidence threshold.

The authored regression constructs the reported stepped solid and an arbitrary translated and
rotated presentation. Both successful ORTHOGONAL preparations now return the same sole Plate axis
and bounds, bounded-equal public placement coordinates, equal ThroughSteps and bounded-equal
FaceLevel geometry. Existing direct boundary tests retain a meaningfully thinner Plate and refuse
the exact and thicker cases.

## Exact MFCAD++-500 comparison

The parent and implementation runs used the published MFCAD++ test split, lexical first 500 unique
model IDs, framed recognition, taxonomy v2 SHA-256
`67f092a2aa8d08be94e9be409c1fb338350626c7f4d1398c2f78be3123977f3b`, and selected-ID SHA-256
`323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`.

The parent report names PR #404 head `a55e659`; its tree is byte-identical to merge commit
`62d6221`. The implementation report names `a0ef49d`. After deleting only package commit and
per-model/aggregate runtime fields, the complete reports are byte-equal: every model status,
record count, defining-face score, constituent-face score, diagnostic and reconciliation field is
unchanged.

| measure | parent | implementation | delta |
| --- | ---: | ---: | ---: |
| loaded / evaluated / invalid / empty | 500 / 500 / 0 / 0 | 500 / 500 / 0 / 0 | 0 |
| Plate records | 234 | 234 | 0 |
| supported/partial face coverage | 8,243/11,322 | 8,243/11,322 | 0 |
| supported/partial defining matches | 5,338/11,322 | 5,338/11,322 | 0 |
| taxonomy-mismatch defining faces | 3,102 | 3,102 | 0 |
| median runtime | 0.6793 s | 0.6654 s | -0.0139 s |
| p95 runtime | 1.3293 s | 1.2553 s | -0.0740 s |
| corpus runtime | 363.79 s | 351.36 s | -12.43 s |

Reports:

- [`effectiveness-mfcadpp-500-plate-tie-parent-a55e659.json`](effectiveness-mfcadpp-500-plate-tie-parent-a55e659.json),
  SHA-256 `b7cd0541a46075575ae49ed55775f68c4aa80d06b6ba8a8df8ba4ce0314627b0`.
- [`effectiveness-mfcadpp-500-plate-tie-a0ef49d.json`](effectiveness-mfcadpp-500-plate-tie-a0ef49d.json),
  SHA-256 `a6f189862ff628f137e969aa9b85e642eea19106f83e1c5f437ecda8ff77f6a6`.

The corpus has no Plate exactly on this boundary, so a neutral corpus result is expected. The
behavioral evidence is the exact downstream reproduction rather than a benchmark score movement.

## Evidence-integrity note

The fresh paired reports do not reproduce the aggregate face scores in the historical PR #404
artifact, despite an identical production/scorer tree and matching recorded hashes. Issue
[#405](https://github.com/pzfreo/b123d-recognisers/issues/405) records the cause: the runner loads
taxonomy before a long run but records its file hash and git commit only at the end, allowing a
mid-run worktree update to pair old in-memory authority with new provenance metadata. That
historical artifact remains immutable but is not used as this child's parent. The stable
same-host pair above is the authority for #383.

## Verification

Focused Plate, framed, scale and threshold tests passed before the final rebase. The complete fast
tier was rerun at the final tree. Ruff and mypy were clean. One independent contract review found
that the initial regression omitted public Plate `u`/`v`; the final test covers those values with
the same bounded kernel-noise policy as FaceLevel. Its narrow re-review was clean. A second focused
adversarial review was warranted because this changes an acceptance boundary; exact tie,
just-inside/outside, scale, axis/sign, early/final parity, NaN and infinity behavior were clean.

Final-diff review against ADRs 0001, 0002, 0003, 0004, 0008 and 0011 confirms that the change keeps
consumer policy downstream, preserves immutable records and one aggregate authority, changes no
face ownership or reconciliation, uses the established dimensional policy, and fixes the explicit
framed route without reordering its representative.

MFInstSeg was not inspected. Its aggregate transfer mount remains unavailable and is tracked by
#293.

## Reproduction

```bash
uv run python tools/run_effectiveness_baseline.py mfcadpp \
  /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version "MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823" \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v2.json \
  --limit 500 --recognition-frame framed --output REPORT.json
```
