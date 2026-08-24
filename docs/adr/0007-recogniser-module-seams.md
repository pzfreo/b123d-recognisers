# ADR 0007 — Internal recogniser module seams

- **Status:** Accepted
- **Date:** 2026-08-16
- **Review:** `b123d-recognisers` issue #21

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
