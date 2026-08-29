# E2 Angled Step frame-axis audit

Issue [#322](https://github.com/pzfreo/b123d-recognisers/issues/322) asked whether four
raw-to-framed Angled Step losses exposed a signed principal-axis covariance defect. They do not.
The existing recogniser is covariant over its documented X/Y/Z domain; both affected corpus models
place the raw-world feature geometry obliquely inside the independently inferred part frame.

## Evidence identity

- Corpus: MFCAD++ published test split, DOI
  [`10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823`](https://doi.org/10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823).
- Selection: first 500 STEP model IDs, lexical ascending; selected-ID SHA-256
  `323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`.
- Historical machine report:
  [`frame-corpus-500-production.json`](frame-corpus-500-production.json), artifact SHA-256
  `ba75a0f5272c0a0dea536abf92874e579cba47977ad4b809c8c866090a21d6ef`, introduced by
  commit `aa372d09360493e11a10fa53e2786aced7e248a1`.
- Current confirmation: issue branch commit `b82291b2226a51e1a7e474bd655b33993533020f`.

The report records four absent Angled Step occurrences and no introductions or
reclassifications. All four occur in only two models:

| Model | Raw Angled Steps | Framed Angled Steps | Frame deviation from world principal planes |
| --- | ---: | ---: | ---: |
| `10492.step` | 1 | 0 | 9.522181° |
| `10649.step` | 3 | 0 | 17.439433° |

`10492` retains a world-X run, but its two cross-section/support directions are rotated 9.52°
inside the inferred frame. `10649` likewise mixes world-principal feature planes with a part frame
rotated 17.44° in its XY plane. These are features oblique inside otherwise framed parts, which
ADR 0011 and E2 explicitly exclude; a signed permutation of a supported principal feature is not
what changed.

## Corpus-independent contract proof

The authored stopped-wedge fixture now exercises the same physical Angled Step with runs along
local X, Y and Z, both signs, plus translation. Every case returns one record with the same 4 mm
legs, 45° angle and 25 mm run length; only its local axis and coordinates change. The aggregate
retains the step and reconciles away the competing Chamfer proposal. A principal-Y STEP export and
re-import retains the same record. The focused module has 24 passing tests.

No production predicate, tolerance, record, provenance or reconciliation rule changes. Existing
near misses continue to cover the through chamfer, concave recess wall, compound corner, missing or
non-triangular terminal and split-terminal boundary. Runtime and MFCAD++ accepted output are
therefore byte-for-byte unchanged; rerunning a 500-model score vector cannot add evidence beyond
the exact no-production diff and the matched current two-model confirmation.

## Decision

Close #322 with no recogniser implementation. Principal-axis covariance is now an explicit tested
contract. Internally oblique Angled Steps remain unsupported and must not be admitted by weakening
the shared bevel alignment gate. MFInstSeg was not available and was not inspected; this child is
not a transfer milestone.

ADR conformance: ADR 0002 determinism and aggregate/direct parity are strengthened; ADR 0003's
Angled Step/Chamfer reconciliation is exercised unchanged; ADR 0008 gains no tolerance; ADR 0009
gains no shared filter; and ADR 0011's distinction between whole-part framing and internally
oblique feature support is preserved.
