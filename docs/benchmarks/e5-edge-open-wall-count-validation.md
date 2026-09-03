# E5 edge-open polygonal wall-count validation

## Decision

ADR 0018 already defines `EdgeOpenPrismaticRecess` as a chain of at least three physical planar
wall supports. The initial implementation admitted exactly six walls as a deliberately narrow
first consumer. This increment removes that implementation-only equality and applies the unchanged
floor, wall-completeness, exterior-opening, mouth, empty-sweep, backing and solid-ownership proofs
to every chain of three or more walls. It does not change the record schema, infer a closed
polygon, or weaken `PrismaticPocket`.

## Corpus-independent controls

`tests/test_edge_open_prismatic_recesses.py` now provides authored three-, four-, five- and
six-wall positives and repeats rigid-axis covariance for every wall count. A two-wall profile is
refused at the exact lower boundary. The existing closed, floorless, perforated, repeated-contact,
parallel-endpoint, shallow-nonparallel, STEP, compound, evidence and schema controls exercise the
same shared proof independently of wall count.

## Complete MFCAD++ development result

The machine report is
[`effectiveness-mfcadpp-2500-edge-open-wall-count-7cb006c.json`](effectiveness-mfcadpp-2500-edge-open-wall-count-7cb006c.json),
SHA-256 `fe81e8ce1183092b0d246a936865504154c9add0f831b01a89c88b1d639fe663`.
It evaluates the published 2,500-model test split in raw coordinates at implementation commit
`7cb006c120227b0a68462efea3bdbca608cb435a`, with taxonomy v12. There are 2,493 evaluated models
and the same seven explicit invalid dispositions.

The exact parent is PR #477's taxonomy-v11 report at implementation commit `7a47cb0`. Taxonomy v12
only adds the already-public edge-open family to classes 13 and 14; no recognition result in the
parent belongs to either class, so the recognition deltas remain exact.

| class | parent coverage | current coverage | gain |
|---|---:|---:|---:|
| Triangular Pocket (13) | 3,412 / 3,892 (0.8767) | 3,533 / 3,892 (0.9078) | +121 |
| Rectangular Pocket (14) | 4,503 / 4,895 (0.9199) | 4,609 / 4,895 (0.9416) | +106 |
| 6-sided Pocket (15) | 5,173 / 5,707 (0.9064) | 5,319 / 5,707 (0.9320) | +146 |

The family grows from 23 to 170 occurrences: 147 new physical records and 373 newly covered
polygonal-Pocket faces. Existing physical-family counts and all reconciliation-drop counts are
unchanged, and no class loses a covered or defining face.

## Vocabulary overlap

The new occurrences are not selected from labels. Reading labels only after Candidate construction
shows 113 of 147 new records have defining walls wholly inside one of the three target Pocket
classes. The remaining 34 are geometrically valid edge-open profiles crossing the dataset's
single-label vocabulary: most are a three-wall profile made of two Rectangular-blind-step walls and
one Chamfer wall; six similarly overlap a paired ramp and Chamfer. Across new defining evidence,
439 of 537 wall faces carry a target Pocket label (0.8175). This is disclosed rather than hidden by
a label-driven rejection: the observed part still contains the physical open chain promised by
ADR 0018, while the dataset assigns its faces to design-intent classes that can overlap that
description.

Family-agnostic coverage therefore also rises for Chamfer (+21), 2-sided through step (+10),
Rectangular blind slot (+3) and Rectangular blind step (+41). These are coverage overlaps, not new
occurrences of those families. Taxonomy mismatch rises by 98 defining faces, exactly the disclosed
cross-vocabulary wall evidence. MFInstSeg was not inspected or run for this increment.
