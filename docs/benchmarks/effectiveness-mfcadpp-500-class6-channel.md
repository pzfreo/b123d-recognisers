# MFCAD++-500 class-6 Channel mapping decision

## Decision

MFCAD++/MFInstSeg class 6, `Rectangular through slot`, maps to both `channels` and
`slots` in immutable effectiveness taxonomy v7. The class remains `partial`.

This is a comparison decision only. It does not change either recogniser, evidence
ownership, reconciliation, public records, or aggregate output. Dataset labels locate
the disagreement but do not decide those production contracts.

## Geometry justification

The exact MFCAD++-500 class-6 audit at `e0251da` covers all 237 labelled faces in 67
shared-edge label-component proxies across 50 models. Channel constituent evidence
touches 31 components and 94 faces, fully covering 28 components. Twenty-three of the
26 Channel-only components contain exactly three planar faces. Representative models
`1000`, `10092`, `10138`, and `10228` each contain the public Channel motif: two
opposed planar side walls plus the planar floor of a rectangular recess open at both
longitudinal body-envelope ends.

Five components are touched by both families. In `10047`, `11687`, `12546`, and
`12805`, each component is exactly three planar faces: Channel contributes its two
defining walls and constituent floor, while Slot independently contributes its two
route-selected defining walls. This overlap is expected evidence visibility, not a
reason to change physical reconciliation.

Slot remains in the mapping because the earlier complete class-6 topology census in
issue #358 established a smaller legitimately supported enclosed principal-axis
subset. In this audit Slot touches 14 components and 31 faces. Nine are Slot-only;
their label components include intersected/split fragments, including model `1118`
where the accepted route is split across two label components. Component proxies are
therefore evidence units rather than physical-feature ground truth, and replacing
Slot with Channel would erase genuine agreement. Conversely, free-axis and split
variants remain outside both contracts, so marking the class fully supported would
overstate capability.

## Exact comparison

Both reports use the fixed lexical first-500 selection, selection SHA-256
`323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`, and the
published test split identified by DOI
`10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823`.

| Class-6 measure | taxonomy v6 (`slots`) | taxonomy v7 (`channels`, `slots`) |
| --- | ---: | ---: |
| Defining-face recall | 31/237 (13.08%) | 85/237 (35.86%) |
| Defining-face precision | 31/88 (35.23%) | 85/183 (46.45%) |
| Exact all-family face coverage | 199/237 (83.97%) | 199/237 (83.97%) |
| Mapped records | 16 | 47 |
| Corpus taxonomy-mismatch defining faces | 3,265 | 3,203 |

All 500 normalized production rows are exactly equal between the v6 report at
`c6381c6` and the v7 report at `b277522`; every non-class-6 score row is also equal.
Physical family counts, dispositions, diagnostics, source hashes, empty-result state,
and accepted records did not move. The v7 run evaluated 500/500 models with no invalid
or empty models in 310.161 seconds (median 0.575 seconds, p95 1.096 seconds). This is
runtime metadata, not a paired performance claim, because the mapping does not execute
inside recognition.

Artifacts:

- `mfcadpp-class6-channel-slot-audit-e0251da.json`: complete per-component and
  per-family audit;
- `effectiveness-taxonomy-v7.json`: immutable mapping;
- `effectiveness-mfcadpp-500-class6-channel-b277522.json`: canonical exact report.

Reproduction (check out `e0251da` for the audit artifact and `b277522` for the
effectiveness artifact; later documentation-only commits reproduce the counts but
record their own exact head):

```console
python tools/audit_mfcadpp_component_overlap.py \
  /path/to/MFCAD++_dataset/step/test \
  --class-id 6 --mapped-family slots \
  --compare-family channels --compare-family slots --limit 500 \
  --output docs/benchmarks/mfcadpp-class6-channel-slot-audit-e0251da.json

python tools/run_effectiveness_baseline.py \
  mfcadpp /path/to/MFCAD++_dataset/step/test \
  --dataset-version "MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823" \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v7.json --limit 500 \
  --output docs/benchmarks/effectiveness-mfcadpp-500-class6-channel-b277522.json
```

## Transfer and architecture

The existing aggregate MFInstSeg summary directionally identifies the same contested
`slots ← channels` pair (68 faces), but the corpus mount is unavailable and no
individual MFInstSeg model was inspected. A canonical v7 transfer rerun remains an
E0/E6 milestone item.

Final-diff review against ADRs 0002, 0003, 0004, 0005, and 0007 is clean: family contracts and
deterministic output are unchanged; discovery and reconciliation remain separate;
defining versus constituent evidence remains explicit; stable family identifiers are
reused; and no recogniser module seam changes. The independent contract review of
`458a594` reproduced the taxonomy delta, audit counts, exact score movement and
normalized row parity and found no concrete blocker or materially false claim.
