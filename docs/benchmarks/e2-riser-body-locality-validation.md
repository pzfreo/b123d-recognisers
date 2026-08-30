# E2 body-local Riser recognition and projection validation

Issue #336 completes the same-solid level/riser contract begun by #335. Riser discovery,
full-span and envelope gates, value reduction, defining evidence and projection authority are now
scoped to one valid solid. Equal occurrences on separate solids remain distinct, including
value-identical bodies.

## Evidence identity

- Reviewed behavior HEAD: `a77df940df5b042320226aae366fe3ba0fb137fc`; merged FaceLevel
  prerequisite: `4b6fe4522a8c40f64b5fe7378f1982965a2489e0`.
- Package identity: `0.4.9.dev0` (development version, not a release).
- MFCAD++ corpus: published test split, DOI
  [`10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823`](https://doi.org/10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823),
  first 500 unique model IDs in lexical order, selection SHA-256
  `323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`.
- Taxonomy v2 SHA-256: `67f092a2aa8d08be94e9be409c1fb338350626c7f4d1398c2f78be3123977f3b`.
- [Final effectiveness report](effectiveness-mfcadpp-500-riser-body-local-a77df94.json),
  SHA-256 `f954634d3f28b3aa40372b620e7f1bff2145118a3bf37281f0bd01208a5b7044`.
- [FaceLevel comparator](effectiveness-mfcadpp-500-face-level-body-local-e3ac1d9.json),
  SHA-256 `d3be7b625afa2d4ac0f446ee436ed8c32d073a990c0c1fd00025c5ddc2887af2`.

MFCAD++ is direct development evidence. No MFInstSeg model was inspected and no transfer claim is
made for this increment.

## Geometry, occurrence and projection result

Each valid solid supplies its own bounds, eligible FaceLevel occurrences and Riser proposals.
Equal records are reduced only within that solid; the aggregate retains separate candidates with
complete original-face evidence and distinct graph-proved SolidRef authority. The aggregate
declares STEP_LEVELS as a completed predecessor and reuses those exact records instead of rescanning
horizontal faces or associating bodies by equal Z values.

`RiserEvidence.body_levels` is the serializable same-solid authority. Existing numeric projection
remains a value selector. Full FaceLevel selectors distinguish equal Z values whose body-local
supports differ; `levels_by_riser` supplies an explicit one-for-one occurrence roster for two
value-identical bodies without publishing an unstable topology/body identifier. A hand-built
legacy record with `body_levels=None` retains the pre-0.4.9 value-only projection. Non-default scan
tolerance is forwarded to FaceLevel authority and remains the projection default.

Construction-authored controls cover separated equal and unequal steps, a false compound-envelope
case, translated children, nested/order variants, same-solid duplicate-face reduction, exact
duplicate solids, occurrence-aligned selection, arbitrary rigid placement, STEP round trip and
non-default tolerance. Existing pad, pocket, channel, chamfer and ramp neighborhoods remain in the
full suite. Complete neutral Riser attribution does not suppress an independently observed bounded
AngledStep diagnostic.

## MFCAD++ effectiveness and runtime

The isolated framed run evaluated 500/500 models with zero invalid or empty models. Every accepted
physical-family count is unchanged from the FaceLevel comparator, including 737 Riser occurrences
and 1,408 FaceLevels. After removing package, environment and runtime metadata plus only the newly
published unmapped-Riser attribution fields, both model-by-model reports have normalized SHA-256
`2a8b243ef8110ddf0bd0f77fe68106c10e929e23125a52d165094bba34fe402a`:

```bash
jq -S \
  'del(.package,.environment,.runtime,
       .summary.taxonomy_mismatch_defining_faces,
       .summary.mapped_dataset_class_records.unmapped)
   | .models |= map(del(.seconds,
                        .taxonomy_mismatch_defining_faces,
                        .mapped_dataset_class_records.unmapped))' \
  REPORT.json | sha256sum
```

Publishing exact Riser evidence raises unmapped structural records from 2,201 to 2,938, exactly
the 737 Riser occurrences. Taxonomy-mismatch defining faces rise from 2,599 to 3,161 because a
Riser may own multiple producing faces. These are newly visible structural claims, not added
machining-family recognitions or a precision regression. The one bounded unsupported AngledStep
diagnostic remains present.

The isolated run took 299.62 s total, with 0.561 s median and 1.090 s p95 per model. The isolated
FaceLevel comparator took 327.21 s on the same development host, a descriptive ratio of 0.9157.
No performance regression is observed; this is not presented as a tightly paired microbenchmark.

## Test, review and ADR gates

- Final local fast lane: 2,365 passed in 225.73 s.
- Exhaustive lane: 389 passed; the subsequent diagnostic/seam fix was covered by 200 focused
  architecture, explanation, registry and production tests plus the final fast rerun.
- Packaging/public contract: wheel and sdist built as `0.4.9.dev0`; 118 package, manifest,
  typing-facing contract, result and registry tests passed.
- Ruff, mypy and diff checks passed.
- One independent bounded review found two concrete blockers: equal-Z value selection lacked an
  occurrence association, and public non-default tolerance was not forwarded. Both were fixed and
  verified. The same reviewer found the post-full-lane diagnostic/seam corrections clean.

ADRs 0002, 0004, 0005, 0007 and 0008 remain satisfied. Candidate identity and exact original-face
provenance stay run-owned; no SolidRef or live CAD object enters public records. Publication is
atomic and fail-closed. The schema advances explicitly, projection remains geometry-free, tolerance
ownership is unchanged, and neutral structural claims do not erase supported bounded diagnostics.
