# Consuming unified recess geometry

`SectionRecess` is the ADR-0019 geometry contract for a constant-section recess, independent of
which algorithm found it. Use `build_section_recess_document(part).to_dict()` for a complete JSON
envelope or `RecognitionResult.section_recesses` when already running the aggregate. The builder
runs raw/caller-coordinate recognition once; it does not automatically frame the input.

## Interpret geometry, not detector names

| Accepted source proof | Unified interpretation |
| --- | --- |
| Native floor-supported pocket, `PrismaticPocket` | Closed profile, one capped end, `pocket` |
| `SectionPassage` | Closed profile, both ends open, `passage` |
| `EdgeOpenPrismaticRecess`, `EdgeOpenCircularPocket` | Physical open chain, one capped end, `edge_open_recess` |
| `RectangularBlindSlot`, `RoundBottomBlindSlot` | Physical U chain, one capped end, `edge_open_recess` |
| Extent-only `Pocket` | No automatic section conversion; an independent exact proof is required |

A section point `(u, v)` at run coordinate `s` reconstructs as
`frame.origin + u * frame.u + v * frame.v + s * frame.run`.
The end gradient gives the additional run displacement as a function of section coordinates.
Use the published low/high conditions; do not infer an opening from the sign of a world axis.
The bulge belongs to the segment starting at that vertex. The last vertex of an open chain has
zero bulge: its `opening` is an absence of wall, never another physical segment.

Use the provider's `feature_kind` and `section_shape` for conventions. In particular, four
vertices do not necessarily mean rectangular. Derive dimensions from the profile only where the
issued classification supports those dimensions. CAM setup, tool choice, accessibility and
toolpaths remain consumer decisions. Islands and non-constant support sections are not admitted.

## Evidence and counts

`bodies`, `faces` and occurrence indices belong to this one document. Retain the exact input and
face enumeration to resolve face indices. Do not compare bare indices across runs, imports or
framing. Both defining and constituent face lists refer to the same roster. The JSON geometry
goldens intentionally do not freeze face ordinals across kernel versions.

The unified inventory is a projection of accepted physical candidates, not a second set of
discoveries. Do not concatenate old family lists with `section_recesses` and count both. The
existing census retains its detector-category counts; the effectiveness scorer continues to use
the physical candidate inventory. Changing the output schema must not change benchmark denominators,
taxonomy or generate duplicate claims. Native SectionRecess pocket candidates retain the existing
shape-to-pocket benchmark mapping.

Three-decimal legacy polygon vertices are normalized on their publication grid before projection.
Collapsed edges and bounded exact backtracking may disappear, but defining and constituent face
evidence is preserved. Ambiguous topology or an excursion beyond the 0.002 mm displacement bound
raises a named `LegacySectionProjectionError`; it is not silently omitted from a successful report.

## Provider cutover status

The exact-proof families above project to the unified result. Their old public records and result
fields have **not yet been removed**. No consumer should interpret their coexistence as two
independent occurrences or a permanent compatibility guarantee.

The authored migration audit found four accepted extent-only Pocket summaries without a unified
counterpart: two in `plates_pads_levels_and_slanted_steps` and two corner notches in `slanted_steps`.
Deleting `RecognitionResult.pockets` now would discard those supported results. Publishing their
bounding boxes as closed sections would instead fabricate geometry. The final cutover therefore
requires a decision to retain explicit extent-only output, deliberately remove that output, or
implement an additional proved representation. That decision is separate from Draftwright adoption.

Run the small provider migration audit without a new benchmark or taxonomy checkpoint:

```console
uv run python -m tools.audit_section_recess_migration
uv run pytest -q -n 4 tests/test_section_recess_migration.py tests/test_section_recess_geometry_golden.py
```

The audit checks exact face-region correspondence on authored fixtures (and accepts repeated
`--step` arguments for development inputs). Evidence contained in another occurrence is reported
separately for extent-only Pocket summaries; it is not proof of geometry equivalence. Reconstruction,
orientation, serialization and ownership tests supply independent geometry validation. The test
suite also checks all 40 vendored MFCAD++ models. No MFInstSeg model is required or inspected.

The release remains unpublished. A green stack is not evidence that the extent-only cutover has
been completed; the public-surface and versioned-manifest removal must follow the explicit decision.
