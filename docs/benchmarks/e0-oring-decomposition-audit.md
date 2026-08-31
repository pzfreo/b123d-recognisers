# E0 O-ring decomposition audit

Issue [#360](https://github.com/pzfreo/b123d-recognisers/issues/360) tests whether
MFCAD++/MFInstSeg class 11, `O-ring`, can be mapped from `bosses` to both `bosses` and `holes`.
The complete result is negative: the dominant annular motif does decompose that way, but the class
also contains interrupted cylindrical fragments and one cylindrical Fillet defining face. Taxonomy
v4 therefore remains authoritative. No production behavior or public ownership changes.

## Complete lexical-500 audit

The published test archive's exact lexical selection contains 147 models / 669 class-11 faces:
453 cylinders and 216 planes in 207 exact label-connected components.

| labelled component geometry | count |
| --- | ---: |
| Two cylinders and one plane | 173 |
| Three cylinders and one plane | 16 |
| One cylinder and one plane | 6 |
| One cylinder only | 4 |
| Five cylinders and two planes | 2 |
| Four cylinders and one plane | 2 |
| Other intersected variants | 4 |

Accepted aggregate evidence claims 211 class-11 faces as Boss defining faces and 230 as Hole
defining faces. It also claims 21 as structural FaceLevel evidence, one as Fillet evidence and one
as Plate evidence. There are 464 distinct claimed faces and 205 unclaimed faces. MFCAD++ has no
instance relation, so the component counts are descriptive topology evidence, not instance recall.
No individual MFInstSeg model was inspected.

## Representative ownership proof

Face indices are zero-based imported-face positions, matching the scorer and lexical STEP labels.
`FORWARD` cylindrical orientation denotes material radially inside the analytic cylinder;
`REVERSED` denotes material radially outside it. A full native cylinder has a 2π U span.

| case | model and labelled faces | observed ownership |
| --- | --- | --- |
| Native annulus | `10015`: face 15 REVERSED cylinder, radius 2.551188, U span 6.283185; face 18 plane; face 19 FORWARD cylinder, radius 1.953636, U span 6.283185 | face 15 is Hole defining evidence, face 19 is Boss defining evidence, and face 18 is outside both defining sets |
| Intersected annulus | `10096`: component faces 31/32 REVERSED cylinders, face 36 plane, face 38 FORWARD cylinder | faces 31/32 are Hole defining evidence and face 36 remains unowned; face 38 has only a 2.267717-radian span and is not accepted as a Boss |
| Compound labelled component | `10170`: full faces 17/18/19 plus intersecting faces 21/22/23/25 | faces 17 and 19 are respectively Hole and Boss evidence and plane 18 is unowned; interrupted REVERSED face 21 is unclaimed, plane 22 is unowned, and FORWARD faces 23/25 are Boss evidence |
| Contradictory cylinder | `10684`: REVERSED faces 13/14, FORWARD face 31, plane 32 | faces 13/14 are Hole evidence and plane 32 is unowned, but face 31 is accepted Fillet evidence (radius 0.609760, U span 3.195073), not Boss evidence |

Across the full selection, twelve class-11 cylinders are outside accepted Boss/Hole defining
ownership. Eleven are unclaimed partial walls in models `10096`, `10155`, `10170`, `11724`,
`12062`, and `12110`, with U spans from 0.232260 to 3.023651 radians. The twelfth is the
Fillet-owned face 31 in `10684`, with U span 3.195073 radians. These are not annular caps that can
remain consulted context: they are cylinders carrying the class label, and assigning them to Boss
or Hole would require weakening the existing full-cylinder/material ownership contracts.

## Decision and measured counterfactual

The proposed many-to-many mapping is rejected under #360's closure condition. The package does
legitimately recognise many inner O-ring walls as Holes, but class 11 is not uniformly equivalent
to the existing Boss/Hole decomposition. Adding `holes` would hide that heterogeneity and make a
comparison taxonomy claim that the public contracts do not support. Immutable taxonomy v4 and its
exact report remain unchanged.

For audit only, an unshipped experimental mapping at commit `ec8b003` was run over the same 500
models. It changed class-11 agreement from Boss-only 211/211 precision and 211/669 recall to
441/854 precision and 441/669 recall, mapped class-11 records from 199 to 400, and total mismatches
from 3,237 to 3,007. All physical records and non-mapping evidence were identical. Those improved
agreement figures are not adopted because they do not satisfy the geometric contract above; the
experimental taxonomy and report are deliberately not published as canonical evidence.

MFInstSeg's rounded Boss/Hole face-versus-instance pattern remains useful directional evidence,
but its O-ring metrics must not be reinterpreted or regenerated with the rejected mapping. A future
mapping change would require an explicit partial/decomposed-class comparison contract capable of
representing the interrupted and Fillet-owned variants without asserting false physical ownership.
