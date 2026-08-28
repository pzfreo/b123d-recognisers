# Proven recognition capability

This inventory states what the current recognisers prove, rather than what their
records might someday be able to represent. It is the reviewed input to the
machine-readable capability contract specified by
[ADR 0005](adr/0005-versioned-cross-repository-capability-contract.md). The installed package
exposes the implemented format-2 document without requiring access to package internals:

```python
from b123d_recognisers import capability_manifest

manifest = capability_manifest(format_version=2)
```

Downstream CI can export the identical deterministic JSON with
`b123d-recognisers-capabilities --format-version 2`. Unknown format versions fail closed. This
page remains the human explanation of the machine-readable boundary.

## Declared-feature inspection API

The recognition-family manifest above remains format 2 and describes recognisers, records, and
aggregate membership only. A separate format-1 document freezes the smaller API used by CAD front
ends when a user selects geometry and declares a feature:

```python
from b123d_recognisers.inspection import inspection_api_manifest

inspection_contract = inspection_api_manifest(format_version=1)
```

Its primary namespace is `b123d_recognisers.inspection`. The consumer-proven operation roster is
`inspect_face`, `classify_bevel` / `BevelReject`, `cone_rims`, `read_double_d_tool`, and
`floor_face_anchor`, together with the closed analytic result and refusal value types required by
`inspect_face`. The manifest records exact signatures, enum values, dataclass fields, introduction
versions, and compatibility aliases. Enum member names and values, dataclass field types plus
frozen/slotted status, and the positional analytic parameter layouts are part of that contract.
Unknown format versions and unknown document fields fail closed.

`AnalyticSurface.parameters` has one kind-specific positional layout. Coordinates, offsets,
radii, requested tolerances, kernel gaps, and anchors use the model length unit (normally mm);
directions are unitless unit vectors and cone angles are radians:

| kind | positional parameters |
| --- | --- |
| `plane` (`SurfaceKind.PLANE`) | `(normal_x, normal_y, normal_z, offset)`, with canonical unit normal and `dot(point, normal) == offset` |
| `cylinder` (`SurfaceKind.CYLINDER`) | `(axis_point_x, axis_point_y, axis_point_z, axis_x, axis_y, axis_z, radius)`, where `axis_point` is the closest point on the canonical axis to the global origin |
| `cone` (`SurfaceKind.CONE`) | `(apex_x, apex_y, apex_z, axis_x, axis_y, axis_z, signed_semi_angle)`, where the angle sign preserves the original cone direction after the axis is canonicalised |
| `sphere` (`SurfaceKind.SPHERE`) | `(centre_x, centre_y, centre_z, radius)` |

`BevelReject.reason` is a closed string contract: `nonplanar`, `degenerate`, `aligned`, or
`compound`. `read_double_d_tool()` returns the ordered tuple `(axis, major_diameter,
across_flats, origin, depth, profile_direction)`: `axis` is the principal-axis name `x`, `y`, or
`z`; both diameters, all three origin coordinates, and depth use model-length units; the
three-component profile direction is unitless.

`FaceInspection.anchor`, when present, is proved in or on the actual trimmed face. It is not merely
a point on the untrimmed underlying surface; inner wires and concave outer wires are respected.

The old `experimental_geometry.inspect_face` and surface-value names are exact-object aliases, as
are the existing root or family-module paths for the other four reads. New code should use the
inspection namespace. This graduation does not publish `GeometryGraph`, opaque graph handles,
adjacency, blend collapse, sections, correspondence, Candidate/evidence, registry, or
reconciliation. Those remain private or experimental because no second external consumer proved
their cost.

## Defining-face attribution status

Attribution remains a private Candidate/evidence contract. Format 2 adds API roles and the counted
aggregate output so compatibility projections cannot masquerade as a second physical authority;
it does not expose face claims. `Fully attributed` means every aggregate record occurrence on every
current output path has non-empty original-face defining evidence. `Incomplete` may include useful
measured occurrences while at least one path remains empty; it does not mean the recogniser returns
nothing. Every non-empty aggregate defining set, complete or partial, must belong to one graph-proved
valid closed solid.

| Status | Physical families | Reason / next boundary |
| --- | --- | --- |
| Fully attributed | `angled_steps`, `bosses`, `chamfers`, `channels`, `countersinks`, `double_d_bores`, `fillets`, `flats`, `grooves`, `holes`, `pads`, `passages`, `plates`, `pockets`, `polygonal_bosses`, `polygonal_stock`, `prismatic_pockets`, `repeating_radial_profiles`, `slots`, `turned_steps` | Existing writer-enabled paths claim every returned occurrence; the family audits prove exact original owner faces while preserving public output. Polygonal Stock remains stock context and is still deliberately absent from the feature census; Repeating Radial Profiles remain neutral correspondence evidence. |
| Incomplete | `risers`, `step_levels` | Step Levels can span multiple bodies and Riser value deduplication can collapse distinct faces/SolidRefs; both have reviewed structural exclusions pending occurrence-preserving identity or explicit multi-source ownership. |

The registry is the closed machine-checked authority for these 22 internal dispositions. Per-face
tools consume the completed frozen inventory and report records, Candidates, accepted occurrences,
attributed occurrences and defining faces separately. Corpus labels are diagnostic comparisons and
never establish ownership.

“Excluded” means that current recognition deliberately returns no record. It does not
mean the geometry is invalid or that support is promised. Expanding an excluded class
is a recognition-behaviour change requiring independent fixtures, semantic goldens,
compatibility review, and release notes.

| Recogniser | Proven current scope | Explicitly excluded or deferred | Primary evidence |
| --- | --- | --- | --- |
| `recognise_angled_steps` | Convex oblique planar slants running along one principal axis, cut into an edge of the part rather than into a wall of a recess, whose blind end is closed by an axis-aligned flat whose **outer wire** has three edges — so a bolt hole through that flat does not hide the step. | Ends whose triangle has a *side* split by a neighbouring feature, through slants (a chamfer), and compound three-axis slants. | Angled-step functional tests; over 120 MFCAD++ models, 100% precision and 70% instance recall, measured before the 0.2.6 gate changes; on 33 held-out MFCAD++ models drawn from classes no predicate was shaped by, 8 records and 100% precision. |
| `recognise_bosses` | External full cylindrical segments on principal or slanted axes, independently per solid; includes turned ODs. | Partial cylinders, internal bores, and caller-specific “local boss” filtering. | Contract suite; simple-hole and turned-step goldens. |
| `recognise_chamfers` | Dimension-worthy external planar bevels and principal-axis conical bevels on turned stock. Called through `build_recognition_result` or `feature_census`, a planar slant with a triangular blind end is excluded — an angled step, dropped by `_reconcile.chamfers_that_are_not_angled_steps` from the claims both families write. Called directly, that planar slant is proposed, because on the face alone it is a bevel. | Compound three-axis corner bevels, internal cones such as countersinks, and faces outside leg/size gates. | Chamfer/fillet/flat golden, turned-chamfer tests, negative bevel tests, bevel-claim reconciliation tests, and 40 labelled MFCAD++ models. |
| `recognise_channels` | Floored rectangular channels spanning both longitudinal ends of one solid; after graph-proved curved end interruptions are trimmed, a paired-wall candidate's unrounded rectangular prism must be materially empty within that solid. | Bounded blind pockets, through slots, same-solid internal islands/bridges that the simple record cannot express, and cross-solid face combinations. | Open-channel golden, per-solid regressions, and H/U/rib adversaries. |
| `recognise_countersinks` | Conical hole-mouth seats with a proven circular major rim, bore rim, and included angle. | General conical faces, decorative bevels, and unmatched cones. | Counterbore/countersink golden and cone rejection tests. |
| `recognise_double_d_bores` | Constant, principal-axis, through double-D voids with two opposed common-circle profiles and a material-free connecting prism. | Blind recesses, obrounds, lenses, arbitrary line/arc loops, non-principal axes, mismatched ends, and cross-solid pairing. | Double-D golden plus capability-negative tests. |
| `recognise_face_levels` | Horizontal planar face levels, optionally area-filtered, with XY support spans. | Slanted/curved faces and semantic decisions about which levels form dimensions. | Plate/level and slanted-step goldens. |
| `recognise_fillets` | Dimension-worthy external cylindrical edge blends and principal-axis toroidal blends on turned stock. | Compound corner rounds, internal rounds, and radii outside configured gates. | Chamfer/fillet/flat golden, turned-fillet tests, and adjacency bound regression. |
| `recognise_flats` | Planar truncations of proven round stock, including single-D and opposed flat evidence. | Arbitrary planar faces without a cylindrical-stock substrate. | Chamfer/fillet/flat and double-D evidence. |
| `recognise_grooves` | External reduced-OD bands between two larger coaxial shaft bands, reached directly or across chamfered or radiused lead-ins; `width` is the flat floor, excluding the lead-ins. | Internal grooves, end reliefs without two larger neighbours, and non-turned recesses. | Turned-step/groove golden; chamfered- and radiused-lead-in tests. |
| `recognise_hole_patterns` | Same-spec hole bolt circles, constant-pitch linear arrays, and complete rectangular grids; greedy largest-first ownership. | Pairs, incomplete lattices as grids, uneven circles/rows, mixed specs, and a hole belonging to multiple returned patterns. | Bolt-circle/grid golden, pattern regressions, and scaling sentinel. |
| `recognise_holes` | Coaxial internal full-cylinder stacks with through/flat/drill-point/unknown bottoms and injected countersink composition. | Slot end caps, partial cylinders, far-side counterbores, and automatic countersink rediscovery when none is injected. | Hole/counterbore/cross-bore goldens and edge regressions. |
| `recognise_passages` | Writer-free historical principal-axis Passage finder with unchanged schema-v1 values and order. Aggregate `.passages` is the stable accepted-rich projectable subsequence, so a historical partial-span false positive may remain direct-only rather than acquire counterfeit Candidate authority. | Attributed calls fail loudly from 0.4.0; use `recognise_section_passages(..., ledger=...)`. Oblique and unmatched legacy-only occurrences have no aggregate compatibility value. | Exact legacy semantic goldens, the mixed `10060.step` subsequence/disposition/census regression, plus the 0.4 migration/error boundary tests. |
| `recognise_section_passages` | Constant-section line-walled passages on principal or free axes, open at both ends, with one rich `SectionPassage` Candidate owning the complete original wall cycle. | Capped, tapered, stepped, curved-wall, open/invalid, cross-solid, or materially obstructed rings; line/arc schema exists but arc-wall discovery is deferred. | Independent topology oracle, principal compatibility matrix, arbitrary rotations, STEP, and exact Candidate/evidence tests. |
| `recognise_plates` | Thin prismatic slabs supported by opposed planar faces and configured area/thickness gates. | The single envelope plate, curved/non-prismatic shells, and slabs below the evidence gates. | Plate/level golden and plate tests. |
| `recognise_pocket_patterns` | Constant-pitch linear and complete rectangular arrays of identical, coplanar, equally oriented `Pocket` records. | Bolt circles, pairs, mixed sizes/opening faces/depth planes, and incomplete grids. | Blind-pocket golden and pattern-negative tests. |
| `recognise_pockets` | Floored rectangular recesses bounded within one solid; elongated blind slots are the same record class. After graph-proved curved end interruptions are trimmed, a paired-wall candidate's unrounded rectangular prism must be materially empty within that solid. | Through slots, open-ended channels, non-rectangular floors, same-solid internal islands/bridges that the simple record cannot express, and cross-solid composites. | Blind-pocket golden, floor/opening regressions, blind-U/rib adversaries, and MFCAD++/NIST change evidence. |
| `recognise_polygonal_bosses` | Attached regular hexagonal Z-axis bosses with six outward side faces, one A/F value, a support cap, and a top cap. Six native constant-radius convex cylindrical corner-blend chains may explicitly bridge the otherwise retained planar side ring when their complete issuer-owned provenance forms one unambiguous cycle. | Other side counts, X/Y axes, whole-stock prisms, inward recesses, incomplete or competing blend cycles, automatic collapse, and cross-solid assemblies. | Polygonal-boss golden, blend-interrupted sharp-control/STEP/aggregate evidence, plus capability-negative tests. |
| `recognise_polygonal_stock` | Exactly one solid consisting solely of a regular hexagonal Z-axis prism’s six sides and two caps. | Other side counts or axes, attachments, holes, chamfers, missing/extra faces, and multi-solid assemblies. | Polygonal-stock golden plus capability-negative tests. |
| `recognise_rectangular_pads` | Bounded rectangular +Z islands with a filled XY footprint, body-local support, and exact face ownership in one valid closed solid. | Full-span steps, non-rectangular/perforated tops, -Z/side pads, cross-solid support, open/invalid bodies, and ambiguous or missing solid ownership. | Plate/pad/level golden and pad tests. |
| `recognise_prismatic_pockets` | Floored recesses of any planar cross-section, found by walking the closed ring of walls: a triangular, hexagonal or rectangular pocket alike. Reports the section, so shape survives into the record. | Obround recesses, whose cylindrical ends form no closed planar ring — `recognise_pockets` reaches those; voids open at both ends (a passage) or capped at both (an enclosed cavity, unreachable by a tool). In the aggregate, a four-wall ring yields to a paired `Pocket`; a non-rectangular ring survives and defeats paired-wall fragments inside it. | Prismatic-pocket functional tests; `triangular_and_hex_pockets` golden; measured over 250 MFCAD++ models, capped rings reach 80 triangular, 72 hexagonal and 61 rectangular pockets where wall pairing reaches essentially only the rectangular ones. |
| `recognise_repeating_radial_profiles` | Complete outer-wire profiles invariant under a proved sector rotation, independently per solid. | Gear semantics, partial-repeat inference, inner-only profiles, and cross-solid cycles. | Repeating-radial-profile and traversal-order goldens. |
| `recognise_risers` | Full-span principal in-plane step-riser evidence, including bounded slanted transitions, independent of a level set. | Pads, pocket walls, partial corner notches, and end-treated/inset risers outside tolerance; shoulder selection remains a consumer projection. | Plate/level and slanted-step goldens. |
| `recognise_slot_patterns` | Constant-pitch linear and complete rectangular arrays of identical through `Slot` records on the same through plane. | Bolt circles, pairs, mixed sizes/planes, and incomplete grids. | Straight/obround-slot golden and pattern-negative tests. |
| `recognise_slots` | Enclosed through-slots proved by opposed walls or qualifying obround end caps, independently per solid. A planar pair must have agreeing AAG arcs into shared boundary neighbours, or belong to one smooth-connected boundary component when STEP has fragmented that boundary (the gAAG-equivalent query); after graph-proved curved end interruptions are trimmed, its unrounded rectangular prism must be materially empty. | Floored pockets, open-ended channels, merely narrow envelope sections, internal islands/bridges that the simple record cannot express, cross-solid composites, and opposed pairs assembled from different sides of a polygonal void. Aggregate reconciliation gives complete pocket and non-rectangular passage rings precedence over paired-wall fragments. | Straight/obround-slot golden, AAG-coherence mutation, H/U/thin-rib/scale adversaries, frozen MFCAD++ holdout, NIST corrections, and recess-reconciliation regressions. |
| `recognise_turned_steps` | Two or more contiguous coaxial external cylindrical segments forming a stepped shaft on one axis. | Plain cylinders, non-turned parts, disconnected/mixed-axis segments, and drafting interpretation beyond the geometry profile. | Turned-step/groove golden and turned-step tests. |

## Surface-representation support is family-specific

Most recognisers above still classify faces by their native surface type. A face is a hole wall
because it arrives as a `GeomAbs_Cylinder`, a floor because it arrives as a `GeomAbs_Plane`.
Imported geometry therefore still has to preserve native analytic surfaces for every family except
the explicitly measured Raised Pad slice below.

STEP carries analytic surfaces, and `tests/test_step_round_trip.py` proves the file boundary does
not disturb them: all twenty golden fixtures exported to STEP and re-imported reproduce their
pinned records exactly, with planes and cylinders still typed as such.

That evidence covers geometry written by this project's own OCCT-based exporter. It shows that
passing through a STEP file is not itself lossy. No third-party corpus is checked in, but the
separate external measurement below now covers one Autodesk exporter corpus without redistributing
its licensed models.

`recognise_rectangular_pads` additionally supports exact plane geometry re-expressed by OCCT as
B-spline faces. Its run-owned effective-surface query retains the exact original faces, bounded
recovery certificates and a separate closed-solid material-side certificate for the top face.
Every participating face must resolve to exactly one valid closed-solid owner; open shells,
invalid bodies, and ambiguous or missing ownership return no Pad records.
The [NURBS-conversion sweep](benchmarks/nurbs-conversion-sweep.md) validates a one-to-one face
correspondence before comparing topology, complete records and exact defining evidence: across 20
goldens it recovers 319/319 faces and retains the one native Pad with no changed, absent or
introduced occurrence. Converted-input adversaries cover a positive Pad, pockets/voids, tier
suppression, envelope contact, open ownership and multiple solids. This claim is limited to exact
OCCT conversion under the reviewed OCP/OCCT 7.9.3.1 contract.

The [external NURBS corpus spike](benchmarks/nurbs-external-corpus-spike.md) scans the complete
42,912-model Fusion 360 Gallery Extended STEP archive, fixes an evenly spaced 1,000-model sample
from its 8,673 B-spline-bearing files before OCCT import or fitting, and imports all 1,000. Of 12,729
imported B-spline/Bezier faces, 48 (0.3771%) satisfy the bounded analytic-recovery contract: 31
cylinders, 12 planes and 5 cones across 21 models. Nine of the recovered planes acquire a separate
material-side certificate, three refuse it, and none changes Raised Pad output against a
native-only counterfactual. The largest accepted kernel gap is 99.3612% of its face-local bound,
so this is bounded recovery evidence, not an upgrade of the exact-conversion claim above.

The same spike now measures the missing feature-unlock counterfactual. It leaves each original
TopoDS input untouched, temporarily exposes recovered planes, cylinders and cones to every raw
surface reader, and counts every aggregate family under both prismatic and rotational caller
classifications. One affected model fails the untouched inventory baseline and is excluded. On the
remaining 20 models, the combined overlay changes 11: 29 recovered cylinders become visible as 26
internal and 3 external cylinder patches, with downstream gains of four Flat candidates in one
model and one Hole candidate in one model. No candidate is lost. Recovered planes and cones unlock
no result in either classification mode. The repeated research inventories take 93.608 seconds,
including 30.850 seconds of untouched baselines; this is harness cost, not a proposed production
hot path.

That is a non-zero, narrowly cylinder-specific signal—not evidence for a general NURBS backlog.
The new Hole and Flat candidates are not yet correctness claims: recovered curved orientation has
not been certified and the individual candidates still need semantic review. A future migration
should therefore start at the shared cylinder substrate with orientation/material-side proof and
those measured cases as an external evaluation set. This sample gives no data-backed reason to
migrate plane consumers beyond Pads or any cone consumer.

B-spline input remains **excluded for every other family**, including all cylinder- and
torus-dependent families. Refused or ambiguous analytic recovery and an unproved material owner
fail closed. Reverse-engineered or otherwise uncontrolled inputs have no support claim even when
an individual face happens to satisfy the bounded fitter. Aggregate results may therefore contain
Raised Pads while other families remain absent; that is a deliberate per-family capability
boundary, not evidence of whole-model support.

## Measured against third-party labelled corpora

Epic 0005 uses a single versioned
[`effectiveness baseline method`](benchmarks/effectiveness-baseline-method.md) and the frozen
[`0.5.0 MFCAD++ result`](benchmarks/effectiveness-mfcadpp-500-0.5.0.md) for new MFCAD++
development reports and MFInstSeg transfer baselines. It records exact numerators and denominators,
accepted physical occurrences, defining-face agreement, instance recall where available,
reconciliation drops, bounded diagnostics, empty models, runtime, versions and corpus selection.
The historical measurements below predate that schema and remain evidence for the narrower claims
they state; they are not silently promoted into the new baseline.

MFTRCAD version 1 is also available as an external, relationship-labelled development source.
Its provenance, deterministic development/holdout draw, malformed-model policy and deliberately
non-authoritative taxonomy mapping are documented in
[`docs/corpora/mftrcad.md`](corpora/mftrcad.md). Its counts remain separate from the vendored
MFCAD++ evidence below and from real-part evidence.

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
On MFCAD++, fitting labelled faces to emitted records across 400 models reproduces it — every
rectangular class recognises, and Triangular passage, 6-sided passage, Triangular pocket, Circular
through slot, 2-sided through step, Horizontal circular end blind slot and Slanted through step
produce essentially nothing. This is what "non-rectangular floors", "Slanted/curved faces" and
"non-principal axes" above mean in practice, on parts written by someone else.

**One figure is about geometry this project was not fitted to.** Everything above comes from a
corpus that has already been used to change predicates, which makes it regression evidence rather
than a generalisation estimate. `tests/corpus/mfcadpp_holdout` is thirty-three models drawn from
the MFCAD++ *val* split — disjoint from the vendored design set by construction — covering the
twenty classes the design set does not target. It was scored once, after the last predicate
change. Angled steps: eight records, every one on a face labelled a triangular blind step, with
forty-eight triangular-pocket faces and twenty-two slanted-through-step faces available to go
wrong on. Of 226 Stock-labelled faces, fourteen are complete Plate boundary evidence and none is
claimed by another family; every affected Plate also owns its opposed non-Stock boundary. That is
expected overlap between this package's material-slab semantics and MFCAD++'s single face label,
not a Stock machining feature. It found one defect before it was sealed — a
right-triangular pocket wall reported as an angled step — which is now rejected by a gate and
pinned by a fixture. Scoring that set again is fine; changing a predicate to satisfy it is not,
and would cost a fresh draw.

**Curved families recognise.** MFCAD is planar-only in all 15 classes, so it cannot exercise
holes, fillets, bosses, countersinks, grooves or turned steps at all. MFCAD++ can, and does:
Through hole and Blind hole yield hole records, Circular blind step yields fillets, O-ring yields
bosses and holes.

Three limits on how far this evidence reaches:

- **It is not a recall score.** These corpora use their own feature vocabulary. Several classes
  are recognised under a *different* family than the corpus names — O-ring as boss, Circular
  blind step as fillet — which is a taxonomy mismatch, not a defect, and makes naive cross-corpus
  percentages meaningless. See *Naming* below for how far that vocabulary is adopted here.
- **The labels are single-assignment, so they mislead at feature intersections.** MFCAD++ gives
  each face exactly one feature label. Where two features meet, a wall belonging to both is
  assigned to one of them, and a wall bounded by raw billet is assigned to *Stock* — which means
  "assigned to no feature", not "no feature touches this". Measured: `recognise_passages` reports
  a genuine 6-sided passage on `11251.step` whose six walls carry **five different labels**, two
  of them *Stock*. Any per-face score against these labels therefore understates a family that is
  right about an intersecting feature, and a recogniser tuned to raise such a score would be
  fitted to the corpus rather than to the geometry.
- **Attribution is reported separately from corpus labels.** `tools/per_face_scan.py` reads one
  completed frozen inventory and reports records, physical Candidates, accepted Candidates and
  measured defining faces for all 22 physical families, alongside each registry attribution
  status. The MFCAD++ label comparison is a separate accepted-only view. When this corpus study was
  recorded, it contained measured output from six prismatic families — slots, pockets, prismatic
  pockets, passages, chamfers and angled steps — while grooves and turned steps also wrote defining
  evidence but did not occur in the 50 vendored milled parts. Families then still migrating had
  partial or no measured face attribution; their registry status stated that limitation rather
  than replacing it with a statistical ownership claim. The
  figures quoted as precision — 100% for angled steps, 44% → 78% for chamfers over 120 models —
  are counted per face rather than fitted. The chamfer figure is the *reconciled* answer, which is what the
  aggregate and the census report; called directly the recogniser proposes a blind step's slant
  as well and scores lower — 50% against 79% over the 40 vendored models — for the reason the
  row above gives.

  Those quoted corpus figures preserve the measurement method used when each study was run; some
  older rows compare record counts with labelled-face counts and therefore remain fit estimates,
  even though later F5 development evidence established exact defining ownership independently.
  The current registry truth is the 20/2 table above: twenty families now publish complete original-
  face evidence, while Step Levels and Risers deliberately remain writer-free structural
  exclusions. External taxonomy labels still do not prove those defining roles, so historical
  count-fit figures must not be upgraded retrospectively into per-face corpus measurements.
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
| Round; Circular blind step | Fillet | |
| O-ring | BossRecord | |
| Through hole; Blind hole | HoleRecord | |
| Rectangular / 2-sided / Slanted through step | — | **unrecognised**; see epic 0002 on through steps |
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
| `Chamfer` | One qualifying external, single-principal-axis planar or conical bevel; `turned` is true only for the conical shaft treatment. |
| `Channel` | One floored rectangular recess open at both ends of its longitudinal solid envelope. |
| `CounterBore` | One coaxial cylindrical hole step used as either the `cbore` or `spotface` field of `HoleRecord`. |
| `CounterSink` | One proved conical seat at a matching cylindrical bore mouth. |
| `DoubleDBore` | One constant principal-axis through double-D void; recogniser output always has `through=True`. |
| `FaceLevel` | One horizontal Z level plus optional XY support spans; it does not claim a dimension requirement. |
| `Fillet` | One qualifying external, single-principal-axis cylindrical or toroidal edge blend; `turned` is true only for the toroidal shaft treatment. |
| `Flat` | One planar truncation corresponding to a proved cylindrical-stock substrate. |
| `Groove` | One external reduced-OD band between larger coaxial neighbours. |
| `HoleRecord` | One internal full-cylinder stack with optional near-side hole treatments and one classified bottom. |
| `HoleSpec` | A normalized grouping key derived from `HoleRecord`; through depth is intentionally absent. |
| `LinearArray` | At least three same-spec holes on one constant-pitch line, ordered along `direction`. |
| `Passage` | One closed uncapped ring of walls; `sides` is the polygon, so a triangular passage reports 3, and `section` gives its corners so the shape can be dimensioned rather than only named. |
| `PassageEnds` | Nested explicit low/high cap state; `SectionPassage` requires the canonical open/open value. |
| `PassageFrame` | Nested canonical right-handed run/u/v frame and perpendicular origin for rich section geometry. |
| `PassageSection` | Nested canonical, origin-centred immutable line/arc boundary. |
| `PassageSectionVertex` | One nested 2-D section vertex whose bulge describes the edge to the next vertex. |
| `Plate` | One qualifying thin prismatic slab represented by its thickness axis and bounds. |
| `PrismaticPocket` | One floored recess of constant planar cross-section, open at one end; `sides` and `section` carry the shape that `width`/`length` cannot. |
| `Pocket` | One floored bounded rectangular recess; elongated blind slots intentionally use this same class. |
| `PocketArray` | At least three identical compatible pockets on one constant-pitch line. |
| `PocketGrid` | A complete rectangular lattice of identical compatible pockets. |
| `PolygonalBoss` | One attached regular hexagonal Z-axis boss; output is exactly `axis="z"`, `side_count=6`. |
| `PolygonalStock` | One whole regular hexagonal Z-axis prism; output is exactly `axis="z"`, `side_count=6`. |
| `RaisedPad` | One bounded rectangular +Z island with footprint and height evidence. |
| `RectGrid` | A complete rectangular lattice of same-spec holes with the documented row/column basis convention. |
| `RepeatingRadialProfile` | Geometry-only proof of complete outer-profile rotational repetition, defined by its two original opposed extremal planar source faces; not gear semantics. |
| `RiserEvidence` | One full-span candidate riser before any consumer-specific level projection. |
| `SectionPassage` | The sole attributed PASSAGES output: canonical frame, run interval, intrinsic section and explicit open ends. |
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

`build_recognition_report()` pairs that unchanged inventory with bounded lifecycle explanations
from the same run. It records whether each physical family ran, candidate and final disposition
counts, and only the residual diagnostic codes established by frozen evidence. It does not scan
unclaimed geometry or imply that an evaluated-empty family has no unsupported related geometry.
ADR 0012 defines this compatibility boundary; framed explanations and surface-cache summaries are
not shipped.

Every public `recognise_*` export must appear exactly once in the recogniser table above. CI derives
that export inventory from the installed public module rather than trusting this page,
so adding a recogniser without an explicit capability claim fails closed even before the
versioned manifest is implemented.
