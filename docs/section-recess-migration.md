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
| Corner-anchored `Pocket` with an independently proved rectangular trihedral boundary | Two-wall L chain, one capped end, `edge_open_recess` / `polygonal` |
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

The two corner notches in `slanted_steps` now have independently proved two-wall open profiles.
The proof checks three same-body, mutually adjacent, rectangular planar faces, inward-facing wall
normals, equal wall run spans, the actual floor at the capped end and exterior planar mouth faces
at the other end. It reads actual source geometry, not the old Pocket's rounded dimensions. A
perforated floor or second cap is refused. The opening joins the loose chain endpoints only as an
absence of boundary: it does not imply a diagonal wall or the floor's footprint.

Two summaries remain in `plates_pads_levels_and_slanted_steps`; individual source inspection shows:

| Region | Actual anatomy | Why not an ordinary pocket |
| --- | --- | --- |
| Under the raised pad overhang, x=32.5..42, y=-9..9, z=4..12 | Base below, pad underside above, lower-step wall at x=32.5 | Open toward +X and at both Y ends |
| Between tall wall and lower step, x=-45..-12.5, y=-25..25, z=4..12 | Opposed walls and base floor | Open toward +Z and at both Y ends |

Both are channel-like partial-support regions. Existing `RaisedPad`, `FaceLevel` and `RiserEvidence`
records describe surrounding structure, but none is an exact replacement for either void. The
current `Channel` recogniser requires an envelope-spanning run; these run intervals instead end
where a shorter wall stops. Reclassifying them as existing Channels would weaken that contract.
Representing either using an open profile with **both run ends open** would require a new admitted
interpretation under ADR 0019 and a proof of the bounded support span. That is the specific remaining
geometry question, not a reason to retain a permanent second extent-only schema. The old results
remain until their replacement or explicit retirement is decided; no bounding box is promoted to a
closed pocket and no existing recognition is silently dropped.

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
