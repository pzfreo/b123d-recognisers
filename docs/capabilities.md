# Proven recognition capability

This inventory states what the current recognisers prove, rather than what their
records might someday be able to represent. It is the reviewed input to the
machine-readable capability contract specified by
[ADR 0005](adr/0005-versioned-cross-repository-capability-contract.md). The installed package
exposes the implemented format-1 document without requiring access to package internals:

```python
from b123d_recognisers import capability_manifest

manifest = capability_manifest(format_version=1)
```

Downstream CI can export the identical deterministic JSON with
`b123d-recognisers-capabilities --format-version 1`. Unknown format versions fail closed. This
page remains the human explanation of the machine-readable boundary.

“Excluded” means that current recognition deliberately returns no record. It does not
mean the geometry is invalid or that support is promised. Expanding an excluded class
is a recognition-behaviour change requiring independent fixtures, semantic goldens,
compatibility review, and release notes.

| Recogniser | Proven current scope | Explicitly excluded or deferred | Primary evidence |
| --- | --- | --- | --- |
| `recognise_bosses` | External full cylindrical segments on principal or slanted axes, independently per solid; includes turned ODs. | Partial cylinders, internal bores, and caller-specific “local boss” filtering. | Contract suite; simple-hole and turned-step goldens. |
| `recognise_chamfers` | Dimension-worthy external planar bevels running along one principal axis. | Compound three-axis corner bevels and faces outside leg/size gates. | Chamfer/fillet/flat golden and negative bevel tests. |
| `recognise_channels` | Floored rectangular channels spanning both longitudinal ends of one solid. | Bounded blind pockets, through slots, and cross-solid face combinations. | Open-channel golden and per-solid regressions. |
| `recognise_countersinks` | Conical hole-mouth seats with a proven circular major rim, bore rim, and included angle. | General conical faces, decorative bevels, and unmatched cones. | Counterbore/countersink golden and cone rejection tests. |
| `recognise_double_d_bores` | Constant, principal-axis, through double-D voids with two opposed common-circle profiles and a material-free connecting prism. | Blind recesses, obrounds, lenses, arbitrary line/arc loops, non-principal axes, mismatched ends, and cross-solid pairing. | Double-D golden plus capability-negative tests. |
| `recognise_face_levels` | Horizontal planar face levels, optionally area-filtered, with XY support spans. | Slanted/curved faces and semantic decisions about which levels form dimensions. | Plate/level and slanted-step goldens. |
| `recognise_fillets` | Dimension-worthy external cylindrical edge blends running along one principal axis. | Compound corner rounds, internal rounds, and radii outside configured gates. | Chamfer/fillet/flat golden and adjacency bound regression. |
| `recognise_flats` | Planar truncations of proven round stock, including single-D and opposed flat evidence. | Arbitrary planar faces without a cylindrical-stock substrate. | Chamfer/fillet/flat and double-D evidence. |
| `recognise_grooves` | External reduced-OD bands between two contiguous larger coaxial shaft bands. | Internal grooves, end reliefs without two larger neighbours, and non-turned recesses. | Turned-step/groove golden. |
| `recognise_hole_patterns` | Same-spec hole bolt circles, constant-pitch linear arrays, and complete rectangular grids; greedy largest-first ownership. | Pairs, incomplete lattices as grids, uneven circles/rows, mixed specs, and a hole belonging to multiple returned patterns. | Bolt-circle/grid golden, pattern regressions, and scaling sentinel. |
| `recognise_holes` | Coaxial internal full-cylinder stacks with through/flat/drill-point/unknown bottoms and injected countersink composition. | Slot end caps, partial cylinders, far-side counterbores, and automatic countersink rediscovery when none is injected. | Hole/counterbore/cross-bore goldens and edge regressions. |
| `recognise_plates` | Thin prismatic slabs supported by opposed planar faces and configured area/thickness gates. | The single envelope plate, curved/non-prismatic shells, and slabs below the evidence gates. | Plate/level golden and plate tests. |
| `recognise_pocket_patterns` | Constant-pitch linear and complete rectangular arrays of identical, coplanar, equally oriented `Pocket` records. | Bolt circles, pairs, mixed sizes/opening faces/depth planes, and incomplete grids. | Blind-pocket golden and pattern-negative tests. |
| `recognise_pockets` | Floored rectangular recesses bounded within one solid; elongated blind slots are the same record class. | Through slots, open-ended channels, non-rectangular floors, and cross-solid composites. | Blind-pocket golden and floor/opening regressions. |
| `recognise_polygonal_bosses` | Attached regular hexagonal Z-axis bosses with six outward side faces, one A/F value, a support cap, and a top cap. | Other side counts, X/Y axes, whole-stock prisms, inward recesses, incomplete rings, and cross-solid assemblies. | Polygonal-boss golden plus capability-negative tests. |
| `recognise_polygonal_stock` | Exactly one solid consisting solely of a regular hexagonal Z-axis prism’s six sides and two caps. | Other side counts or axes, attachments, holes, chamfers, missing/extra faces, and multi-solid assemblies. | Polygonal-stock golden plus capability-negative tests. |
| `recognise_rectangular_pads` | Bounded rectangular +Z islands with a filled XY footprint and body-local support. | Full-span steps, non-rectangular/perforated tops, -Z/side pads, and cross-solid support. | Plate/pad/level golden and pad tests. |
| `recognise_repeating_radial_profiles` | Complete outer-wire profiles invariant under a proved sector rotation, independently per solid. | Gear semantics, partial-repeat inference, inner-only profiles, and cross-solid cycles. | Repeating-radial-profile and traversal-order goldens. |
| `recognise_risers` | Full-span principal in-plane step-riser evidence, including bounded slanted transitions, independent of a level set. | Pads, pocket walls, partial corner notches, and end-treated/inset risers outside tolerance; shoulder selection remains a consumer projection. | Plate/level and slanted-step goldens. |
| `recognise_slot_patterns` | Constant-pitch linear and complete rectangular arrays of identical through `Slot` records on the same through plane. | Bolt circles, pairs, mixed sizes/planes, and incomplete grids. | Straight/obround-slot golden and pattern-negative tests. |
| `recognise_slots` | Enclosed through-slots proved by opposed walls or qualifying obround end caps, independently per solid. | Floored pockets, open-ended channels, merely narrow envelope sections, and cross-solid composites. | Straight/obround-slot golden and slot regressions. |
| `recognise_turned_steps` | Two or more contiguous coaxial external cylindrical segments forming a stepped shaft on one axis. | Plain cylinders, non-turned parts, disconnected/mixed-axis segments, and drafting interpretation beyond the geometry profile. | Turned-step/groove golden and turned-step tests. |

## Public record contract audit

The record audit below distinguishes recogniser output from helper/projection
records. Fields describe evidence already proved by current code; they are not an
invitation to construct values outside that evidence and call them recognized.

| Public record | Implemented contract boundary |
| --- | --- |
| `BoltCircle` | At least three same-spec holes, equally spaced on one circle. |
| `BossRecord` | One external full-cylinder segment; its vector axis is not restricted to a world-axis string. |
| `Chamfer` | One qualifying external, single-principal-axis planar bevel. |
| `Channel` | One floored rectangular recess open at both ends of its longitudinal solid envelope. |
| `CounterBore` | One coaxial cylindrical hole step used as either the `cbore` or `spotface` field of `HoleRecord`. |
| `CounterSink` | One proved conical seat at a matching cylindrical bore mouth. |
| `DoubleDBore` | One constant principal-axis through double-D void; recogniser output always has `through=True`. |
| `FaceLevel` | One horizontal Z level plus optional XY support spans; it does not claim a dimension requirement. |
| `Fillet` | One qualifying external, single-principal-axis cylindrical edge blend. |
| `Flat` | One planar truncation corresponding to a proved cylindrical-stock substrate. |
| `Groove` | One external reduced-OD band between larger coaxial neighbours. |
| `HoleRecord` | One internal full-cylinder stack with optional near-side hole treatments and one classified bottom. |
| `HoleSpec` | A normalized grouping key derived from `HoleRecord`; through depth is intentionally absent. |
| `LinearArray` | At least three same-spec holes on one constant-pitch line, ordered along `direction`. |
| `Plate` | One qualifying thin prismatic slab represented by its thickness axis and bounds. |
| `Pocket` | One floored bounded rectangular recess; elongated blind slots intentionally use this same class. |
| `PocketArray` | At least three identical compatible pockets on one constant-pitch line. |
| `PocketGrid` | A complete rectangular lattice of identical compatible pockets. |
| `PolygonalBoss` | One attached regular hexagonal Z-axis boss; output is exactly `axis="z"`, `side_count=6`. |
| `PolygonalStock` | One whole regular hexagonal Z-axis prism; output is exactly `axis="z"`, `side_count=6`. |
| `RaisedPad` | One bounded rectangular +Z island with footprint and height evidence. |
| `RectGrid` | A complete rectangular lattice of same-spec holes with the documented row/column basis convention. |
| `RepeatingRadialProfile` | Geometry-only proof of complete outer-profile rotational repetition, not gear semantics. |
| `RiserEvidence` | One full-span candidate riser before any consumer-specific level projection. |
| `Slot` | One enclosed through-slot; no floor and no open longitudinal end. |
| `SlotArray` | At least three identical compatible through-slots on one constant-pitch line. |
| `SlotGrid` | A complete rectangular lattice of identical compatible through-slots. |
| `StepShoulder` | A pure projection result from `RiserEvidence` plus a caller-supplied level set, not a recogniser return. |
| `TurnedProfile` | A consumer aggregate built from `TurnedStep` values, not a recogniser return. |
| `TurnedStep` | One self-contained coaxial shaft segment; recognition requires a multi-step profile. |

`RecognitionResult` is the frozen orchestration inventory rather than a `Record`
subclass. It owns every public recogniser family, preserves classification-gated
empty inventories explicitly, and makes no claim that every geometry fact has
Draftwright IR, DSL, code-generation, drawing, or completeness semantics.

Every public `recognise_*` export must appear exactly once in the recogniser table above. CI derives
that export inventory from the installed public module rather than trusting this page,
so adding a recogniser without an explicit capability claim fails closed even before the
versioned manifest is implemented.
