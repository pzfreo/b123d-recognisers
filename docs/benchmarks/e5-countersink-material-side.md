# E5 CounterSink material-side validation

- **Issue:** #303
- **Parent main:** `96d981e2100fb3f5f650299b32d82d17ad7f82b6`
- **Implementation source:** `f53392f4bf1c831103c383c9d622bb739e7dc64e`
- **Dataset:** published MFCAD++ test split, canonical lexical first 500 unique model IDs
- **Selection SHA-256:** `323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`
- **Taxonomy:** v8, SHA-256 `ef8ec7e88b0f72acdce5f7c11470af9b62c0aee5e550c0d1208fe33ecb69eb0f`
- **Recognition frame:** raw

## Geometry decision

A CounterSink cone bounds a void: its outward-from-material face normal points radially toward
the analytic cone axis. The same normal points away from the axis on an external stepped-shaft
transition. CounterSink discovery applies that sign predicate locally before publication; it is
invariant under rigid transforms and uniform positive scale and does not depend on a Hole result,
world axis, body order, size threshold, corpus label, or consumer policy.

The exact Draftwright reproducer changes from one direct and aggregate CounterSink to none while
still producing no Hole. Authored controls retain internal seats along principal and arbitrary
axes, flipped mouths, blind and through bores, both seats of a two-sided through bore, separate
valid solids, traversal variants, uniform scale, mirroring, and STEP round trips. The remaining
DIN 332 centre-drill ambiguity is unchanged and documented.

## MFCAD++ transfer evidence

The parent comparison is
`effectiveness-mfcadpp-500-double-d-22bf3e6.json`; the implementation report is
`effectiveness-mfcadpp-500-countersink-f53392f.json`.

MFCAD++ has no distinct countersink class. Current taxonomy v8 therefore maps CounterSink records
to its Chamfer class, so corpus labels cannot authorize this semantic boundary. The corpus is a
regression/transfer check only. All 500 models loaded and evaluated. All eight existing
CounterSink records across six models remain accepted; the corpus contains no occurrence of the
authored external stepped-shaft defect.

After removing `.runtime`, `.package.commit`, and each `.models[].seconds`, parent and
implementation reports are byte-identical with normalized SHA-256
`5fa6f2448a018731d1496a93a540d14b00849f5909a5047294edcf87ae193ab9`.
The implementation report SHA-256 is
`999fc7071977bae6dcb699d4c2e0d72dedb018a65a139e976e04011c0e4ec25b`.

Standalone runtime remains neutral within run noise:

| Metric | Parent | Implementation | Ratio |
| --- | ---: | ---: | ---: |
| total | 343.629 s | 344.023 s | 1.0011x |
| median/model | 0.6400 s | 0.6381 s | 0.9970x |
| p95/model | 1.2538 s | 1.2208 s | 0.9736x |

## Validation and review

- Full fast tier: 2,554 passed, 391 slow deselected.
- Focused CounterSink, Hole, and reader-roster suite after review fix: 112 passed.
- Ruff and the configured full mypy run are clean.
- Applicable ADRs reviewed before implementation and against the final diff: 0002, 0003,
  0004, 0007, 0008, 0009, and 0012. ADRs 0007 and 0009 record the local material-side gate.
- One bounded independent review found no geometry or API defect. Its evidence blocker is resolved
  by the paired report and this note; its two stale documentation findings were fixed and narrowly
  revalidated. The optional duplicate scale-negative test was not added because covariance follows
  directly from the sign predicate and the existing suite already tests scaled internal seats.
