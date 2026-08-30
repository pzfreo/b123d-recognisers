# E2 body-local TurnedProfile validation

Issue #337 makes TurnedStep discovery, grouping and downstream Plate suppression physical-body
local in compound parts. The recogniser reuses the run-owned cylinder inventory, partitions its
existing `solid_idx` evidence once, and publishes no candidate until the complete family roster
has proved exact one-solid ownership.

## Evidence identity

- Reviewed behavior HEAD: `2023fafa1a6b8782326c964d08c36b58a12da6c1`; merged Riser
  prerequisite: `9ca53f5a79537f0ede516a3dc851590cc12f3b65`.
- Package identity: `0.4.9.dev0` (development version, not a release).
- MFCAD++ corpus: published test split, DOI
  [`10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823`](https://doi.org/10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823),
  first 500 unique model IDs in lexical order, selection SHA-256
  `323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`.
- Taxonomy v2 SHA-256: `67f092a2aa8d08be94e9be409c1fb338350626c7f4d1398c2f78be3123977f3b`.
- [Final effectiveness report](effectiveness-mfcadpp-500-turned-profile-body-local-2023faf.json),
  SHA-256 `aa797b239277c6cea8290043a6b249cc61366fada4ec217abbb8ffe97344cb58`.
- [Riser comparator](effectiveness-mfcadpp-500-riser-body-local-a77df94.json), SHA-256
  `f954634d3f28b3aa40372b620e7f1bff2145118a3bf37281f0bd01208a5b7044`.

MFCAD++ is direct development evidence. No MFInstSeg model was inspected and no transfer claim is
made for this increment.

## Geometry, occurrence and consumer result

Each valid solid is evaluated against only its own external cylinder bands and bounds. Every
recogniser-produced `TurnedStep` carries one immutable `TurnedProfileKey`: its principal axis line
plus body bounds distinguish parallel, coaxial-disjoint and mixed-axis profiles without exposing
SolidRef, traversal position or live topology. `TurnedProfile.grouped_from_steps` preserves those
physical groups; the legacy `from_steps` convenience accepts one group and refuses an accidental
cross-profile merge.

The complete proposal roster is bound to exact original cylinder faces and checked before any
candidate is issued. A forced later attribution failure proves that no earlier candidate prefix is
left behind. Plate discovery consumes only completed TurnedStep occurrence SolidRefs, excludes
those same solids, and still permits an independent prismatic body in a rotational-classified
compound. A rotational-classified shape with no established turned profile retains its historical
empty Plate inventory. Neither registry adapter rescans cylinders or invokes either family twice.

Construction-authored controls cover equal and unequal parallel shafts, coaxial-disjoint profiles,
mixed principal axes, equal-valued records with distinct keys, child-order stability, STEP round
trip, framed AXIAL gauge motion, exact evidence ownership, atomic failure, and mixed turned/Plate
suppression. Existing groove, chamfer, fillet, bore and Plate neighborhoods remain covered by the
full suite.

## MFCAD++ effectiveness and runtime

The isolated framed run evaluated 500/500 models with zero invalid or empty models. Every summary
metric and every model-level evidence row is identical to the Riser comparator. After removing
only package/environment/runtime identity and each model's `seconds`, both reports have normalized
SHA-256 `0f7e02d4d5347e7f72dd63f61d24d084ca0cfb88c39af2f13654724551539c6f`:

```bash
jq -S 'del(.package,.environment,.runtime) | .models |= map(del(.seconds))' REPORT.json \
  | sha256sum
```

The final run took 313.04 seconds total, with 0.596 seconds median and 1.137 seconds p95 per model.
The isolated comparator took 299.62 seconds; the descriptive total-time ratio is 1.0448. This is
within the expected variation of separate CAD-kernel runs and is not presented as a paired
microbenchmark. More importantly, the implementation performs the same single cylinder scan and
the model-level semantic/evidence vector is unchanged.

## Test, review and ADR gates

- Final local fast lane: 2,374 passed in 413.92 seconds before the final conservative Plate gate;
  that gate and regenerated goldens then passed 159 focused integration tests.
- Exhaustive lane: 389 passed in 1,419.31 seconds.
- Ruff, mypy, manifest validation and diff checks passed.
- One independent contract review found one stale ADR statement and one missing atomic-failure
  test. Both were fixed; the same reviewer found the narrow recheck clean.

ADRs 0003, 0005, 0007, 0010 and 0011 remain satisfied. Persistent identity is geometry-derived,
serializable and topology-free; run-local ownership remains in completed occurrence evidence.
The cylinder substrate is reused once, discovery publication is atomic, framed coordinate meaning
is explicit, schema versions advance deliberately, and downstream suppression is same-solid.
