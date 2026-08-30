# E2 body-local Plate occurrence validation

Issue [#334](https://github.com/pzfreo/b123d-recognisers/issues/334) makes Plate discovery and
attribution local to each valid solid in an aggregate. It removes cross-solid face grouping,
area averaging and deduplication while retaining the existing one-solid geometry contract and one
aggregate family invocation.

## Evidence identity

- Behavior commit: `c55cbbfa44056f950ed6f7c19aeb4956f0681a9c`; benchmark transition and
  architecture-roster commits: `3f2409e225cf74091e59f040682a7bd3c01b07b4` and
  `23fde591ad9812a7468ee021c262a9726f499913`.
- MFCAD++ corpus: published test split, DOI
  [`10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823`](https://doi.org/10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823).
- [MFCAD++-500 paired report](plate-body-locality-performance-mfcadpp-500-23fde59.json), SHA-256
  `cbc2512595bd47171945da5b88057dbba108e578191082fbacc1b1f60399bfe3`.
- [NIST/Gramel census paired report](plate-body-locality-performance-census-23fde59.json), SHA-256
  `7fe1ea2c43202b828d04951b872699d9ce7f4144a4ddc1d837cfa6992f76edd2`.

MFCAD++ is direct development evidence. No MFInstSeg tree exists at the supplied
`/app/workspaces-codex/datasets/mfinstseg` path or the other checked `/app` dataset mounts in this
runtime. This increment therefore makes no independent transfer claim and substitutes no other
dataset.

## Geometry, ownership and refusal proof

The exact consumer reproduction contains two independently valid T-brackets at `u=-70` and
`u=70`. Legacy whole-compound discovery creates two fictitious midpoint records and aggregate
attribution raises `_PlateAttributionError`; body-local discovery returns all four physical Plate
occurrences with their original transverse witnesses and exactly one owning solid each.

Construction-authored tests cover single, equal and unequal two-body occurrences, coincident axial
bounds, nested compounds, child-order permutations, independent translation, arbitrary rigid
motion in framed recognition, defining-face provenance and installed-wheel/public typing. Negative
cases prove that separated flat boxes do not become a Plate by pooling their faces or cross-section
area. Existing thickness, area, opposed-face and open-shell compatibility boundaries remain
unchanged and retain their prior tests.

## Effectiveness and runtime result

The framed effectiveness command evaluated the lexical first 500 MFCAD++ models with taxonomy
mapping v1: 500 evaluated, zero invalid or empty. A full model-by-model comparison excluding
runtime metadata was identical to the prior E2 report. The reconciled physical output contains 233
Plates; the paired aggregate benchmark measures 234 raw aggregate Plate records before corpus
reconciliation. These are intentionally distinct metrics, not a count discrepancy.

| Workload | Models | Legacy raw Plates | Body-local raw Plates | Added | Other outputs equal | Legacy retained | Body-local/legacy total |
| --- | ---: | ---: | ---: | ---: | --- | --- | ---: |
| MFCAD++ first 500 | 500 | 234 | 234 | 0 | yes | yes | 0.9902 |
| NIST/Gramel census | 13 | 12 | 14 | 2 | yes | yes | 1.0094 |

The isolated MFCAD++ arms took 225.95 s and 223.73 s; paired median delta was -0.0046 s per model.
The isolated census arms took 188.53 s and 190.30 s; paired median delta was -0.0036 s. Both are
inside the 1.10 total-time budget. Alternating arm order limits systematic warm-cache bias.

The final local fast tier passed 2,326 tests; its sole failure was the mechanical surface-reader
roster after moving the reader into `_plate_proposals`, and that architecture test passed narrowly
after correction. The exhaustive tier passed 384 tests. Focused suites passed 58 tests and the
broader Plate/tolerance neighborhood passed 224 tests. Ruff, mypy and the installed-wheel contract
pass. Hosted Linux fast/slow, Python 3.10/3.12/3.14, macOS, Windows and coverage checks are green.
One independent contract/ADR review found one bounded benchmark error-transition omission; the
same reviewer verified the narrow fix and reported no remaining material issue.

## ADR conformance

- ADR 0002/0003: equal values on separate bodies retain physical multiplicity; candidates are
  staged before atomic publication and the public record/schema remain unchanged.
- ADR 0004: every accepted low/high role and `SolidRef` belongs to exactly one solid; no aggregate
  cache or face grouping crosses that boundary.
- ADR 0007/0008/0009: `_discover_plates` remains the sole writer-enabled family core, with one
  aggregate invocation and the existing tolerance authorities.
- ADR 0011: scope, axis, bounds, transverse witnesses and defining evidence are derived from the
  same framed working solid. Child transforms and topology ordering do not alter occurrences.
