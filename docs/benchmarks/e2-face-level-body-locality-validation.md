# E2 body-local FaceLevel prerequisite validation

PR #346 is the focused prerequisite for issues #335 and #336. It makes FaceLevel discovery,
filtering, support spans and defining evidence local to each valid solid while retaining one
aggregate family invocation and the existing public record schema. Issue #335 remains open until
#336 uses this authority to prove that riser projection joins levels and risers only within the
same solid.

## Evidence identity

- Reviewed implementation HEAD: `e3ac1d90ad9902a3294503cd28833c30261f30ef`; parent provider
  milestone: `9803829e298e5c2f6806423bd5ce743edfa76aeb`.
- MFCAD++ corpus: published test split, DOI
  [`10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823`](https://doi.org/10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823),
  first 500 unique model IDs in lexical order, selection SHA-256
  `323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`.
- Taxonomy v2 SHA-256: `67f092a2aa8d08be94e9be409c1fb338350626c7f4d1398c2f78be3123977f3b`.
- [Final effectiveness report](effectiveness-mfcadpp-500-face-level-body-local-e3ac1d9.json),
  SHA-256 `d3be7b625afa2d4ac0f446ee436ed8c32d073a990c0c1fd00025c5ddc2887af2`.
- [Provider comparator](effectiveness-mfcadpp-500-e2-framed-provider-a404823.json), SHA-256
  `eb21c3e50d00ba6a24a7566b7020d916305171b878ac7a03550fab4bd050e0dd`.

MFCAD++ is direct development evidence. No MFInstSeg model was inspected for this increment and no
transfer claim is made.

## Geometry and ownership result

The consumer reproduction now returns two equal-Z physical occurrences for two separated stepped
bodies. Each retains its real XY support rather than a union spanning the air gap, and each
aggregate candidate owns the complete horizontal source-face cluster from exactly one graph-proved
valid solid. Area filtering and end-envelope exclusion use that same body's footprint and height.

Construction-authored controls cover equal separated occurrences, connected same-body coalescence,
nested compounds, child-order permutation, a large unrelated body, STEP round trip and arbitrary
rigid placement through framed recognition. Existing off-grid tolerance tests now explicitly prove
that nearby faces on separate bodies do not cluster through air. Reviewed Draftwright goldens split
previous compound-global support unions and remove levels that were interior only to the compound,
not to any physical body.

## MFCAD++ effectiveness and runtime

The isolated final framed run evaluated 500/500 models with zero invalid or empty models. Every
accepted physical-family count is unchanged from the provider comparator, including 1,408
FaceLevels. After removing package, runtime and environment metadata plus only the newly exposed
unmapped FaceLevel attribution fields, both full model-by-model reports have normalized SHA-256
`2a8b243ef8110ddf0bd0f77fe68106c10e929e23125a52d165094bba34fe402a`. The exact normalization
applied independently to each report is:

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

Publishing exact FaceLevel evidence intentionally changes two attribution diagnostics. Unmapped
record projections rise from 793 to 2,201: exactly the 1,408 structural FaceLevel occurrences,
which taxonomy v2 does not map to a machining class. Taxonomy-mismatch defining faces rise from
1,133 to 2,599 because some FaceLevels own more than one horizontal face. These are newly visible
structural claims, not added recognitions or a supported-class precision regression; the raw report
is retained so consumers can audit both views.

The isolated final run took 327.21 s total, with 0.623 s median and 1.170 s p95 per model. The
isolated provider comparator took 348.67 s total on the same development host, a descriptive ratio
of 0.9385. No performance regression is observed; this is not presented as a tightly paired
microbenchmark.

## Test, review and ADR gates

- Local fast lane: 2,350 passed in 324.88 s.
- Local exhaustive lane: 389 passed in 933.57 s.
- Capability/registry follow-up: 94 passed; Ruff and mypy passed.
- One independent final-diff review found one stale attribution-roster sentence. The narrow fix
  was verified clean at `e3ac1d9`; no production, test or golden blocker remains.
- Hosted Linux/macOS/Windows and Python-version checks are the final merge gate.

ADR 0007 remains satisfied: the public facade is writer-free and `_discover_step_levels` is the
sole writer-enabled adapter. ADR 0008 remains satisfied: tolerance clusters are unchanged while
area and end-envelope authorities are evaluated per solid. ADRs 0002-0004 remain satisfied:
equal-valued occurrences retain multiplicity, exact original-face evidence has one SolidRef, and
publication remains deterministic and atomic. The final diff does not claim the same-solid riser
join; that separately reviewed contract remains explicit in #336.
