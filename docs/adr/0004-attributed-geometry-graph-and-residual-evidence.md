# ADR 0004 — Attributed geometry graph and residual evidence

- **Status:** Accepted
- **Date:** 2026-08-15
- **Decider:** Paul Fremantle

## Context

Current recognisers repeatedly traverse faces and encode adjacency assumptions locally. That makes
it difficult to explain why a feature was accepted, detect important geometry no recogniser
claimed, or prevent two recognisers from silently owning the same region.

Analysis Situs demonstrates a useful substrate: an attributed adjacency graph whose nodes
represent B-rep faces and whose arcs capture neighbourhood and transition properties. This ADR
adopts the architectural pattern, not an Analysis Situs runtime dependency or copied algorithm.

[Prior art: graph-based feature recognition](../prior-art-feature-recognition.md) records what that
substrate is in detail, what the field built on it since, why the learned branch is closed to this
package, and what the labelled corpora can and cannot evidence.

## Decision

Introduce an immutable per-run attributed geometry graph:

- nodes identify faces or normalized regions and carry surface, orientation and measurement facts;
- arcs identify shared boundaries and carry concave, convex, smooth and other relevant relations;
- recogniser candidates claim node/region identities and cite evidence predicates;
- reconciliation records the disposition of every claim;
- residual analysis classifies unclaimed evidence as confidently irrelevant, ambiguous,
  unsupported, or potentially dimension/manufacturing-defining.

Raw face indices may be useful within one run but are not persistent semantic identity. Public
records contain stable geometry-derived identities and serialisable evidence summaries, never
live OCP face objects.

The graph is recognition infrastructure. It does not decide whether residual geometry should be
dimensioned, machined, edited or shown to a user; consumers translate neutral diagnostics into
their own policy.

## Required evidence

- A graph can represent split cylindrical faces, interrupted bores and slanted transitions.
- Existing recogniser outputs remain stable for a characterization corpus.
- At least two recogniser families reuse graph evidence instead of rescanning topology.
- A synthetic unrecognised recess is reported as residual evidence.
- Fillets, stock faces and harmless face splitting do not flood residual diagnostics.
- A recogniser can see through a blend and across a split — see the amendment below.
- Graph construction and recognition stay within a measured performance budget.

## Consequences

The graph creates a coherent substrate for future rule or subgraph recognisers and enables honest
unclaimed-geometry diagnostics. It also adds memory, identity and tolerance complexity, so it is
proposed separately from the initial mechanical extraction.

## Amendment (0.2.6, issue #75)

**A blend is not only noise. It is also a bridge, and the acceptance list above only asks about
the noise.** The criterion it does carry — *"fillets, stock faces and harmless face splitting do
not flood residual diagnostics"* — treats a blend as something residual analysis must not trip
over. That is one of the two things a blend does to recognition, and it is the cheaper one. The
other is that a recogniser has to traverse *through* it: a fillet or chamfer between two regions
breaks the adjacency the recogniser is looking for, and a face split by a neighbouring feature
stops answering the question asked of it. Both cost recall, and neither shows up as a flooded
diagnostic, because they do not produce residue — they produce absence.

Two measurements, on geometry this package already ships:

- **A cone breaks band contiguity.** A manufactured groove carries a conical lead-in where the
  textbook drawing shows a sharp corner, so its two cylindrical bands never touch.
  `grooves._joined` matches a cone to both rims to see across it (issue #60). Without that the
  groove is not recognised at all — not mis-measured, absent.
- **A split triangle breaks a topological count.** `recognise_angled_steps` identifies a blind end
  by an axis-aligned neighbour bounded by exactly three edges. Where a neighbouring feature
  subdivides that triangle it reads as four or five and the step is missed. Instance recall is 70%
  over 120 MFCAD++ models (114 of 163), 24 of the 49 misses have no bare triangular face anywhere
  on them, and the module records the edge count as about half the recall it costs.

### What the added criterion asks

Two regions separated by a blend face are reachable under a **named** relation, and a face
subdivided by a neighbouring feature answers as one region. Both are queries a recogniser asks
for explicitly, not a widened adjacency it gets by default.

*Named* is the load-bearing word. Making blended neighbours simply neighbours would move every
existing recogniser's answers at once, which contradicts this record's own requirement that
outputs stay stable for a characterization corpus. The whole point is that a recogniser opts in
per question — as `grooves` does today, for coaxial cones landing on both rims and for nothing
else.

### What this does not adopt

Analysis Situs's `Collapse()` is the primitive for this, and it is not the shape to copy: it
mutates the graph, propagates dihedral attributes to newly inserted transition arcs only where
the angles are equal, and its own header records that `PopSubgraph()` does not clean those
attributes up afterwards. What is wanted here is a query over an immutable graph — which is what
the run-local face graph built for issue #92 already is.

## Amendment (framework consolidation, issue #161)

Candidate evidence records defining ownership only. When the narrowly named AngledStep terminal
predicate stops at a linear outer boundary whose more than three raw edges collapse to exactly
three co-directed geometric sides, discovery may issue a failed-predicate Observation carrying
its consulted terminal context. It does not infer or emit the missing AngledStep. Observations
carry closed primitive facts, freeze with the run's evidence and remain outside candidate
completeness and dispositions.

The private residual reducer is a bounded identity join over those observations and accepted
candidates, not a residual graph scan or a second recogniser. Broader residual classification,
other consulted roles and public diagnostic schemas remain future work.

## Amendment (geometry foundation, issue #180)

Epic 0004 F1 adds one private lazy `EffectiveSurfaceIndex` above `FaceGraph`. It is keyed only by
the original graph-issued `FaceNode`, reads that node's original face, derives at most one closed
native/recovered/refused fact, and never creates a replacement topology or graph. Candidate
defining and consulted evidence therefore continues to name the exact original node.

Recovered facts are geometry-only and carry `RECOVERED_UNORIENTED`; canonical axis/frame signs are
value conventions rather than material-side evidence. An oriented query refuses
`ORIENTATION_UNPROVEN` until a separately reviewed recovered-orientation capability and consumer
slice exists. F2 deliberately classifies only original native surfaces and does not unlock
recovered orientation. Original
topology, adjacency, orientation and solid-side probing remain authoritative. The index cannot
issue Candidates, classify features or mutate the graph.

## Amendment (geometry foundation, issue #181)

First-order continuity and second-order material-side enrichment are separate immutable facts.
The existing pair-level `ArcKind` and its unordered cache remain authoritative for adjacency and
compatibility traversal. A legacy `smooth` pair may additionally expose `SmoothSide` as neutral,
convex, concave or unproven. Failure to establish original closed-solid ownership, regular D2 data
or one agreeing side never rewrites the legacy arc.
For this private enrichment, build123d's ``Solid.is_valid``—its ``BRepCheck`` validity
certificate—is the closed-manifold ownership authority; an open or invalid ``TopoDS_Solid``, no
solid, or more than one owning solid is unproven.

Side observations belong to exact original shared edges and graph-issued face nodes. Every sample
on every shared edge must agree before the unordered pair receives a proved side; disagreement is
unproven. Neutral requires equivalent original native analytic surfaces through the shared
`_analytic_surfaces` authority. Recovered F1 geometry remains unoriented and cannot authorize a
material-side fact. Candidate evidence continues to name only the original face nodes.

## Amendment (geometry foundation, issue #182)

F3a adds an opt-in immutable support-bridge abstraction above the original graph. `FaceGraph`
promotes its existing closed-solid/two-face proof into issuer-owned `SolidRef`, paired
`SharedEdgeOccurrenceRef` and `EdgeOwnershipFact` values. A shared occurrence contains both exact
oriented face half-edge occurrences and preserves repeated/seam multiplicity; it is never inferred
from coordinates or traversal indices.

Selected cylindrical blend faces may be hidden from logical incidence, but every logical node and
arc expands to complete original-node and original-occurrence provenance. The base graph is never
mutated or substituted. Overlapping discovery components refuse before issuance, and selection is
atomic. Complete provenance does not imply Candidate ownership: the separately reviewed consumer
must classify expanded original nodes as defining or consulted evidence before sink issuance.
Run-local node/wire/edge ordinals provide deterministic tuple presentation only; they are not
geometric identity and invariance remains defined through explicit original-face/edge
correspondence.

F5 promotes the existing solid-membership substrate through
`FaceGraph.common_valid_solid(nodes)`. Every non-empty non-LEGACY aggregate physical defining set,
whether its family is complete or partial, must resolve to one issuer-owned valid closed `SolidRef`
before Candidate publication and again from terminal frozen evidence. Empty incomplete-family
evidence remains permitted. This proves body provenance only; each family still owns the geometric
decision separating defining faces from stock, neighbours, probes and consulted context.

Issue #185 adds a private, read-only post-reconciliation consumer for accepted Repeating Radial
Profile evidence. It revalidates exactly two original defining faces and their one common graph-
issued valid solid before projecting immutable geometry summaries. It cannot issue a Candidate,
mutate evidence, invoke discovery/reconciliation, or expose FaceNode/SolidRef/kernel handles. Equal
descriptor values preserve multiplicity and are compatibility evidence, never identity.
