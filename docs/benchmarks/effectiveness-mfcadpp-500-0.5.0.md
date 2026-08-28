# MFCAD++ effectiveness baseline: 0.5.0 development series

This is the first frozen development baseline for Epic 0005 E0. The canonical evidence is
[`effectiveness-mfcadpp-500-0.5.0.json`](effectiveness-mfcadpp-500-0.5.0.json); metric definitions
and limitations are in the [baseline method](effectiveness-baseline-method.md).

## Provenance

- Package version: `0.5.0.dev0`
- Scorer commit: `475f4eb84b1ae531210ed129e45d3e3df81c5e5d`
- Corpus: first 500 unique IDs in lexical order from the published MFCAD++ test split
- Dataset identity: DOI `10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823`
- Selection hash: `323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`
- Result: 500 selected, loaded, and evaluated; no invalid models

The exact command was:

```bash
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version \
  'MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823' \
  --limit 500 \
  --output docs/benchmarks/effectiveness-mfcadpp-500-0.5.0.json
```

## What the evidence says

The strongest supported recall is through holes at `234/239` defining faces (97.9%). The larger
opportunities are class-specific rather than a single architecture score: blind holes are
`177/363` (48.8%), rectangular pockets `385/907` (42.4%), circular-end pockets `423/973`
(43.5%), and O-ring features `211/669` (31.5%). Six-sided pockets are stronger at `828/1133`
(73.1%). Unsupported classes remain zero by design and should not be read as regressions.

The aggregate contains 734 accepted records that cannot be projected onto a supported MFCAD++
class and 922 accepted defining-face occurrences whose supported label maps to another family.
These are useful investigation queues, not automatically false recognitions: MFCAD++ labels each
face once, while one accepted occurrence may own shared or stock-contact faces.

All 500 models contain at least one accepted physical record. This does **not** mean every model's
machining features were recognized: structural `face-levels`, `risers`, and `plates` count as
physical records. Per-class recall and unmapped records are the meaningful omission signals.

Recognition runtime for the corpus had a 0.453 s median and 0.923 s p95 per model, with 242.139 s
total. These are descriptive values from the shared development host, not a performance budget.

## Separate validation arms

Run on the same checkout after capture:

- Semantic golden parity: 21 passed in 39.87 s.
- Vendored NIST and turned real parts: 23 passed in 207.66 s.
- Composite performance: minimum 4.079 s across five iterations; over the historical 2.698 s
  ceiling.
- Census performance: minimum 185.182 s across three iterations; over the historical 109.651 s
  ceiling.

The two timing failures are recorded rather than waived. This increment adds offline scoring,
tests, and documentation and does not change production recognition. The historical budget was
measured at another commit on a shared host, so these results establish that a controlled
same-host A/B or a new environment baseline is needed; they do not attribute the difference to
E0.

## Transfer evidence still required

MFInstSeg is not mounted in this workspace and is distributed through authenticated sources. No
substitute or inspected development corpus is presented as blind evidence. The frozen adapter,
partition checks, and command are ready in the baseline method; the MFInstSeg report remains the
external prerequisite before E0 can be closed.
