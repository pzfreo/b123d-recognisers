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
| `recognise_angled_steps` | Convex oblique planar slants running along one principal axis, cut into an edge of the part rather than into a wall of a recess, whose blind end is closed by an axis-aligned planar region with a geometrically triangular exterior. Smooth coplanar face splits, collinear edge splits and inner holes are normalized without changing that exterior. | Genuinely notched or curved terminal boundaries, through slants (a chamfer), and compound three-axis slants. | Functional, STEP-round-trip and normalized-region adversarial tests; over 120 MFCAD++ models, historical 100% precision and 70% instance recall before the normalized-region changes; after fixing this predicate, the 33-model frozen holdout remains at 8/8 angled-step precision with zero claims on 226 stock faces. |
| `recognise_bosses` | External full cylindrical segments on principal or slanted axes, independently per solid; includes turned ODs. | Partial cylinders, internal bores, and caller-specific “local boss” filtering. | Contract suite; simple-hole and turned-step goldens. |
| `recognise_chamfers` | Dimension-worthy external planar bevels and principal-axis conical bevels on turned stock. Called through `build_recognition_result` or `feature_census`, a planar slant with a triangular blind end is excluded — an angled step, dropped by `_reconcile.chamfers_that_are_not_angled_steps` from the claims both families write. Called directly, that planar slant is proposed, because on the face alone it is a bevel. | Compound three-axis corner bevels, internal cones such as countersinks, and faces outside leg/size gates. | Chamfer/fillet/flat golden, turned-chamfer tests, negative bevel tests, bevel-claim reconciliation tests, and 40 labelled MFCAD++ models. |
| `recognise_channels` | Floored rectangular channels spanning both longitudinal ends of one solid; after graph-proved curved end interruptions are trimmed, a paired-wall candidate's unrounded rectangular prism must be materially empty within that solid. | Bounded blind pockets, through slots, same-solid internal islands/bridges that the simple record cannot express, and cross-solid face combinations. | Open-channel golden, per-solid regressions, and H/U/rib adversaries. |
| `recognise_circular_blind_steps` | One-cap quarter-disc sectors swept along a principal axis to one source-solid envelope opening. The analytic quarter-cylinder and exact quarter-disc cap are normalized across harmless splits, the two radial stock contexts are convex, the actual sweep is materially empty, and every cylinder/cap patch is claimed. | Half/full cylinders, no- or two-cap sectors, interrupted caps or cylinders, internal run openings, tangent escapes, material-bearing sweeps, and cross-solid composites. | Constructed axes/open signs/quadrants/scales, STEP and split-region adversaries; development evidence is seven records/fourteen correctly labelled faces, followed after review by seventeen records/thirty-four correctly labelled faces on the frozen holdout. Interacted variants remain unsupported. |
| `recognise_countersinks` | Conical hole-mouth seats with a proven circular major rim, bore rim, and included angle. | General conical faces, decorative bevels, and unmatched cones. | Counterbore/countersink golden and cone rejection tests. |
| `recognise_double_d_bores` | Constant, principal-axis, through double-D voids with two opposed common-circle profiles and a material-free connecting prism. | Blind recesses, obrounds, lenses, arbitrary line/arc loops, non-principal axes, mismatched ends, and cross-solid pairing. | Double-D golden plus capability-negative tests. |
| `recognise_face_levels` | Horizontal planar face levels, optionally area-filtered, with XY support spans. | Slanted/curved faces and semantic decisions about which levels form dimensions. | Plate/level and slanted-step goldens. |
| `recognise_fillets` | Dimension-worthy external cylindrical edge blends and principal-axis toroidal blends on turned stock. | Compound corner rounds, internal rounds, and radii outside configured gates. | Chamfer/fillet/flat golden, turned-fillet tests, and adjacency bound regression. |
| `recognise_flats` | Planar truncations of proven round stock, including single-D and opposed flat evidence. | Arbitrary planar faces without a cylindrical-stock substrate. | Chamfer/fillet/flat and double-D evidence. |
| `recognise_grooves` | External reduced-OD bands between two larger coaxial shaft bands, reached directly or across chamfered or radiused lead-ins; `width` is the flat floor, excluding the lead-ins. | Internal grooves, end reliefs without two larger neighbours, and non-turned recesses. | Turned-step/groove golden; chamfered- and radiused-lead-in tests. |
| `recognise_hole_patterns` | Same-spec hole bolt circles, constant-pitch linear arrays, and complete rectangular grids; greedy largest-first ownership. | Pairs, incomplete lattices as grids, uneven circles/rows, mixed specs, and a hole belonging to multiple returned patterns. | Bolt-circle/grid golden, pattern regressions, and scaling sentinel. |
| `recognise_holes` | Coaxial internal full-cylinder stacks with through/flat/drill-point/unknown bottoms and injected countersink composition. | Slot end caps, partial cylinders, far-side counterbores, and automatic countersink rediscovery when none is injected. | Hole/counterbore/cross-bore goldens and edge regressions. |
| `recognise_passages` | Closed rings of logical planar walls running through the material, uncapped at both ends, with three or more sides and one shared span. Multiple directly zero-angle coplanar STEP patches normalize only when their actual union is one complete hole-free rectangle; every source patch is claimed. Pre-existing singleton walls may contain an interruption from another intersecting void, yielding truthful maximal constant-section segments. | Capped voids (a pocket); genuinely unequal or non-rectangular multi-patch wall regions that the single constant `section`/`length` record cannot express. Direct output is a candidate inventory. In the aggregate, a complete normalized four-wall ring defeats patch-local Slot fragments, but yields to a Slot that spans and dimensions the same whole void; a non-rectangular ring defeats paired-wall fragments assembled inside it. | Passage functional tests, sewn/STEP-round-trip wall-region fixtures, axis/scale cases and offset/branch adversaries; over 120 MFCAD++ models, historical 100% precision and 51% instance recall — a synthetic corpus scored against its own labels, so read the recall as a heuristic's reach and not as a bound on real parts. |
| `recognise_plates` | Thin prismatic slabs supported by opposed planar faces and configured area/thickness gates. | The single envelope plate, curved/non-prismatic shells, and slabs below the evidence gates. | Plate/level golden and plate tests. |
| `recognise_pocket_patterns` | Constant-pitch linear and complete rectangular arrays of identical, coplanar, equally oriented `Pocket` records. | Bolt circles, pairs, mixed sizes/opening faces/depth planes, and incomplete grids. | Blind-pocket golden and pattern-negative tests. |
| `recognise_pockets` | Floored rectangular recesses bounded within one solid; elongated blind slots are the same record class. After graph-proved curved end interruptions are trimmed, a paired-wall candidate's unrounded rectangular prism must be materially empty within that solid. | Through slots, open-ended channels, non-rectangular floors, same-solid internal islands/bridges that the simple record cannot express, and cross-solid composites. | Blind-pocket golden, floor/opening regressions, blind-U/rib adversaries, and MFCAD++/NIST change evidence. |
| `recognise_polygonal_bosses` | Attached regular hexagonal Z-axis bosses with six outward side faces, one A/F value, a support cap, and a top cap. | Other side counts, X/Y axes, whole-stock prisms, inward recesses, incomplete rings, and cross-solid assemblies. | Polygonal-boss golden plus capability-negative tests. |
| `recognise_polygonal_stock` | Exactly one solid consisting solely of a regular hexagonal Z-axis prism’s six sides and two caps. | Other side counts or axes, attachments, holes, chamfers, missing/extra faces, and multi-solid assemblies. | Polygonal-stock golden plus capability-negative tests. |
| `recognise_rectangular_pads` | Bounded rectangular +Z islands with a filled XY footprint and body-local support. | Full-span steps, non-rectangular/perforated tops, -Z/side pads, and cross-solid support. | Plate/pad/level golden and pad tests. |
| `recognise_prismatic_pockets` | Floored recesses of any planar cross-section, found by walking the closed ring of logical walls: a triangular, hexagonal or rectangular pocket alike. Directly smooth coplanar wall patches normalize only when their union is one complete hole-free rectangle. Reports the section, so shape survives into the record, and claims every source patch. | Obround recesses, whose cylindrical ends form no closed planar ring — `recognise_pockets` reaches those; genuinely interrupted/piecewise wall regions; voids open at both ends (a passage) or capped at both (an enclosed cavity, unreachable by a tool). In the aggregate, a four-wall ring yields to a paired `Pocket`; a non-rectangular ring survives and defeats paired-wall fragments inside it. | Prismatic-pocket functional and split-wall tests; `triangular_and_hex_pockets` golden; measured over 250 MFCAD++ models, capped rings historically reach 80 triangular, 72 hexagonal and 61 rectangular pockets where wall pairing reaches essentially only the rectangular ones. |
| `recognise_repeating_radial_profiles` | Complete outer-wire profiles invariant under a proved sector rotation, independently per solid. | Gear semantics, partial-repeat inference, inner-only profiles, and cross-solid cycles. | Repeating-radial-profile and traversal-order goldens. |
| `recognise_risers` | Full-span principal in-plane step-riser evidence, including bounded slanted transitions, independent of a level set. | Pads, pocket walls, partial corner notches, and end-treated/inset risers outside tolerance; shoulder selection remains a consumer projection. | Plate/level and slanted-step goldens. |
| `recognise_round_bottom_blind_slots` | One-cap, edge-open constant U-section recesses: a positive-width planar floor tangent to two equal-radius analytic quarter cylinders, with identical cap-to-envelope span, exact matching cap, convex opening/depth context and materially empty sweep. Direct coplanar and coaxial-cylinder subdivisions normalize and every defining source patch is claimed. | Rectangular/obround pockets, through or two-cap U sections, unequal/non-quarter radii, cap holes or continuation, branches, tangent-blend escapes, and same-solid material inside the sweep. | Constructed axes/open signs/scales, STEP, split cap/floor/cylinders/context, compound and family-confusion adversaries; development anatomy is two records/eight correctly labelled faces in one model, followed by five records/twenty correctly labelled faces on the frozen holdout. |
| `recognise_semicircular_bottom_blind_slots` | One-cap, edge-open constant sections formed by two equal straight planar legs tangent to one analytic half-cylinder. The three logical walls share one cap-to-envelope span, the cap exactly matches the semicircular profile, stock context is convex, and the swept profile is materially empty. Direct coplanar and coaxial subdivisions normalize and all defining patches are claimed. | Flat-bottom and quarter-cylinder profiles; through or two-cap sections; unequal legs, radii or spans; incomplete/chamfer-mediated caps; extra closures, holes, notches, branches, tangent escapes, and same-solid material inside the sweep. | Constructed axes/open signs/scales, STEP and split-region adversaries; development evidence is two records/eight correctly labelled faces, with interacted variants deliberately unsupported; after review, frozen-holdout evidence is three records/twelve correctly labelled faces. |
| `recognise_slot_patterns` | Constant-pitch linear and complete rectangular arrays of identical through `Slot` records on the same through plane. | Bolt circles, pairs, mixed sizes/planes, and incomplete grids. | Straight/obround-slot golden and pattern-negative tests. |
| `recognise_slots` | Enclosed through-slots proved by opposed walls or qualifying obround end caps, independently per solid. A planar pair must have agreeing AAG arcs into shared boundary neighbours, or belong to one smooth-connected boundary component when STEP has fragmented that boundary (the gAAG-equivalent query); after graph-proved curved end interruptions are trimmed, its unrounded rectangular prism must be materially empty. | Floored pockets, open-ended channels, merely narrow envelope sections, internal islands/bridges that the simple record cannot express, cross-solid composites, and opposed pairs assembled from different sides of a polygonal void. Aggregate reconciliation gives complete pocket and non-rectangular passage rings precedence over paired-wall fragments. | Straight/obround-slot golden, AAG-coherence mutation, H/U/thin-rib/scale adversaries, frozen MFCAD++ holdout, NIST corrections, and recess-reconciliation regressions. |
| `recognise_turned_steps` | Two or more contiguous coaxial external cylindrical segments forming a stepped shaft on one axis. | Plain cylinders, non-turned parts, disconnected/mixed-axis segments, and drafting interpretation beyond the geometry profile. | Turned-step/groove golden and turned-step tests. |
| `recognise_through_steps` | Rectangular open-profile removals spanning one source solid: two orthogonal principal planar regions, one complete concave run seam, convex terminal context at both ends, distinct envelope-reaching legs, and an exactly empty removed prism. Coplanar representation splits are normalized and all source patches claimed. | Two-sided and slanted through steps; capped/blind steps; channels and pockets with additional concave walls; unequal spans, internal leg endings, non-rectangular region boundaries, and ambiguous branches. An additive L-solid is indistinguishable from the same final subtractive shape. | Constructed rotations/mirrors/scales, STEP round-trip, split-patch, compound and family-confusion adversaries; development evidence is 3 records/6 correctly labelled faces, followed by 3 records/6 correctly labelled faces on the frozen 33-model holdout. |

## Analytic surfaces are a precondition for every recogniser

Every recogniser above classifies faces by their surface type. A face is a hole wall because it is
a `GeomAbs_Cylinder`, a floor because it is a `GeomAbs_Plane`. Imported geometry therefore has to
arrive with its analytic surfaces intact.

STEP carries analytic surfaces, and `tests/test_step_round_trip.py` proves the file boundary does
not disturb them: all twenty golden fixtures exported to STEP and re-imported reproduce their
pinned records exactly, with planes and cylinders still typed as such.

That evidence covers geometry written by this project's own OCCT-based exporter. It shows that
passing through a STEP file is not itself lossy; it does not measure any particular third-party
CAD system's export, and no such corpus is checked in. The requirement is the same either way — a
file whose faces arrive as analytic surfaces recognises, one whose faces arrive as B-splines does
not — but the proven evidence is the round trip, not a survey of emitters.

Geometry whose faces are B-splines is **excluded, in every family at once**. A NURBS-only export
can describe a face that is exactly a cylinder while typing it `GeomAbs_BSplineSurface`; no
recogniser here inspects the underlying geometry to discover that, so recognition returns nothing
rather than degrading partially. This is a whole-package boundary rather than a per-row exclusion,
and it is held by test as a contrast against the analytic result. Supporting it would mean fitting
analytic surfaces to B-spline faces and bounding the residual — a recognition-behaviour change
under the usual evidence requirements, not a tolerance adjustment.

## Measured against third-party labelled corpora

The exclusions above were written from this project's own fixtures. Two external per-face
labelled corpora now test them against models nobody here authored — [MFCAD](https://github.com/hducg/MFCAD)
(15,488 models) and [MFCAD++](https://doi.org/10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823)
(59,665 models, 24 feature classes, 3–10 *interacting* features per model). Neither is checked
in whole, per `migration/PARITY.md`; both are freely downloadable. Two small MFCAD++ subsets
are vendored under `tests/corpus`, each with the rule that selected it: forty models the
predicates here were shaped by, and thirty-three that were held out.

**The exclusions hold, and they are the dominant failure mode.** On MFCAD, per-class recognition
tracks how axis-aligned a class's faces are: classes whose feature faces are 100% axis-aligned are
recognised in every model, while the three mostly-oblique classes return nothing in 78% of theirs.
Before the AAG expansions recorded below, fitting labelled faces to emitted records across 400
MFCAD++ models reproduced it — every rectangular class recognised, while Triangular passage,
6-sided passage, Triangular pocket, Circular through slot, 2-sided through step, Horizontal
circular end blind slot and Slanted through step produced essentially nothing. This is what
"non-rectangular floors", "Slanted/curved faces" and
"non-principal axes" above mean in practice, on parts written by someone else.

**One figure is about geometry this project was not fitted to.** Everything above comes from a
corpus that has already been used to change predicates, which makes it regression evidence rather
than a generalisation estimate. `tests/corpus/mfcadpp_holdout` is thirty-three models drawn from
the MFCAD++ *val* split — disjoint from the vendored design set by construction — covering the
twenty classes the design set does not target. It was scored once, after the last predicate
change. Angled steps: eight records, every one on a face labelled a triangular blind step, with
forty-eight triangular-pocket faces and twenty-two slanted-through-step faces available to go
wrong on. Stock: 226 faces, none claimed. It found one defect before it was sealed — a
right-triangular pocket wall reported as an angled step — which is now rejected by a gate and
pinned by a fixture. Scoring that set again is fine; changing a predicate to satisfy it is not,
and would cost a fresh draw.

**Curved families recognise.** MFCAD is planar-only in all 15 classes, so it cannot exercise
holes, fillets, bosses, countersinks, grooves or turned steps at all. MFCAD++ can, and does:
Through hole and Blind hole yield hole records, complete Circular blind steps yield their dedicated
record (while direct fillet discovery still sees the local radius), and O-ring yields bosses and
holes.

Three limits on how far this evidence reaches:

- **It is not a recall score.** These corpora use their own feature vocabulary. Several classes
  are recognised under a *different* family than the corpus names — O-ring as boss, for example —
  which is a taxonomy mismatch, not a defect, and makes naive cross-corpus
  percentages meaningless. See *Naming* below for how far that vocabulary is adopted here.
- **The labels are single-assignment, so they mislead at feature intersections.** MFCAD++ gives
  each face exactly one feature label. Where two features meet, a wall belonging to both is
  assigned to one of them, and a wall bounded by raw billet is assigned to *Stock* — which means
  "assigned to no feature", not "no feature touches this". Measured: `recognise_passages` reports
  a genuine 6-sided passage on `11251.step` whose six walls carry **five different labels**, two
  of them *Stock*. Any per-face score against these labels therefore understates a family that is
  right about an intersecting feature, and a recogniser tuned to raise such a score would be
  fitted to the corpus rather than to the geometry.
- **Attribution is per-face where a family writes claims, and statistical elsewhere.** A
  recogniser handed a claim ledger records the faces each record was established by, so its
  records can be scored against the labels of the faces they actually consumed rather than
  fitted. `tools/per_face_scan.py` does exactly that, over the nine claiming families these
  corpora can reach — `recognise_slots`, `recognise_pockets`, `recognise_prismatic_pockets`,
  `recognise_passages`, `recognise_chamfers`, `recognise_angled_steps`,
  `recognise_through_steps`, `recognise_round_bottom_blind_slots` and
  `recognise_semicircular_bottom_blind_slots`. Grooves and turned
  steps write claims too and are absent from these figures for a different reason: all 50
  vendored MFCAD++ and NIST parts are milled prismatic and report no turned steps at all. The
  figures quoted as precision — 100% for angled steps, 44% → 78% for chamfers over 120 models —
  are counted per face rather than fitted. The chamfer figure is the *reconciled* answer, which is what the
  aggregate and the census report; called directly the recogniser proposes a blind step's slant
  as well and scores lower — 50% against 79% over the 40 vendored models — for the reason the
  row above gives.

  Every other family still has to be fitted: it writes no claims, so the MFCAD++ figures for it
  come from comparing record counts against labelled-face counts across models rather than from
  observing ownership. That fit is strong for holes, fillets and bosses and weak for plates and
  countersinks; only the former should be read. The difference between the two halves of this
  bullet is the difference between measuring a recogniser and estimating it, and closing it is a
  matter of writing claims in the remaining families rather than of new machinery.
- **Synthetic parts, generated features.** Both corpora are procedurally built, and
  synthetic-to-real transfer is an open research problem. They are sound as a false-negative
  detector and unsound as ground truth about real drawings.

## Naming

**A new family takes MFCAD++'s name for the thing it recognises, where MFCAD++ has one.**
Inventing a parallel vocabulary for shapes a published corpus has already named costs
comparability and buys nothing, and every figure in the section above has to be footnoted when
the two disagree.

**An existing public record keeps its name.** `Slot`, `Pocket`, `Chamfer` and the rest are
drawing-callout vocabulary — what a machinist reading the output calls the feature — and ADR 0005
makes them a versioned cross-repository contract with a downstream consumer. Renaming them to
match a machine-learning label set is a breaking change bought with the wrong currency. Where the
two vocabularies name the same shape differently, the mapping is recorded here rather than
resolved by moving the code.

MFCAD++'s class leads in the table below, because that is the direction the policy runs: theirs is
what a new family adopts, and this is where the existing names are reconciled to it.

| MFCAD++ class | reported here as | note |
| --- | --- | --- |
| Rectangular through slot; Circular through slot | Slot | slots are through by definition here |
| Rectangular pocket | Pocket | blind by definition here |
| Triangular pocket; 6-sided pocket | PrismaticPocket | any planar cross-section, found by walking the ring; `Pocket` cannot express a non-rectangular footprint |
| **Circular end pocket** | Pocket | an obround blind recess; direct recognisers may propose competing paired walls, but aggregate boundary reconciliation keeps the floored pocket |
| Rectangular blind step | Pocket | a floored recess open at one edge reads as a corner notch |
| Rectangular / Triangular / 6-sided passage | Passage | one family, three shapes, not distinguished |
| Triangular blind step | AngledStep | |
| Chamfer | Chamfer | |
| Round | Fillet | |
| Circular blind step | CircularBlindStep | The aggregate gives the complete cap-to-envelope sector precedence over its local Fillet proposal; direct Fillet discovery remains compatible. |
| O-ring | BossRecord | |
| Through hole; Blind hole | HoleRecord | |
| Rectangular through step | ThroughStep | Bounded orthogonal two-region subset |
| Horizontal circular end blind slot | RoundBottomBlindSlot | Bounded edge-open U-profile subset; the corpus orientation word does not limit the axis-generic record |
| 2-sided / Slanted through step | — | **unrecognised**; two-sided examples expose a local concave tripod whose terminal material face extends beyond the feature footprint, requiring a 3-D skeleton record and sub-face/context evidence rather than whole-face claims; slanted variants need a separate contract |
| — | Channel | full-span floored recess; no MFCAD++ counterpart |

**A contested face is not decided by MFCAD++'s taxonomy.** Its labels are single-assignment and
therefore inconsistent exactly where two families disagree — the case a tiebreaker would be asked
to settle. Measured: `recognise_passages` reports a genuine 6-sided passage on `11251.step` whose
six walls carry **five different labels**, two of them *Stock*. Deferring to the corpus there
would have deleted a correct record. Which family owns a face is decided by the reconciler from
the claims, under ADR 0003, and by evidence about the geometry rather than about the label.

## Public record contract audit

The record audit below distinguishes recogniser output from helper/projection
records. Fields describe evidence already proved by current code; they are not an
invitation to construct values outside that evidence and call them recognized.

| Public record | Implemented contract boundary |
| --- | --- |
| `AngledStep` | One convex oblique slant closed by a triangular blind end; `length` is how far it runs before that end. |
| `BoltCircle` | At least three same-spec holes, equally spaced on one circle. |
| `BossRecord` | One external full-cylinder segment; its vector axis is not restricted to a world-axis string. |
| `Chamfer` | One qualifying external, single-principal-axis planar bevel. |
| `Channel` | One floored rectangular recess open at both ends of its longitudinal solid envelope. |
| `CircularBlindStep` | One exact quarter-disc sector swept from a blind cap to a source-solid run opening; transverse axes and signs preserve its quadrant. |
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
| `Passage` | One closed uncapped ring of walls; `sides` is the polygon, so a triangular passage reports 3, and `section` gives its corners so the shape can be dimensioned rather than only named. |
| `Plate` | One qualifying thin prismatic slab represented by its thickness axis and bounds. |
| `PrismaticPocket` | One floored recess of constant planar cross-section, open at one end; `sides` and `section` carry the shape that `width`/`length` cannot. |
| `Pocket` | One floored bounded rectangular recess; elongated blind slots intentionally use this same class. |
| `PocketArray` | At least three identical compatible pockets on one constant-pitch line. |
| `PocketGrid` | A complete rectangular lattice of identical compatible pockets. |
| `PolygonalBoss` | One attached regular hexagonal Z-axis boss; output is exactly `axis="z"`, `side_count=6`. |
| `PolygonalStock` | One whole regular hexagonal Z-axis prism; output is exactly `axis="z"`, `side_count=6`. |
| `RaisedPad` | One bounded rectangular +Z island with footprint and height evidence. |
| `RectGrid` | A complete rectangular lattice of same-spec holes with the documented row/column basis convention. |
| `RepeatingRadialProfile` | Geometry-only proof of complete outer-profile rotational repetition, not gear semantics. |
| `RiserEvidence` | One full-span candidate riser before any consumer-specific level projection. |
| `RoundBottomBlindSlot` | One edge-open, one-cap constant U-section recess; explicit run/open direction, section axes, quarter-cylinder radius and flat width. |
| `SemicircularBottomBlindSlot` | One edge-open, one-cap section with two straight legs and one semicircular bottom; explicit run/open direction, section axes, radius and leg depth. |
| `Slot` | One enclosed through-slot; no floor and no open longitudinal end. |
| `SlotArray` | At least three identical compatible through-slots on one constant-pitch line. |
| `SlotGrid` | A complete rectangular lattice of identical compatible through-slots. |
| `StepShoulder` | A pure projection result from `RiserEvidence` plus a caller-supplied level set, not a recogniser return. |
| `TurnedProfile` | A consumer aggregate built from `TurnedStep` values, not a recogniser return. |
| `TurnedStep` | One self-contained coaxial shaft segment; recognition requires a multi-step profile. |
| `ThroughStep` | One open-profile step spanning a source solid; the current recogniser emits canonical three-point rectangular sections only. |

`RecognitionResult` is the frozen orchestration inventory rather than a `Record`
subclass. It owns every public recogniser family, preserves classification-gated
empty inventories explicitly, and makes no claim that every geometry fact has
Draftwright IR, DSL, code-generation, drawing, or completeness semantics.

Every public `recognise_*` export must appear exactly once in the recogniser table above. CI derives
that export inventory from the installed public module rather than trusting this page,
so adding a recogniser without an explicit capability claim fails closed even before the
versioned manifest is implemented.
