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
| Fully attributed | `angled_steps`, `bosses`, `chamfers`, `channels`, `circular_blind_steps`, `countersinks`, `double_d_bores`, `fillets`, `flats`, `grooves`, `holes`, `pads`, `paired_ramp_steps`, `passages`, `plates`, `pockets`, `polygonal_bosses`, `polygonal_stock`, `prismatic_pockets`, `repeating_radial_profiles`, `risers`, `slots`, `step_levels`, `through_steps`, `turned_steps` | Existing writer-enabled paths claim every returned occurrence; the family audits prove exact original owner faces while preserving public output. Polygonal Stock remains stock context and is still deliberately absent from the feature census; Repeating Radial Profiles remain neutral correspondence evidence. Face Levels and Risers retain body-local multiplicity and own their complete same-solid source-face clusters. |
| Incomplete | — | Every current aggregate family has complete original-face attribution. |

The registry is the closed machine-checked authority for these 25 internal dispositions. Per-face
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
| `recognise_circular_blind_steps` | Inward quarter-cylindrical principal-axis corner cuts with one concave interior planar terminal, an opening at the opposite same-solid envelope end, two convex transverse side joins, and an empty exact terminal-sector sweep. | Full bores, through or capped grooves, non-quarter, external, tapered or oblique walls, obstructed sectors, invalid bodies, and cross-solid evidence. | Authored positive, negative, tolerance-boundary, transformation, STEP, provenance, reconciliation and MFCAD++ development evidence. |
| `recognise_countersinks` | Conical hole-mouth seats with a proven circular major rim, bore rim, and included angle. | General conical faces, decorative bevels, and unmatched cones. | Counterbore/countersink golden and cone rejection tests. |
| `recognise_double_d_bores` | Constant, principal-axis, through double-D voids with two opposed common-circle profiles and a material-free connecting prism. | Blind recesses, obrounds, lenses, arbitrary line/arc loops, non-principal axes, mismatched ends, and cross-solid pairing. | Double-D golden plus capability-negative tests. |
| `recognise_face_levels` | Horizontal planar face-level occurrences clustered independently per valid solid, optionally area-filtered against that body's plan footprint, with body-local XY support spans. Aggregate occurrences own the exact horizontal source-face cluster. | Slanted/curved faces and semantic decisions about which levels form dimensions. | Plate/level and slanted-step goldens; separated-body, nested-compound, STEP, order, area-authority and framed rigid-motion controls. |
| `recognise_fillets` | Dimension-worthy external cylindrical edge blends and principal-axis toroidal blends on turned stock. | Compound corner rounds, internal rounds, and radii outside configured gates. | Chamfer/fillet/flat golden, turned-fillet tests, and adjacency bound regression. |
| `recognise_flats` | Planar truncations of proven round stock, including single-D and opposed flat evidence. | Arbitrary planar faces without a cylindrical-stock substrate. | Chamfer/fillet/flat and double-D evidence. |
| `recognise_grooves` | External reduced-OD bands between two larger coaxial shaft bands, reached directly or across chamfered or radiused lead-ins; `width` is the flat floor, excluding the lead-ins. | Internal grooves, end reliefs without two larger neighbours, and non-turned recesses. | Turned-step/groove golden; chamfered- and radiused-lead-in tests. |
| `recognise_paired_ramp_steps` | One principal-axis, mirror-symmetric pair of original planar ramp faces meeting concavely along its run, with a convex stock-envelope opening and one concave unsmoothed three- or five-sided terminal in the same valid solid. | Asymmetric ramps, seven-sided/subdivided terminals, non-principal runs, and ambiguous ownership. A rigidly rotated top-opening triangular recess has the same geometry and remains the same record; corpus taxonomy does not override that invariance. | Authored positive, material-side/ownership/presentation/scale adversaries; semantic golden; first-500 MFCAD++ development scan. |
| `recognise_through_steps` | Exactly two rectangular principal-plane regions meeting along one complete concave seam and opening across both ends of one valid source solid; reports the oriented open section and run. | Channels, pockets, capped or partial-run cuts, interrupted, tapered or curved walls, non-principal runs, and ambiguous ownership. | Authored positive/negative/transformation/STEP/provenance tests; semantic golden; first-500 MFCAD++ development comparison. |
| `recognise_hole_patterns` | Same-spec hole bolt circles, constant-pitch linear arrays, and complete rectangular grids; greedy largest-first ownership. | Pairs, incomplete lattices as grids, uneven circles/rows, mixed specs, and a hole belonging to multiple returned patterns. | Bolt-circle/grid golden, pattern regressions, and scaling sentinel. |
| `recognise_holes` | Coaxial internal full-cylinder stacks with through/flat/drill-point/unknown bottoms and injected countersink composition. | Slot end caps, partial cylinders, far-side counterbores, and automatic countersink rediscovery when none is injected. | Hole/counterbore/cross-bore goldens and edge regressions. |
| `recognise_passages` | Writer-free historical principal-axis Passage finder with unchanged schema-v1 values and order. Aggregate `.passages` is the stable accepted-rich projectable subsequence, so a historical partial-span false positive may remain direct-only rather than acquire counterfeit Candidate authority. | Attributed calls fail loudly from 0.4.0; use `recognise_section_passages(..., ledger=...)`. Oblique and unmatched legacy-only occurrences have no aggregate compatibility value. | Exact legacy semantic goldens, the mixed `10060.step` subsequence/disposition/census regression, plus the 0.4 migration/error boundary tests. |
| `recognise_section_passages` | Constant-section line-walled passages on principal or free axes, open at both ends, with one rich `SectionPassage` Candidate owning the complete original wall cycle. | Capped, tapered, stepped, curved-wall, open/invalid, cross-solid, or materially obstructed rings; line/arc schema exists but arc-wall discovery is deferred. | Independent topology oracle, principal compatibility matrix, arbitrary rotations, STEP, and exact Candidate/evidence tests. |
| `recognise_plates` | Body-local thin prismatic slabs supported by opposed planar face clusters, a roll-invariant body-oriented cross-envelope area gate, and the configured thickness gate. Equal-valued occurrences on separate valid solids retain multiplicity and independent transverse witnesses. In a rotational-classified mixed compound, completed TurnedSteps exclude only their owning solids; a rotational run with no established turned profile retains the historical empty Plate inventory. | The single envelope plate, curved/non-prismatic shells, internally oblique normals, cross-solid face pairing, and slabs below the evidence gates. | Plate/level golden; signed-axis and in-plane-roll boundaries; single/equal/unequal/nested compound, mixed turned/prismatic, framed rigid-motion, STEP, provenance and package tests; paired [body-locality](benchmarks/e2-plate-body-locality-validation.md) and [roll-covariance](benchmarks/e2-plate-roll-covariance-validation.md) evidence. |
| `recognise_pocket_patterns` | Constant-pitch linear and complete rectangular arrays of identical, coplanar, equally oriented `Pocket` records. | Bolt circles, pairs, mixed sizes/opening faces/depth planes, and incomplete grids. | Blind-pocket golden and pattern-negative tests. |
| `recognise_pockets` | Principal-axis floored rectangular recesses bounded within one solid; elongated blind slots are the same record class. Corner depth is the uniquely shallowest complete physical leg. Opposed-wall recesses require exactly one valid floor/opening interpretation. After graph-proved curved end interruptions are trimmed, the unrounded rectangular prism must be materially empty within that solid. | Through slots, open-ended channels, non-rectangular or internally oblique floors, ambiguous equal corner legs or depth interpretations, same-solid internal islands/bridges that the simple record cannot express, and cross-solid composites. | Signed X/Y/Z, rigid-frame, STEP, provenance and ambiguity controls; blind-pocket golden, blind-U/rib adversaries, and matched MFCAD++ evidence. |
| `recognise_polygonal_bosses` | Attached regular hexagonal principal-axis bosses with six outward side faces, one A/F value, and two unambiguous terminal boundaries whose normals agree on the signed attachment direction. `axis` is X, Y or Z; `base`/`top` remain ascending coordinates even when attachment runs in the negative direction. Six native constant-radius convex cylindrical corner-blend chains may explicitly bridge the otherwise retained planar side ring when their complete issuer-owned provenance forms one unambiguous cycle. | Non-principal axes in the supplied recognition frame, other side counts, whole-stock prisms, inward recesses, incomplete or competing blend cycles, automatic collapse, and cross-solid assemblies. | Signed X/Y/Z, in-plane/arbitrary-rigid-motion, exact face-anchor, compound, STEP, blend-interrupted sharp-control, aggregate and capability-negative tests. |
| `recognise_polygonal_stock` | Exactly one solid consisting solely of a regular hexagonal principal-axis prism’s six sides and two caps; `axis` identifies X, Y or Z. | Non-principal axes in the supplied recognition frame, other side counts, attachments, holes, chamfers, missing/extra faces, and multi-solid assemblies. | Polygonal-stock golden, X/Y/Z transform and framed rigid-motion evidence, plus capability-negative tests. |
| `recognise_rectangular_pads` | Bounded rectangular islands on all six signed principal directions, with a filled transverse footprint, body-local support, orientation-bearing XYZ bounds, and exact face ownership in one valid closed solid. A complete, unambiguous four-chain convex cylindrical corner-blend cycle may reconstruct the same four planar wall roles and rounded top. Overlapping readings require one uniquely shortest attachment span. | Full-span steps, non-rectangular/perforated tops, internally oblique pads, tied axis interpretations, partial or competing corner-blend cycles, cross-solid support, open/invalid bodies, and ambiguous or missing solid ownership. | Plate/pad/level golden; signed-axis sharp/blend, rigid-frame, ambiguity, rotated negative, STEP, provenance/refusal and aggregate pad tests; authored blend sweep; paired census and MFCAD++-500 effectiveness/performance evidence. |
| `recognise_prismatic_pockets` | Floored recesses of any planar cross-section, found by walking the closed ring of walls: a triangular, hexagonal or rectangular pocket alike. Reports the section, so shape survives into the record. | Obround recesses, whose cylindrical ends form no closed planar ring — `recognise_pockets` reaches those; voids open at both ends (a passage) or capped at both (an enclosed cavity, unreachable by a tool). In the aggregate, a four-wall ring yields to a paired `Pocket`; a non-rectangular ring survives and defeats paired-wall fragments inside it. | Prismatic-pocket functional tests; `triangular_and_hex_pockets` golden; measured over 250 MFCAD++ models, capped rings reach 80 triangular, 72 hexagonal and 61 rectangular pockets where wall pairing reaches essentially only the rectangular ones. |
| `recognise_repeating_radial_profiles` | Complete outer-wire profiles invariant under a proved sector rotation, independently per solid. | Gear semantics, partial-repeat inference, inner-only profiles, and cross-solid cycles. | Repeating-radial-profile and traversal-order goldens. |
| `recognise_risers` | Per-valid-solid full-span principal in-plane step-riser occurrences, including bounded slanted transitions. Each occurrence carries its body's eligible level-Z set so pure shoulder projection cannot borrow a level from another solid. | Pads, pocket walls, partial corner notches, and end-treated/inset risers outside tolerance; caller-specific level selection remains a pure consumer projection. | Plate/level and slanted-step goldens; equal/unequal separated-body, false-envelope, nested/order, STEP and framed-motion controls. |
| `recognise_slot_patterns` | Constant-pitch linear and complete rectangular arrays of identical through `Slot` records on the same through plane. | Bolt circles, pairs, mixed sizes/planes, and incomplete grids. | Straight/obround-slot golden and pattern-negative tests. |
| `recognise_slots` | Principal-axis enclosed through-slots proved by opposed walls or qualifying obround end caps, independently per solid. A planar pair must have agreeing AAG arcs into shared boundary neighbours, or belong to one smooth-connected boundary component when STEP has fragmented that boundary (the gAAG-equivalent query); after graph-proved curved end interruptions are trimmed, its unrounded rectangular prism must be materially empty. A connected curved region smoothly closing either selected depth end refuses the alternate deep-pocket interpretation. | Floored pockets and their alternate orthogonal projections, open-ended channels, internally oblique or merely narrow envelope sections, internal islands/bridges that the simple record cannot express, cross-solid composites, and opposed pairs assembled from different sides of a polygonal void. Aggregate reconciliation gives complete pocket and non-rectangular passage rings precedence over paired-wall fragments. | Signed X/Y/Z and framed covariance, straight/obround-slot golden, split-smooth-closure, AAG-coherence mutation, H/U/thin-rib/scale adversaries, frozen MFCAD++ holdout, NIST corrections, recess-reconciliation regressions, and [paired MFCAD++-500 validation](benchmarks/e5-slot-depth-closure-validation.md). |
| `recognise_turned_steps` | Two or more contiguous coaxial external cylindrical segments forming a stepped shaft, recognised independently per valid solid. Each step carries a serializable physical axis-line/body membership key, so equal parallel, coaxial-disjoint and mixed-axis profiles retain separate deterministic groups and exact same-solid evidence. | Plain cylinders, non-turned bodies, disconnected cylindrical bands within one profile, internally oblique axes, and drafting interpretation beyond the geometry profile. | Turned-step/groove golden; equal/unequal parallel, coaxial-disjoint, mixed-axis, compound-order, STEP, framed-motion, Plate/groove ownership and exact-attribution controls; [body-local MFCAD++-500 validation](benchmarks/e2-turned-profile-body-locality-validation.md). |

The [authored boundary-blend sweep](benchmarks/blend-boundary-sweep.md) holds each feature body
fixed while filleting only the boundary used by its named recogniser. Across fifteen valid blended
variants, Polygonal Boss and Rectangular Pad preserve their exact records through their selected
blend views; Hole and Groove remain present with legitimately changed dimensions; and Pocket
consistently reclassifies to Prismatic Pocket. Pad's complete-cycle support has independent
provenance, refusal, native, STEP and aggregate tests. Corpus and runtime effects remain separately
reported evidence rather than being inferred from this authored sweep. The
[MFCAD++ E4 comparison](benchmarks/effectiveness-mfcadpp-500-e4-pad.md) has exact score-vector parity
over the frozen 500-model development selection and a same-process enabled/disabled timing ratio of
1.0221; that corpus contains no newly accepted complete Pad corner-blend cycle.

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
The shared cylinder inventory now consumes exact recovered cylinders only after independent radial
material-side proof against one valid closed-solid owner. Hole and Boss aggregate Candidates retain
the original cylinder faces and their recovery/material-side dependencies. Recovered angular span
comes from original trim topology/points rather than spline U units, and recovered axial bounds use
OCCT optimal exact-geometry bounds in the cylinder frame. Exact converted OD and bore fixtures cover
both radial signs, transforms, curved trims, aggregate attribution and the existing Boss consumer.
Native and recovered axis lines, directions and axial extrema use one post-measurement canonical
output seam; standalone native Hole/Boss calls retain their fast path because the recovery graph is
created lazily only when an eligible spline face is encountered.
The paired recovered-plane end query gives exact converted through Holes the same complete record in
standalone and aggregate routes; refusal reports an `unknown` end rather than guessing. No Hole,
Boss or Flat admission threshold was relaxed.

The four Flat and one Hole candidates from the external spike remain prioritisation evidence rather
than correctness claims until the licensed source archive can be rerun and those models adjudicated.
A wholly converted model may still stop at a downstream native-surface boundary: Hole end cones,
tori, spheres and cylinders remain native-only even though certified recovered planes now establish
open/flat ends. This sample gives no data-backed reason to migrate plane consumers beyond Pads and
that bounded Hole end role, or to migrate any cone consumer.

B-spline input remains **excluded beyond the measured Raised Pad and shared-cylinder boundaries**.
Torus-dependent branches remain excluded. Refused or ambiguous analytic recovery and an unproved
material owner fail closed. Reverse-engineered or otherwise uncontrolled inputs have no support
claim even when an individual face happens to satisfy the bounded fitter. Aggregate results may
therefore contain only the families whose complete downstream predicates remain supported; that is
a deliberate per-family boundary, not evidence of whole-model support.

## Measured against third-party labelled corpora

Epic 0005 uses a single versioned
[`effectiveness baseline method`](benchmarks/effectiveness-baseline-method.md) and the frozen
[`0.5.0 MFCAD++ result`](benchmarks/effectiveness-mfcadpp-500-0.5.0.md) for new MFCAD++
development reports and MFInstSeg transfer baselines. It records exact numerators and denominators,
accepted physical occurrences, defining-face agreement, instance recall where available,
reconciliation drops, bounded diagnostics, empty models, runtime, versions and corpus selection.
The E2 [`Angled Step frame-axis audit`](benchmarks/e2-angled-step-axis-audit.md) proves authored
signed X/Y/Z covariance and classifies the four historical framed losses as internally oblique
geometry in two models, with no production relaxation.
The E2 [`Prismatic Pocket frame-axis audit`](benchmarks/e2-prismatic-pocket-axis-audit.md) proves
signed X/Y/Z ring covariance and classifies all six historical losses at their defining-wall
discovery boundary, with rectangular Pocket precedence unchanged.
The E2 [`rectangular recess frame-axis audit`](benchmarks/e2-rectangular-recess-axis-audit.md)
removes world-Z and XYZ-iteration dependence from Pocket/Slot depth selection, reduces 88
historical rectangular raw-to-framed transitions to seven classified non-contract/false-projection
residuals, raises net correct Pocket defining faces by 19, and remains within the 1.10 runtime gate.
The E2 [`residual Fillet and Plate audit`](benchmarks/e2-residual-frame-axis-audit.md) removes eight
false cylindrical Fillets by refusing sign-dependent equidistant supporting-plane choices while
preserving every other family count. It separately traces one Plate transition to the
rotation-dependent bbox cross-area gate tracked in issue #329; Plate behavior is unchanged here.
The E5b [`bounded rectangular Through Step result`](benchmarks/effectiveness-mfcadpp-500-e5b-through-step.md)
added 39 conservative occurrences with 78/78 correct defining faces. The E5d
[`interruption-tolerant result`](benchmarks/effectiveness-mfcadpp-500-e5d-through-step.md) preserves
100% defining-face precision while expanding to 92 occurrences and 184/415 defining-face recall;
both increments record paired runtime sentinels separately.
The E5f [`Circular Blind Step result`](benchmarks/effectiveness-mfcadpp-500-e5f-circular-blind-step.md)
adds 118 accepted occurrences with 236/236 defining-face precision and reconciles exactly 114
overlapping Fillets; its MFCAD++ and real-part paired runtime ratios remain below 1.04.
The E0 [`circular through-slot scope audit`](benchmarks/e0-circular-through-slot-scope-audit.md)
checks all 78 class-7 faces in the lexical MFCAD++-500 selection and records that the exact
semicylindrical groove geometry is unsupported by the two-opposed-wall `Slot` contract; taxonomy
v3 corrects the scope without changing any physical record or production behavior.
The E2 [`framed Polygonal Stock result`](benchmarks/e2-framed-polygonal-stock.md) makes exact whole
hexagonal stock principal-axis covariant, restores the downstream framed occurrence under rigid
presentation, retains exact MFCAD++-500 output parity, and stays below the paired runtime ceiling.
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
| Rectangular through slot | — | **unsupported as a corpus class**; its dominant three-wall edge-slot motif is open longitudinally, while closed/free-axis variants mix distinct package contracts |
| Circular through slot | — | **unsupported**; MFCAD++/MFInstSeg use this label for a semicylindrical groove, which the current `Slot` record cannot express |
| Rectangular pocket | Pocket | blind by definition here |
| Triangular pocket; 6-sided pocket | PrismaticPocket | any planar cross-section, found by walking the ring; `Pocket` cannot express a non-rectangular footprint |
| **Circular end pocket** | Pocket | an obround blind recess; direct recognisers may propose competing paired walls, but aggregate boundary reconciliation keeps the floored pocket |
| Rectangular blind step | Pocket | a floored recess open at one edge reads as a corner notch |
| Rectangular / Triangular / 6-sided passage | Passage | one family, three shapes, not distinguished |
| Triangular blind step | AngledStep | |
| Chamfer | Chamfer | |
| Round | Fillet | |
| Circular blind step | CircularBlindStep | one physical occurrence owns its cylindrical wall and blind terminal; an overlapping Fillet is reconciled away |
| O-ring | BossRecord | |
| Through hole; Blind hole | HoleRecord | |
| 2-sided through step | PairedRampStep | conservative mirror-symmetric, horizontal, three/five-terminal subset |
| Rectangular through step | ThroughStep | principal two-wall subset; independent boundary interruptions are allowed only with complete seam, terminal, envelope and empty-prism proofs |
| Slanted through step | — | **unrecognised**; tracked under recognition-effectiveness roadmap |
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
| `PairedRampStep` | One principal-axis mirror-ramp cut; `angle` is the common acute ramp angle, `length` its open-to-terminal run, and `at` the original shared-ridge midpoint. A dimensioning consumer projects `2 × angle` at `at` plus the run `length` along `axis`. |
| `ThroughStep` | One rectangular open-profile cut; `section` preserves both oriented legs and their concave corner using the two non-run coordinates in ascending XYZ order (`yz`, `xz`, or `xy`), while `length` and `axis` report the complete run and `at` is the removed-prism midpoint. |
| `CircularBlindStep` | One quarter-cylindrical corner cut; `centreline` runs from the interior terminal to the envelope opening, and `section` locates both arc endpoints and the cylinder centre in the canonical transverse coordinate pair. |
| `BoltCircle` | At least three same-spec holes, equally spaced on one circle. |
| `BossRecord` | One external full-cylinder segment; its vector axis is not restricted to a world-axis string. |
| `Chamfer` | One qualifying external, single-principal-axis planar or conical bevel; `turned` is true only for the conical shaft treatment. |
| `Channel` | One floored rectangular recess open at both ends of its longitudinal solid envelope. |
| `CounterBore` | One coaxial cylindrical hole step used as either the `cbore` or `spotface` field of `HoleRecord`. |
| `CounterSink` | One proved conical seat at a matching cylindrical bore mouth. |
| `DoubleDBore` | One constant principal-axis through double-D void; recogniser output always has `through=True`. |
| `FaceLevel` | One body-local horizontal Z-level occurrence plus optional XY support spans; equal values on separate solids retain multiplicity, and the record does not claim a dimension requirement. |
| `Fillet` | One qualifying external, single-principal-axis cylindrical or toroidal edge blend; a cylindrical blend requires one unambiguous nearest supporting plane on each transverse axis, and `turned` is true only for the toroidal shaft treatment. |
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
| `PolygonalBoss` | One attached regular hexagonal principal-axis boss; `axis` is `"x"`, `"y"` or `"z"`, `side_count=6`, and `base`/`top` are ascending coordinates along that axis. |
| `PolygonalStock` | One whole regular hexagonal principal-axis prism; `axis` is `"x"`, `"y"` or `"z"`, and `side_count=6`. `base`/`top` are coordinates along that axis while centre and flat geometry remain 3-D in the recognition frame. |
| `RaisedPad` | One bounded rectangular principal-axis island. XYZ bounds locate the exact local occurrence; `axis` identifies its attachment-to-terminal coordinate and `direction` is `1` or `-1` for the material-outward terminal side. Overlapping axis readings select the unique shortest attachment span; a tied minimum is refused without a world-axis preference. |
| `RectGrid` | A complete rectangular lattice of same-spec holes with the documented row/column basis convention. |
| `RepeatingRadialProfile` | Geometry-only proof of complete outer-profile rotational repetition, defined by its two original opposed extremal planar source faces; not gear semantics. |
| `RiserEvidence` | One body-local full-span candidate riser before consumer-specific projection; `body_levels` retains the complete same-solid FaceLevel occurrences (`null` only for hand-built legacy records). `project_step_shoulders(..., levels_by_riser=...)` provides explicit occurrence-aligned selection when separate bodies have value-identical levels. |
| `SectionPassage` | The sole attributed PASSAGES output: canonical frame, run interval, intrinsic section and explicit open ends. |
| `Slot` | One enclosed through-slot; no floor and no open longitudinal end. |
| `SlotArray` | At least three identical compatible through-slots on one constant-pitch line. |
| `SlotGrid` | A complete rectangular lattice of identical compatible through-slots. |
| `StepShoulder` | One occurrence-preserving pure projection from body-local `RiserEvidence` plus a caller-supplied level set, not a recogniser return. |
| `TurnedProfile` | One consumer aggregate for a single physical turned body/profile, grouped from `TurnedStep` values rather than returned by a recogniser. |
| `TurnedProfileKey` | Serializable body-local membership shared by the steps of one physical turned profile; it records the principal axis line and body bounds without exposing topology identity. |
| `TurnedStep` | One self-contained shaft segment carrying its physical profile membership; recognition requires a multi-step profile. |

`RecognitionResult` is the frozen orchestration inventory rather than a `Record`
subclass. It owns every public recogniser family, preserves classification-gated
empty inventories explicitly, and makes no claim that every geometry fact has
Draftwright IR, DSL, code-generation, drawing, or completeness semantics.

The framing lifecycle is the ordinary aggregate route for new integrations.
`build_framed_recognition_result()` retains its explicit caller-supplied classification.
`prepare_framed_part()` returns either a
typed frame refusal or a `PreparedFramedPart` pairing the exact normalized working shape, frame,
and precomputed cylinder substrate. A consumer may inspect those local facts, then call
`prepared.recognise(rotational=...)`; the existing aggregate runs once with that classification
and without repeating cylinder analysis. This lifecycle does not expose the private graph,
Candidates, evidence, registry, or reconciliation state, and does not move downstream view or
drawing policy into this package.

`build_raw_recognition_result()` is the explicit caller/world-coordinate route. The historical
`build_recognition_result()` name remains its compatibility alias through 0.4.x and is removed in
0.5.0 rather than silently changing return type. Typed frame refusal never selects that raw route.

`build_framed_recognition_report()` pairs the exact local working shape and frame with bounded
lifecycle explanations from the same run. It records whether each physical family ran, candidate and final disposition
counts, and only the residual diagnostic codes established by frozen evidence. It does not scan
unclaimed geometry or imply that an evaluated-empty family has no unsupported related geometry.
`PreparedFramedPart.recognise_report()` supports classification from the local part without a
second cylinder scan. `build_raw_recognition_report()` is the explicit caller-coordinate report;
`build_recognition_report()` remains its 0.4.x compatibility alias. ADR 0012 defines this
compatibility boundary; surface-cache summaries are not shipped. The [E1 validation](benchmarks/e1-bounded-explanations-validation.md) records exact
MFCAD++ parity and the separately measured projection cost.

Every public `recognise_*` export must appear exactly once in the recogniser table above. CI derives
that export inventory from the installed public module rather than trusting this page,
so adding a recogniser without an explicit capability claim fails closed even before the
versioned manifest is implemented.
