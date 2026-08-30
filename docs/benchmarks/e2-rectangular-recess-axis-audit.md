# E2 rectangular recess frame-axis audit

Issue [#320](https://github.com/pzfreo/b123d-recognisers/issues/320) removes the world-Z and
axis-iteration dependencies from principal-axis `Pocket` and `Slot` recognition. A corner
interruption now assigns depth to its uniquely shallowest physical leg. Opposed-wall floored
recesses evaluate both possible depth interpretations and accept exactly one, rather than letting
the first rejected XYZ interpretation suppress a later valid one. Ambiguous geometry fails closed.

## Evidence identity

- Corpus: MFCAD++ published test split, DOI
  [`10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823`](https://doi.org/10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823).
- Selection: first 500 STEP model IDs, lexical ascending; selected-ID SHA-256
  `323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`.
- Final behavior commit: `c4c0fa1f9f537adafa9737536828c0130b32e1a4`; measurement-tool commit:
  `4cfd8ae53b47610a88d7f16a1f05c7d0bfcdf35a`.
- Final [frame report](e2-rectangular-recess-frame-corpus-500-4cfd8ae.json), SHA-256
  `26a3f3869242727fffe0c4d9e9fdd41ffe586b0f88f82276afc4d3676f2e6d1d`.
- Defining-face [transition audit](e2-rectangular-recess-frame-transitions-500-4cfd8ae.json),
  SHA-256 `6e1f6ccf18d43c39332f03930035d6e9ba57ed42db7aa16c86b85d2331b61269`.
- Taxonomy-v2 effectiveness: [raw](effectiveness-mfcadpp-500-e2-rectangular-raw-4cfd8ae.json)
  (`d5751c1643cebf06ca35e782550cddac372a4064d89368433cd836411a6a080d`) and
  [framed](effectiveness-mfcadpp-500-e2-rectangular-framed-4cfd8ae.json)
  (`6397d36e300054f564a1129a71861e57f944613d2eeda8c4ad49e5225916a335`).

MFCAD++ is open development evidence. Its face labels measure effect but do not choose geometry
semantics. It has no publisher instance relation, so instance recall is correctly undefined.

## Contract proof

Authored construction tests cover signed X/Y/Z principal permutations, translation and arbitrary
whole-part rigid motion through the framed aggregate. They prove stable dimensions and opening
semantics for opposed-wall pockets and corner interruptions, exact original-face provenance,
direct/aggregate parity and deterministic ordering. STEP round trips preserve the canonical corner
depth. Adversarial controls retain through Slot, open Channel, sealed void, material rib/island,
cross-solid, split-floor and ambiguous equal-leg refusals. The ambiguity boundary uses the existing
`COORD_FLOOR`: a 0.5-floor difference refuses and a two-floor difference establishes depth.

No public record, family ownership, reconciliation rule or tolerance was added. The implementation
remains in the shared rectangular-recess core and retains one graph/evidence authority.

## Corpus result

The released-frame baseline changed 51 raw Pockets to absent, introduced 33 Pockets, lost three
Slots and reclassified one Pocket/Slot in each direction. The corner-only intermediate report
reduced this to 15 absent and 17 introduced Pockets plus three absent Slots. The final report has
four absent Pockets, three absent Slots, and **zero introduced rectangular recesses or
reclassifications**.

Every residual transition has a geometry-derived classification:

| Residual | Count | Classification |
| --- | ---: | --- |
| Pocket absent | 3 | Defining evidence is internally oblique in the inferred stock frame. |
| Pocket absent | 1 | Principal only in the accepting raw presentation; framed walls are tilted about 1.9°. |
| Slot absent | 3 | An alternate projection of a coincident blind Pocket, not an enclosed through-slot. |

The classifier requires both the dominant normal component to be near one and every transverse
component to be near zero; it does not mistake a 0.9994 component for an exact principal face.
There are zero unclassified residuals and zero frame refusals. Framed rigid-motion recognition
retains 2,878/2,878 baseline occurrences; the previously documented extra Slot sentinel remains.

## Effectiveness and runtime

Both taxonomy-v2 runs evaluate 500/500 models with zero invalid or empty results. Relative to the
prior `01c93cc` E2 development report, correct Pocket defining faces rise from 1,335 to 1,354 net.
Rectangular-pocket recall rises from 385/907 (42.45%) to 404/907 (44.54%), and rectangular blind
step rises from 403/607 (66.39%) to 449/607 (73.97%). Rectangular blind-slot attribution falls from
77/178 to 31/178 because the old result depended on world Z; those faces move chiefly to the
geometry-canonical rectangular Pocket/blind-step interpretation. Raw rectangular-through-slot
recall remains 31/237.

The paired raw run takes 240.89 seconds and the framed run 251.35 seconds, a 1.0434 ratio, below
the E2 1.10 package budget. The complete frame evaluation takes 910.22 seconds; frame inference and
normalization are 15.69 seconds, while framed recognition is 447.39 seconds versus 418.70 seconds
raw. No MFInstSeg tree is available under the checked workspace dataset paths, so this child does
not inspect transfer models; MFInstSeg remains the Epic #290 milestone baseline.

## ADR conformance

- ADR 0002: values and ordering derive from physical spans, never axis-letter/traversal order.
- ADR 0003: existing aggregate and reconciliation remain the only accepted-result authority.
- ADR 0004: candidates retain exact defining source faces through the shared graph.
- ADR 0007/0009: the change stays in the rectangular-recess family core; no upstream filter moves.
- ADR 0008: only existing coordinate/tolerance constants are used; no corpus-derived threshold.
- ADR 0011: records remain local to the explicit selected frame; internally oblique features stay
  outside this principal-axis child and are tracked separately by #310.

