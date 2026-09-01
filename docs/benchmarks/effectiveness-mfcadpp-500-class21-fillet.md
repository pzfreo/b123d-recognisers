# MFCAD++-500 class-21 Fillet mapping rejection

## Decision

Do not add `fillets` to MFCAD++/MFInstSeg class 21, `Circular blind step`.
Immutable taxonomy v7 remains unchanged: the class maps only to
`circular-blind-steps`.

This rejects a tempting comparison-score increase. It does not change either
recogniser, evidence ownership, reconciliation, public records, or aggregate output.

## Geometry justification

The exact MFCAD++-500 audit at shipped main `1432138` covers all 354 class-21
faces in 173 shared-edge same-label component proxies across 131 models.

- `CircularBlindStep` evidence covers 236 faces and fully covers all 117 components
  it touches. Its public contract owns both the cylindrical wall and blind planar
  terminal.
- Accepted `Fillet` evidence covers 42 cylindrical faces in 42 different residual
  components. It never overlaps an accepted `CircularBlindStep` component.
- Thirty-seven of those residual components also contain one or more labelled planar
  terminals which Fillet does not own: 29 contain one cylinder plus one plane, seven
  contain one cylinder plus two planes, and one contains two cylinders plus three
  planes. `StepLevel` touches only 12 of these 37 components, `AngledStep` touches one,
  and accepted all-family evidence fully covers only nine. These other families can
  supply some terminal coverage, but none turns the Fillet record itself into a
  complete circular blind step.
- The remaining five Fillet-covered label components are singleton cylinders, but
  they have the same accepted Fillet wall semantics and provide no terminal evidence
  that would justify treating a generic round as a complete CircularBlindStep.

Representative residual models `1000`, `10033`, `10118`, and `10127` show a
concave cylindrical wall joined directly to the labelled planar terminal geometry.
This is the same physical motif as the accepted class-21 components in `10000`,
`10063`, and `1007`; the difference is that the stricter CircularBlindStep predicate
does not accept the residual form. Mapping Fillet would therefore score an incomplete
fallback interpretation of a missed step, not a second public vocabulary for the same
complete feature.

ADR 0003 independently confirms the semantic boundary: when both candidates do
describe the same region, reconciliation records
`blend.fillet_superseded_by_circular_blind_step`. That loser is not another physical
class-21 occurrence.

## Exact counterfactual

Both measurements use the fixed lexical first-500 selection, selection SHA-256
`323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`, and the
published MFCAD++ test split identified by DOI
`10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823`.

| Class-21 measure | shipped v7 (`circular-blind-steps`) | unshipped counterfactual (+ `fillets`) |
| --- | ---: | ---: |
| Defining-face recall | 236/354 (66.67%) | 278/354 (78.53%) |
| Defining-face precision | 236/236 (100%) | 278/284 (97.89%) |
| Exact all-family face coverage | 298/354 (84.18%) | 298/354 (84.18%) |
| Mapped records | 118 | 160 |
| Corpus taxonomy-mismatch defining faces | 3,203 | 3,161 |

The counterfactual changes comparison mapping only, so all 500 production rows and
physical family counts remain unchanged. It was generated from a temporary uncommitted
mapping edit and is deliberately not a canonical artifact: retaining it beside
immutable taxonomy v7 would falsely imply that v7 contains the rejected mapping.

## Artifacts and reproduction

`mfcadpp-class21-circular-step-fillet-audit-1432138.json` is the immutable complete
per-component and per-family audit. Reproduce it at `1432138` with:

```console
python tools/audit_mfcadpp_component_overlap.py \
  /path/to/MFCAD++_dataset/step/test \
  --class-id 21 --mapped-family circular_blind_steps \
  --compare-family circular_blind_steps --compare-family fillets --limit 500 \
  --output docs/benchmarks/mfcadpp-class21-circular-step-fillet-audit-1432138.json
```

## Transfer and architecture

The aggregate-only MFInstSeg summary directionally reports the same contested pair,
but its corpus mount is unavailable and no individual model was inspected. This
MFCAD++ rejection prevents the rounded aggregate from overriding the public geometry
contract; a future canonical transfer run should retain the shipped mapping.

The decision conforms to ADRs 0002, 0003, 0004, 0005, and 0007. Deterministic family
output, explicit reconciliation, defining/constituent evidence, stable family IDs and
module seams are unchanged. The independent review found and corrected an
overstatement of StepLevel terminal coverage; the decision, audit arithmetic,
counterfactual, unchanged taxonomy and ADR conformance were otherwise clean.
