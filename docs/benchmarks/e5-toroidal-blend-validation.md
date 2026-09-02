# E5 toroidal Blend validation

Issue #442 extends the public `Blend` contract before downstream adoption. `Blend.radius` remains
the rolling-ball (torus minor) radius; its discriminated `path` is either a
`StraightBlendPath` or a full `CircularBlendPath` carrying centre, canonical normal and major
radius. Partial toroidal arcs remain refused because a full-circle value would not describe them
truthfully.

## Authored contract evidence

MFCAD++ contains only one labelled torus, so it is measurement rather than a specification. Three
new checked-in goldens provide several independently checkable circular occurrences:

| Golden | Contract exercised |
| --- | --- |
| `toroidal_blends_turned` | four paths on one stepped shaft, including three convex paths and one concave shoulder root |
| `toroidal_blend_internal` | one concave blind-bore floor path with known minor and major radii |
| `toroidal_blend_compound` | two equal-looking paths retained as separate body-local occurrences |

Focused tests additionally cover a torus split into two native faces, rigid transforms, mirrors,
uniform scale, STEP round-trip, traversal order, Fillet precedence, full-torus and bead rejection,
partial-torus rejection and non-tangent support rejection. Every accepted torus patch is defining
and constituent evidence.

## Architecture review

ADR 0013 owns the schema and geometric contract. The path union avoids overloading the former
cylindrical `axis`, `axis_direction` and `at` fields with toroidal meanings. ADR 0007 records the
one new private seam: `blends` uses shared analytic parameter equivalence to group native torus
patches. The surface-reader and exact-arc rosters account for native torus parameters, complete UV
coverage, oriented differential side evidence and every exact smooth-spring check.

This remains a conservative concrete consumer, not a general recovered-surface abstraction. A
candidate must prove one solid, one complete circular U domain, complete rolling boundaries, two
analytic support regions (one transverse plane and one coaxial cylinder), exact smooth springs and
an agreeing oriented material side. Full decorative tori, beads, partial paths and ambiguous or
non-tangent supports fail closed.

## Complete MFCAD++ result

The canonical run used the published lexical 2,500-model test split, raw coordinates and immutable
taxonomy v10. It retained the same seven previously documented invalid model rows and evaluated
the other 2,493 models. The command was:

```bash
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version \
  'MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823' \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v10.json \
  --limit 2500 --allow-invalid \
  --output docs/benchmarks/effectiveness-mfcadpp-2500-toroidal-blends-6d449d2.json
```

| Round / Blend measure | Previous saved Blend report `47a5f04` | Candidate `6d449d2` | Change |
| --- | ---: | ---: | ---: |
| Physical Blend occurrences | 6 | 7 | +1 |
| Round defining-face recall | 6/13 (46.15%) | 7/13 (53.85%) | +1 face |
| Round face coverage | 10/13 (76.92%) | 11/13 (84.62%) | +1 face |
| Round mapped defining precision | 6/225 (2.67%) | 7/226 (3.10%) | +1 correct claim |

The sole new Blend occurrence is model 12140. Its one defining torus is class 23 `Round`, so the
increment reaches the only previously untouched toroidal Round face in this open corpus. The
report also contains changes from commits already landed after the saved comparison report:
98 additional Chamfer records and five additional Chamfer/AngledStep reconciliation drops. Those
are not attributed to #442. No other physical-family count changes between the two reports.

The checked-in canonical report SHA-256 is
`14c53201fcc26e951f35d00bf53ea96be426587533f35a365ad1d06a5b5b0b44`.
MFInstSeg was not inspected or run for this increment.
