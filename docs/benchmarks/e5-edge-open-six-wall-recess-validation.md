# E5 edge-open six-wall recess validation

## Decision

ADR 0018 introduces a sibling `EdgeOpenPrismaticRecess` instead of weakening
`PrismaticPocket` or forcing a partial profile into `PassageSection`. The public section is the
ordered chain of physical wall segments plus the two physical endpoints of its opening. It does
not contain an inferred closing edge and does not claim an exterior-air footprint.

The first implementation deliberately recognizes only the high-value six-wall subset. It
requires one single-wire planar floor, six planar concave wall supports forming one non-branching
open path, a wholly convex residual floor boundary, exactly one common principal-axis mouth,
an empty extrusion of the exact floor toward that mouth, material behind that exact floor, and
one valid solid owner. The six walls are defining
evidence; the exact floor is additional constituent evidence.

## Corpus-independent controls

`tests/test_edge_open_prismatic_recesses.py` pins the immutable schema and serialized payload,
one authored positive, a dedicated golden, axis covariance, STEP round-trip, equal geometry on
separate bodies, exact defining/constituent evidence, and refusals for a closed pocket, a
floorless passage, and the adjacent five- and seven-wall subsets.

## Complete MFCAD++ development result

The machine report is
[`effectiveness-mfcadpp-2500-edge-open-d82a1c0.json`](effectiveness-mfcadpp-2500-edge-open-d82a1c0.json),
SHA-256 `76f513455d2c6759a67e8a227eb45ad17a5bb238326378cdbffa1b381223b2cf`.
It evaluates the complete published 2,500-model test split in raw coordinates at clean commit
`d82a1c01a805177bc3804ed4295526c57fddef06`, using taxonomy v11. Seven published malformed inputs
remain explicit invalid dispositions.

The exact parent comparison is
[`effectiveness-mfcadpp-2500-floor-seed-a492231.json`](effectiveness-mfcadpp-2500-floor-seed-a492231.json).
There are no source or test differences between that report's implementation commit and this
branch's pre-change main for the measured recognition paths.

| class | parent defining | current defining | delta | parent coverage | current coverage | delta |
|---|---:|---:|---:|---:|---:|---:|
| 6-sided pocket | 4,242 | 4,380 | +138 | 5,022 / 5,707 (0.8800) | 5,173 / 5,707 (0.9064) | +151 |
| Rectangular pocket | 2,186 | 2,186 | 0 | 4,503 / 4,895 | 4,504 / 4,895 | +1 |
| every other class | unchanged | unchanged | 0 | unchanged | unchanged | 0 |

The run returns 24 edge-open records. Twenty-three contribute exactly 138 class-15 defining
faces (six each). The remaining record, model `23645`, is not a geometric false positive: its
truthful six-wall open chain consists of five faces labelled Rectangular pocket and one face
labelled Chamfer. It contributes no class-15 defining face and one additional class-14 constituent
coverage face. We retain it rather than make a label-derived exclusion. Thus the class-15 claim
purity of this increment alone is 138 / 144 = 0.9583, with 23 / 24 occurrence alignment.

## Interpretation

The Option 1 schema fixes the original footprint defect and transfers beyond the four prototype
models to 23 class-15 occurrences. It closes 151 of the 685 class-15 faces left after floor-seeded
recovery, leaving 534. This is a useful, bounded improvement rather than a general pocket
solution. The remaining six-sided residual should be re-audited by topology gate before widening
the open-chain contract.

MFInstSeg was not inspected or run for this development increment; it remains the periodic
pseudo-blind transfer baseline.
