# ADR 0007 — Internal recogniser module seams

- **Status:** Accepted
- **Date:** 2026-08-16
- **Review:** `b123d-recognisers` issue #21

Writer capability is intentionally absent from the Step Level and Riser registry adapters. Their
public values are not injective occurrence keys, so adding a writer seam would either select a
source by traversal order or publish a cross-solid defining set. A future seam requires a reviewed
identity or multi-source ownership contract first.

## Context

`_features.py` combines the cylinder face scan, hole/boss interpretation, and pure pattern
geometry. `slots.py` likewise combines wall/floor scanning, slot/pocket/channel interpretation,
and pure pattern geometry. The runtime orchestrator already computes cylinder and feature
inventories once and injects them into consumers, but those file boundaries conceal that flow and
make changes to one family appear coupled to the others.

The split must be mechanical. ADR 0001's standalone geometry-only boundary and ADR 0002's
single-inventory recogniser contract remain authoritative. In particular, moving code must not add
a scan, change a record, reorder a result, or create another public import path.

## Dependency graph before the move

The two oversized modules currently contain these acyclic logical layers:

```text
_features.py
  cylinder substrate: analyse_cylinders -> full_cylinders
  hole/boss layer:    cylinder substrate -> recognise_holes / recognise_bosses
  pattern layer:      HoleRecord -> shared 2-D pattern geometry -> recognise_hole_patterns

slots.py
  wall/floor core:    one planar/cylindrical face inventory and candidate geometry
  recess layer:       wall/floor core -> recognise_slots / recognise_pockets / recognise_channels
  pattern layer:      Slot/Pocket records -> shared 2-D pattern geometry
```

`result.py` owns orchestration and is the only place that creates the shared cylinder inventory.
The pocket/slot pattern code currently imports generic pattern helpers lazily from `_features.py`;
that reverse-looking dependency is the seam to remove.

## Decision

Use private implementation modules and retain `_features.py` and `slots.py` as compatibility
facades. The post-move graph is:

```text
_geometry / _record / _typing
          |
          +--> _cylinder_substrate
          |          |
          |          +--> _hole_features
          |
          +--> _pattern_geometry
                     |       |
                     |       +--> _hole_patterns
                     |       +--> _recess_patterns
                     |
          +--> _recess_faces --> _recess_reduce --> _recess_obround
                                            |             |
                                            +------+------+
                                                   v
                                            _recess_core --> _recess_features

_features.py  --> _cylinder_substrate + _hole_features + _hole_patterns
slots.py      --> _recess_features + _recess_patterns
```

`_pattern_geometry` is record-agnostic and performs no topology scan. `_cylinder_substrate`
performs the sole cylinder-face inventory scan. The recess group performs the shared wall/floor
candidate work used by the three recess recognisers, in four layers -- see the amendment below. Family modules interpret injected/shared
evidence; they do not call sibling recognisers.

All new modules are private. Existing root imports, facade imports, object identity, signatures,
record serialization, and `__module__` values remain compatible. The compatibility facades contain
re-exports only; they are not second implementations.

## Enforced boundaries

Architecture tests derive the package import graph and reject cycles, any Draftwright import, and
any unreviewed public module. They also assert the allowed internal dependency edges and facade/root
symbol identity. Orchestration tests continue to count the cylinder substrate once, while exact
goldens, determinism tests, benchmarks, and installed-archive audits protect behavior and artifacts.

## Consequences

- A hole/boss change no longer shares a file with generic pattern allocation, and a recess-family
  change no longer shares a file with its pure pattern interpretation.
- Shared geometry stays shared: neither recogniser families nor their pattern modules duplicate a
  topology scan.
- The installed wheel gains private implementation files but no public module or symbol. This is an
  internal patch-level change; it does not alter the capability manifest or recognition policy.

## Amendment (0.2.6, issue #127 item D)

`_recess_core` reached 1,200 lines carrying four responsibilities, which is the maintenance
hotspot this record's own consequences section was meant to prevent. It is now four modules,
split by responsibility rather than by family, because the three recess families share almost
everything below their candidate predicates and share nothing above them:

| Module | Owns |
| --- | --- |
| `_recess_faces` | the face read, the candidate end/floor probes, and the coincidence bands |
| `_recess_reduce` | merging, collapsing and body-scoping candidates into features |
| `_recess_obround` | cylindrical end caps, and the slots and pockets recovered from them |
| `_recess_core` | what a slot, a pocket and a channel each are, given those three |

The layering is strict and downward, and the architecture tests assert it edge by edge rather
than merely rejecting cycles. That is the property the split was for: a predicate belonging to
one family cannot quietly become substrate for the other two without the import map saying so.

No public symbol, signature, record value or `__module__` changed, and the split is verified
byte-identical over the whole corpus. It remains an internal patch-level change, exactly as
this record's consequences describe.

## Amendment (framework consolidation, issues #156 and #157)

`_candidates` is the private run-local identity/evidence layer and depends only on immutable AAG
facts from `_adjacency`. `_claims` sits above it as a temporary compatibility facade for existing
families. Reconciliation may read the frozen `EvidenceIndex` and name the record families whose
conflicts it decides, but it may not import discovery entry points, accept `Part`, or construct
graph facts. Migrated discovery cores receive `FaceGraph` plus `EvidenceSink`, never the readable
legacy ledger. Architecture tests enforce these edges and capability shapes while later epic
stages migrate the remaining families.

## Amendment (framework consolidation, issue #159)

`RecognitionContext` owns only logically immutable neutral facts: the part, shared face-edge and
face-graph derivations, cylinder substrate and applicability classification. Evidence is not a
context field. Aggregate orchestration is split into discovery, reconciliation, derivation and
projection functions. Discovery receives the mutable write capability; reconciliation receives
candidate sets plus the terminal `EvidenceIndex`; derivation receives accepted records; projection
receives accepted and derived inventories and may not discover or decide policy.

The private `InventoryProduct` is the sole bridge to census and attribution tools. Those consumers
may inspect its accepted identities and frozen evidence but may not invoke recognisers or repeat a
filter. This preserves the existing family-owned geometry predicates while making orchestration
direction executable rather than conventional.

## Amendment (framework consolidation, issue #158)

`_dispositions` is a private policy-neutral layer above candidate identity. It defines closed
outcomes/reasons, identity relationships and exact completion, but imports no recogniser record or
geometry module. `_reconcile` owns the family-specific predicates and emits partial dispositions;
the orchestration coordinator supplies default acceptance and canonical physical source order.
Projection, derived patterns and census consume computed reconciliation views and do not repeat
family policy.

## Amendment (framework consolidation, issue #160)

`_registry` is the private orchestration-to-family integration layer. It owns the closed,
source-ordered physical and derived definitions, their declared value dependencies, neutral
context applicability, internal result-field coverage and explicit census participation. Its
adapters may import family facades; family modules may not import the registry or sibling
recognisers. The registry owns no geometry predicate and `_reconcile` remains registry-blind.

Physical adapters receive neutral run services, the write-only evidence capability and a
restricted view containing only declared, already-completed physical dependencies. Derived
adapters receive only their declared accepted physical sources after reconciliation. The registry
therefore makes orchestration dependencies executable without introducing a recogniser base class,
filesystem discovery, dynamic imports or plugin behavior.

Issue #219 makes that restricted physical view an issuer-owned capability rather than a caller-
constructed mapping. Orchestration completes each registry family exactly once, then asks the
issuer for an opaque input object bound to the next definition's exact declared predecessor roster.
The registry adapter may read validated record identity and original-node/common-solid provenance
from those predecessor handles, but cannot construct, copy, broaden or enumerate the view. Family
modules continue to receive only their own write capability; they do not import CandidateInventory,
EvidenceIndex, disposition, result or reconciliation layers. The exact completed CandidateSet is
reused by terminal inventory, so no parallel dependency ledger exists.

The authority boundary is deliberately narrow. Registry definitions drive internal discovery
order, applicability, physical completeness and derived pattern order. Typed `RecognitionResult`
projection, public exports, capability/schema metadata and the stable census key order remain
explicit independent review surfaces, with tests comparing them to registry coverage rather than
generating them from metadata.

## Amendment (framework consolidation, issue #161)

`_diagnostics` is a private policy-neutral consumer above frozen evidence and completed
reconciliation. It may join issuer-validated Observations to accepted candidate identity and
project primitive diagnostic values. It may not receive `Part`, a graph, a mutable evidence sink,
or call discovery. Family-owned failed-predicate geometry remains in the family module that owns
the successful predicate; the reducer contains no replacement geometry test.

## Amendment (geometry foundation, issue #179)

`_sections` is a private standard-library-only geometry-value leaf. It owns canonical frames,
intrinsic line/arc section values, end topology, and run-local body-reference issuance; it imports
no kernel, record, graph, candidate, recognition, or policy module. `_section_adapters` sits above
that leaf and may import only `passages` and `prismatic_pockets` to prove exact principal-axis
compatibility. Recognition, reconciliation, registry, and public projection do not import or invoke
the adapters in F4a. This preserves the epic-0003 lifecycle while the public schema remains a
proposal until its later ADR 0005 publication gate.

## Amendment (geometry foundation, issue #180)

Private `_effective_surfaces` sits above `_adjacency`: it may import the graph and kernel geometry,
while `_adjacency` and family modules must not import it. `RecognitionContext` owns the concrete
run-scoped index. Later migrated family cores receive only a restricted read protocol; they cannot
construct the index or invoke its fitter. Standalone wrappers reuse an injected ledger graph when
present, avoiding a foreign `FaceNode` universe.

A machine-checked reader roster accounts for every raw `BRepAdaptor_Surface.GetType`,
`Face.geom_type`, `graph.is_planar` and equivalent classification. Each entry is migrated,
topology-only raw with a named rationale, orientation-deferred, or torus-deferred. Raw
classification cannot remain an undocumented family-acceptance path. The neutral F1 slice changes
no public signature; ADR 0002 is amended when the first consumer injection lands.

## Amendment (geometry foundation, issue #181)

`_analytic_surfaces` is a topology-free private leaf imported by both `_adjacency` and
`_effective_surfaces`. It is the sole owner of native plane/cylinder/cone/sphere canonical
parameters, finite/domain validation and equivalence. It imports only OCP and `_geometry`; it owns
no graph/node, recovery, orientation, evidence, cache or family policy. This avoids both an
`_adjacency -> _effective_surfaces` cycle and duplicated analytic conventions.

`_adjacency` remains the sole owner of legacy arcs, smooth-side observations, original-solid
eligibility and both unordered-pair caches. Production and tool/test callers are frozen in an AST
roster: compatibility traversal reads the legacy fact through `is_any_smooth`, exact nonsmooth
callers retain their named comparisons, and no family consumes `SmoothSide` in the neutral F2
slice. Family, orchestration, claim and reconciliation modules cannot be dependencies of the graph.

## Amendment (geometry foundation, issue #182)

Private `_blend_view` sits above `_adjacency` and `_effective_surfaces`. It may consume only their
restricted graph-issued ownership/occurrence and analytic-fact capabilities. It may not import
families, orchestration, claims, candidates, reconciliation or records, construct another graph or
surface index, re-walk solids, or issue evidence. Both inputs bind atomically to one graph/run.

`CollapsedGraphView` is a distinct bounded support-bridge API, not a `FaceGraph` subtype, duck type
or global context substitute. No production recogniser receives it in neutral F3a. ADR 0002 and
ADR 0009 are amended only when issue #192 authorises one named direct/aggregate family consumer.

Issue #192 authorises exactly `polygonal_bosses` to import `_blend_view` and construct
`EffectiveSurfaceIndex`, `BlendCollapseIndex` and one explicitly selected view inside its shared
direct/aggregate discovery core. The view supplies bridge incidence only; the base graph retains
all geometry, ownership and evidence authority. The consumer must expand and revalidate the exact
original provenance multiset before staging, may issue only the six planar support nodes, and may
not read Fillet Candidates, claims, evidence, dispositions or reconciliation. No orchestration
injection, public signature, whole-stock path or second family consumer is authorised. Architecture
guards derive the sole importing module and sole production constructor/view call sites.

F5 keeps attribution declarations in `_registry`; aggregate orchestration in `result` compares them
with the completed `CandidateInventory` and terminal `EvidenceIndex`. Family discovery receives only
the existing graph-bound write capability and cannot read frozen evidence, dispositions, inventory
or sibling output. `FaceGraph` alone owns common-solid membership. Generic per-face tooling consumes
one completed `InventoryProduct`; corpus adapters may compare labels but cannot rerun discovery or
define attribution status.

For the F5c Flat migration, `flats._discover_flats` is the single private writer-enabled core.
It accepts only the inseparable graph-bound `EvidenceWriter`; `_registry` is its sole production
writer-enabled caller, while the public `recognise_flats` facade invokes the same core without a
writer and keeps its existing signature. The core may write original `FaceNode` evidence but may
not read claims, frozen evidence, inventory, reconciliation, or another family's output. Stock
cylinders and an opposed Flat face remain consulted geometry rather than Candidate evidence.

For F5d, `fillets._discover_fillets` is likewise the single private writer-enabled core and
`_registry` its sole production writer caller. The public `recognise_fillets` facade keeps its
signature and calls the core without a writer. The core may issue only the original curved blend
face; neighbour planes, cylinders, sphere continuation, material probes and whole-part scale are
consulted. It cannot read claims/evidence/inventory/reconciliation, and no other family or tool may
receive its write capability.

Only turned face context is retained as graph-bindable proposal context: exact external cylinders
and the plane/sphere faces that authorize the torus branch are validated with the owner. Prismatic
neighbour coordinates and the convex material probe are transient scalar/topology decisions in the
existing algorithm; the independent role matrix rederives them, but the proposal does not claim a
complete prismatic context-node roster.

For F5e, `countersinks._discover_countersinks` is the sole private writer-enabled core and
`_registry` its sole production writer caller. The public `recognise_countersinks` facade retains
its exact signature and calls the core without a writer. The core may issue only the original
conical seat face; coaxial bore-cylinder and line/radius facts remain transient consulted geometry.
It cannot read claims, evidence, inventory, reconciliation, or another family output. Moving the
raw cylinder adaptor loop changes only its machine-owned surface-reader roster key; the existing
orientation-deferred disposition remains unchanged.

For F5f, `_hole_features._discover_bosses` is the sole private writer-enabled Boss core and
`_registry` its sole production writer caller. The public `recognise_bosses` compatibility facade
retains its exact signature and delegates without a writer. The core carries only the returned
record and immutable original segment-face snapshot; planes, cones, tori, spheres and weak curved
partners visited by the shared Hole/Boss end classifier remain transient context. No parallel
classifier trace is introduced, and the existing `_classify_end_uncached` surface-reader roster
does not move. The core may issue original segment nodes but cannot read claims, frozen evidence,
inventory, reconciliation or another family output.

For F5g, `profiled_bores._discover_double_d_bores` is the sole private writer-enabled Double-D
core and `_registry` its sole production writer caller. The public facade delegates without a
writer. The core uses shared adjacency incidence to seed four role-labelled lateral chains from
both exact openings. Traversal crosses only same-support, inward-facing continuations; each chain
must consume one high seed, cover the full interval without overlap/gap, remain nonbranching, and
stay disjoint from every other role/occurrence. It creates no parallel edge-owner store. Every
complete graph-ordered wall set binds to one valid SolidRef before first issuance. End planes,
opening profiles, bbox extrema and void-prism results remain consulted, and the core cannot read
claims, frozen evidence, inventory or reconciliation.

For the Polygonal Boss F5 migration, `polygonal_bosses._discover_polygonal_bosses` is the sole
private writer-enabled core and `_registry` its sole production writer caller.  The registry passes
its whole-run graph and writer.  Single-solid discovery may reuse that graph; multi-solid discovery
deliberately retains one local graph per solid and carries the six original side faces back to the
whole-run graph for issuance.  Terminal/support/transition caps remain transient consulted context.
The core may issue only the six side nodes and cannot read claims, frozen evidence, inventory,
reconciliation or another family output.

For Polygonal Stock attribution, `polygonal_bosses._discover_polygonal_stock` is the sole private
writer-enabled core and `_registry` its sole production writer caller. The registry passes its exact
shared graph and writer. Discovery carries selected side and cap identities through record creation,
then proves the resulting eight nodes equal the complete graph inventory and share one SolidRef.
The public facade supplies no writer, and the core reads no Candidate or reconciliation product.

For the F5 rectangular-Pad migration, `pads._discover_rectangular_pads` is the sole private
writer-enabled core and `_registry` its sole production writer caller. The public facade delegates
without a writer. The core may import only the record/type leaves plus `_geometry`, `_candidates`
and the graph-bound `_claims` writer. It carries the exact returned record, top and ordered four
wall-role snapshots through current per-solid dedup, tier suppression and sorting; it cannot read
claims, completed evidence, sibling output, disposition, inventory or reconciliation.

For the F5 Hole migration, `_hole_features._discover_holes` is the sole private writer-enabled core
and `_registry._holes` its sole production writer caller. The public facade delegates without a
writer and keeps its existing signature. The registry may pass only the shared cylinder/edge
products and restricted completed COUNTERSINKS occurrences declared by the Hole definition. The
core may validate those opaque predecessor handles and their SolidRefs, but cannot inspect a
Candidate set, EvidenceIndex, inventory, disposition, reconciliation result, or another family's
global output. CounterSink cones remain predecessor-owned consulted context.

For Channel attribution, `_recess_features._discover_channels` is the sole private writer-enabled
family core and `_registry` its sole production writer caller. The public `recognise_channels`
facade delegates without a writer even when its legacy `ledger=` parameter supplies a shared graph.
The one-solid proposal seam remains in `_recess_core`, beside the unchanged wall-pair predicate;
it carries exact low/high wall nodes but reads no evidence, inventory, sibling output or policy.

For Plate attribution, `plates._discover_plates` is the sole private writer-enabled core and
`_registry._plates` its sole production writer caller. The registry reads restricted completed
TURNED_STEPS records once for the unchanged global veto, then passes only `writer=services.writer`.
The core carries exact original low/high face clusters and reads no Candidate set, evidence index,
inventory, disposition, reconciliation output, sibling recogniser or predecessor occurrence.

Issue #234 keeps recess provenance inside the existing lower stack. `_recess_faces` issues raw
planar/cylindrical topology facts, `_recess_obround` groups exact cap patches, `_recess_reduce`
owns occurrence-preserving merge/body projections, and `_recess_core` creates Slot/Pocket
proposals. `_recess_features` may project their planar nodes into the pre-existing compatibility
ledger, but no lower module imports `_claims`, candidates, inventory, dispositions or reconciliation.

For Repeating Radial Profile attribution,
`repeating_profiles._discover_repeating_radial_profiles` is the sole private writer-enabled core and
`_registry` its sole production writer caller. The public facade delegates without a writer. The
core carries each exact returned record with its original lower/upper extremal faces through current
correspondence and sorting, binds both before publication, and reads no Candidate set, evidence
index, inventory, disposition, reconciliation output or sibling recogniser.

Issue #235 adds `_recess_features._discover_slots` as the sole writer-enabled Slot adapter over the
neutral proposal stack. The public compatibility facade and registry are its only production writer
callers; the registry supplies the run `FaceEdges` and `services.writer`. Lower face, obround,
reduction and core modules remain evidence-policy-free.

Issue #236 makes `_recess_features._discover_pockets` the sole private writer-enabled Pocket
adapter. The public compatibility facade and `_registry` are its only writer callers. Proposal,
reduction and cap modules remain neutral identity carriers and do not read evidence or siblings.

F6a adds `_body_geometry` below records/policy and `_correspondence` above the completed immutable
inventory. The lower leaf may read bounded analytic kernel facts but imports no recogniser,
Candidate, evidence, registry, reconciliation or result module. The upper module may read only its
issuer-bound product authority, accepted RRP Candidates and terminal evidence. No discovery entry
point imports it, and neither module is publicly exported.

F6b1 adds `_correspondence_match` above those two private leaves. It imports only immutable
descriptor/matching-graph values and tolerance authority from `_body_geometry`, plus snapshot
values and the issuer-validating factory from `_correspondence`. It cannot import kernel geometry,
FaceGraph/SolidRef, recognisers, Candidates/evidence, reconciliation implementation, registry,
census or result. `correspondence_changes` is optional and private; no production module calls it,
and the snapshot-only comparison leaf is closed to that entry and direct tests.

F4b adds `_section_passages` as a neutral topology producer below Passage records and policy. It
may read `FaceGraph`, analytic section primitives, and solid classification, but not Candidates,
evidence, reconciliation, results, census, or sibling recognisers. `passages` is its sole policy
caller and the sole constructor/issuer of public `SectionPassage` records.

F6b2 adds `_correspondence_partition` as a pure geometry-value leaf above `_body_geometry` and
below `_correspondence_match`. It derives bounded prism facts from immutable schema-three values
only: it imports no product/snapshot authority, kernel wrapper, graph, recogniser, Candidate,
evidence, reconciliation, registry or result module. `_correspondence_match` remains the sole
issuer-validating and policy-bearing entry, combining its singleton hypotheses with partition
hyperedges in one exact-cover proof. Split and merge remain private geometric-partition labels,
never causal CAD lineage.
