# E5 neutral blend-chain gap audit

Issue #414 asks whether the existing private `BlendCollapseIndex` has measurable value for the
class-23 `Round` / public `Fillet` coverage gap before another blend recogniser is designed. This
audit constructs chains from production graph and effective-surface authority; labels are read only
after discovery.

## Authority

- Production main: `6ae44e0ab4db830ebe91890bca7e83072518d5bd`
- Audit implementation: `ee5f4ae503154f74d5909bd28488b7556fd6a706`
- Production source hash: `2a7a12458dbc882ccb8b354be3636f31ed4f3b7ab18fc587dde0138c27828571`
- Standard lexical-500 selection hash: `323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`
- Complete 2,500-model selection hash: `ad92768788d88e3c4e3866bc2a614e7a345fea7fc52463dfc9f0b9b9e850058e`

Canonical artifacts:

- `mfcadpp-blend-chain-audit-500-ee5f4ae.json`
  (`cfba6e7637c2f0097a35350450a1b5a8e47eea0adf7d7dde860bf6882b42804e`)
- `mfcadpp-blend-chain-audit-2500-ee5f4ae.json`
  (`fd6942c3987f14d27ba6cc89a337bbf96fad723fc9aaf46e8ed7421829233756`)

## Standard milestone is not a useful denominator

The first lexical 500 models contain one Round face. It is a torus, is untouched by accepted
evidence and is outside the cylindrical blend index. No conclusion about #414 can rest on this
one-face sample. Label-blind discovery nevertheless measures 403 concave chains and 1,146 refused
components across all 500 models before that label is read.

## Complete MFCAD++ test corpus

The full mounted 2,500-model test corpus contains 13 Round faces in eight models:

| state | Round faces |
| --- | ---: |
| already covered by accepted constituent evidence | 5 |
| already covered by defining evidence | 0 |
| already covered by accepted Fillet evidence | 0 |
| untouched by every accepted constituent | 8 |
| untouched and reached by a convex neutral chain | 5 |
| untouched in an index refusal | 1 |
| untouched and outside the index | 2 |

Across all 2,500 models, label-blind discovery issues five convex chains containing five faces. All
five carry the Round label: 5/5 target-class precision for this measured convex subset. It also
issues 1,828 concave chains containing 1,830 faces; only one face is Round-labelled, and that face
is already covered by Pocket constituent evidence. Consequently the measured reusable subset is
specifically **convex**, not a license to publish every neutral chain as `Fillet`.

The five recovered untouched faces are native cylinders. Three have principal axes and radii below
the current default 0.6 minimum-evidence threshold; one has a principal axis and radius 0.951. The
fifth is small-radius with a non-principal cylinder axis. These facts separate three
decisions that must not be conflated: using the index, changing the minimum-radius policy, and
generalising the public `Fillet.axis` schema.

The two untouched faces outside the index are one torus and one surface of revolution. They cannot
be recovered by consuming `BlendCollapseIndex` and remain separate geometry work.

## Decision

`BlendCollapseIndex` has demonstrated downstream value and must not be removed as unused
foundation. Its same-solid convex chains find five of eight otherwise untouched MFCAD++ Round faces
with no class-23 false positive in the complete corpus. However, 13 labelled faces are too small a
denominator to authorize a public Fillet contract change, and the standard 500-model effectiveness
gate cannot measure the proposed consumer meaningfully.

The complete label-blind run takes 315.15 seconds. It constructs the index before consulting labels
for every selected model; the aggregate recognition inventory is run only for label-positive models
to measure existing evidence overlap, after neutral discovery is complete.

Before implementation, run this same aggregate-only decomposition on the published MFInstSeg test
partition, where the saved baseline reports 3,415 Round faces and 2,486 untouched faces. The former
workspace mount is currently absent, the saved artifact is summary-only, and the public dataset
copy requires authenticated access; exact chain topology cannot be reconstructed from rounded
metrics. The required audit must report convex/concave reach, purity, refusal reasons, radius bands,
axis capability and overlap with accepted Fillet, Circular Blind Step, Pocket and O-ring evidence.

No Analysis Situs rerun is requested yet. The fair comparison point is a reviewed implementation
merged to main, with an exact shared model selection and the upstream radius/cone/extrusion settings
recorded.
