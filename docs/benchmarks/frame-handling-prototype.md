# Part-relative frame-handling prototype

This prototype tests the underlying problem in issue #272 rather than treating the rigid-motion
sweep as an outcome. It is implemented in `tools/frame_handling_prototype.py` and deliberately
changes no package API, recogniser predicate, record schema or capability claim.

## Approach

The prototype derives unoriented direction classes from planar-face normals and cylinder axes,
weighted by analytic face area. The two strongest independent classes form a right-handed local
frame. A surface of revolution may expose only one meaningful direction; its unconstrained roll is
treated as gauge. A transient copy of the part is rotated into this frame and the existing
recognition and reconciliation stack runs unchanged.

This is normalization, not general free-axis recognition. Public records produced by the
experiment are still expressed in the normalized XYZ frame. Mapping them back to caller space—or
superseding axis-letter records with free-axis records—remains a separate contract decision.

## Golden-corpus result

Each original fixture and each Z30, X30 and X90 presentation inferred its frame independently.
Occurrence identity was compared using the face-evidence matcher from the rigid-motion sweep.

| presentation | baseline occurrences | same family | reclassified | absent | introduced |
| --- | ---: | ---: | ---: | ---: | ---: |
| Z30 | 75 | **75** | 0 | 0 | 0 |
| X30 | 75 | **75** | 0 | 0 | 0 |
| X90 | 75 | **75** | 0 | 0 | 0 |

All 20 fixtures inferred a frame. This recovers both representative failure modes: families that
previously disappeared and recess occurrences whose ownership changed between Slot/Passage or
Pocket/PrismaticPocket.

## MFCAD++ development sample

The external input was the first 100 STEP filenames in lexical order from the MFCAD++ test split
at `/app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test`. This is open development
evidence, not sealed holdout evidence. X30 was chosen as the single generic rotation because the
golden result had already shown Z30 and X30 convergence.

Two models (`10191.step`, `10299.step`) reach a pre-existing assertion that a rich passage must
reproduce its legacy projection after normalized X30 presentation. The comparable set is therefore
98 models:

| route | baseline occurrences | same family | reclassified | absent | introduced |
| --- | ---: | ---: | ---: | ---: | ---: |
| raw X30 | 568 | 217 | 10 | **341** | 2 |
| independently normalized X30 | 562 | **561** | 0 | **1** | 3 |

The differing baseline denominators are real: normalization itself changes the accepted inventory
on some axis-aligned corpus models. Across all 100 unrotated models, raw versus normalized gives
579 baseline occurrences, 566 same-family, one reclassified, 12 absent and six introduced. The
four non-refused normalized-rotation mismatches are recess fragments: three introduced Slot
fragments and one absent Slot fragment. They show that reconciliation remains sensitive to the
small numerical/topological differences produced by an OCCT transform even after the larger
world-frame gate is removed.

## Cost sample

Over the first 20 models from the same selection, inference plus copied-shape transformation took
0.236 seconds total versus 9.778 seconds for recognition of the normalized copies: **2.4%** added
work. Median times were 10.1 ms and 390.8 ms respectively. Import time was excluded.

## Honest conclusion

The direction is useful enough to continue: a 38.2% same-family retention rate on the comparable
raw X30 sample becomes 99.8%, and the complete golden corpus becomes invariant under all
three probes. Runtime is not the constraint.

It is not ready to ship. Before a production route can be accepted it must:

1. define whether consumers receive local-frame records plus the frame, or free-axis replacement
   records in caller space;
2. make recess discovery/reconciliation stable under normalization noise;
3. resolve the two passage compatibility failures without weakening fail-closed evidence;
4. specify ambiguity behavior for parts with insufficient or equally supported direction classes;
5. validate a production-shaped implementation on a larger development draw before one final
   sealed evaluation.

The sweep is therefore retained as instrumentation supporting #272. It does not close #272; this
prototype supplies the first evidence that the underlying problem is tractable and valuable.
