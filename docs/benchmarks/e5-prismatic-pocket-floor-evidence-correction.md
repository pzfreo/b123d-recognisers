# E5 Prismatic Pocket floor evidence correction

Issue [#405](https://github.com/pzfreo/b123d-recognisers/issues/405) found that the original #403
corpus artifact loaded taxonomy/code authority before its long model loop but recorded taxonomy
hash and git commit afterward. A worktree update during that run attached new provenance to old
in-memory authority. The historical artifact remains immutable, but its class statuses disagree
with the mapping at its recorded SHA and it is not used here.

The fixed runner freezes exact taxonomy bytes and commit before import, requires a clean tracked
tree, scores from the captured bytes, and refuses publication if commit, tracked tree or taxonomy
changes before the end. A cross-process asymmetric STEP regression separately proves stable
`ADVANCED_FACE` label-to-imported-face geometry pairing.

## Corrected comparator

Both clean runs retain current main through Plate covariance merge `f314536` and the #405 runner
fix. The audit-parent commit `8eed072` removes only the two #403 production source changes:
`_rings.py` retains boolean cap decisions without cap identities and `prismatic_pockets.py`
publishes defining walls as its default constituent set. Implementation commit `6b47169` retains
the shipped exact cap identities. This isolates constituent evidence without replaying unrelated
history.

Both reports use the published MFCAD++ test split, lexical first 500 unique model IDs, framed
recognition, taxonomy-v2 SHA-256
`67f092a2aa8d08be94e9be409c1fb338350626c7f4d1398c2f78be3123977f3b`, and selected-ID SHA-256
`323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`.

| Dataset class | Parent | Implementation | Delta |
| --- | ---: | ---: | ---: |
| 13 Triangular pocket | 489/732 | 642/732 | +153 |
| 14 Rectangular pocket | 654/907 | 665/907 | +11 |
| 15 Six-sided pocket | 845/1,133 | 972/1,133 | +127 |
| 16 Circular-end pocket | 637/973 | 640/973 | +3 |
| 4 Six-sided passage | 659/1,336 | 660/1,336 | +1 |
| **Supported/partial total** | **7,948/11,322 (70.20%)** | **8,243/11,322 (72.81%)** | **+295 / +2.61 points** |
| **All statuses** | **8,732/15,170 (57.56%)** | **9,027/15,170 (59.51%)** | **+295 / +1.94 points** |

Exactly 205 models gain 295 labelled constituent faces; the largest model-level increment is five.
After removing only coverage and commit/runtime fields, the complete reports are equal: physical
records, defining evidence, mapped records, taxonomy mismatches, reconciliation, diagnostics,
validity and empty-model outcomes do not move.

The implementation run took 354.01 seconds versus 348.92 seconds for the parent (1.015x); medians
were 0.640 and 0.651 seconds, and p95 values 1.296 and 1.314 seconds. The small paired difference is
within run noise and the implementation adds no geometry query.

Reports:

- [`effectiveness-mfcadpp-500-prismatic-floor-parent-8eed072.json`](effectiveness-mfcadpp-500-prismatic-floor-parent-8eed072.json),
  SHA-256 `909a4792fe8818c1240ff0bd7fafe62f94e397a49ad403c7f14252e120d8505d`.
- [`effectiveness-mfcadpp-500-prismatic-floor-corrected-6b47169.json`](effectiveness-mfcadpp-500-prismatic-floor-corrected-6b47169.json),
  SHA-256 `7fd30fc228678d20ac44dd03a3b8af1825c3eace857637245b20e1acd1a98224`.

MFInstSeg was not used or inspected. This correction changes corpus evidence only; the shipped
record, defining ownership, reconciliation and public constituent contract remain those reviewed
and merged in #404.
