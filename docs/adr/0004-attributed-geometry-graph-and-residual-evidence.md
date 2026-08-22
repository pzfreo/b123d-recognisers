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

The 0.2.10 recess phase-purity work implements a narrow precursor to the disposition requirement:
every discovered recess candidate receives one internal accepted/rejected reason after discovery.
It does **not** implement residual analysis or public ambiguous/unsupported outcomes, and therefore
must not be cited as satisfying those required-evidence items.

## Amendment (0.2.11, logical planar wall regions)

The split-face limb now has a second family consumer. `FaceGraph.coplanar_region` is the cached,
immutable gAAG query for patches reachable across **direct material-side zero-angle** adjacency
while remaining planar.
It is intentionally narrower than `smooth_region`: a plane-to-fillet-to-plane tangent path does
not make the two planes one boundary region. Angled-step terminal evidence and prismatic-ring wall
normalization share this neutral query; their feature predicates remain in their family modules.

For rings, graph connectivity is necessary but not sufficient. Multiple source patches become one logical
wall only when cancelling internal seams leaves one valid, hole-free rectangular exterior aligned
with the proposed run axis. Logical walls must then satisfy the pre-existing equal-span, degree-2
cycle, simple-section, void and cap proofs. This normalizes representation without interpreting a
genuine multi-patch notch, lateral breakout, step or branch as a constant sweep. The stricter
rectangle proof is a normalization precondition, not a retroactive restriction on pre-existing
singleton walls, which may contain an inner wire made by another intersecting void. Every source
node remains in the accepted claim; no virtual face or missing wall area is claimed.

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
- **A split triangle used to break a topological count.** `recognise_angled_steps` identified a
  blind end by an axis-aligned neighbour bounded by exactly three edges. Where a neighbouring
  feature subdivided that triangle it read as four or five and the step was missed. Historical
  instance recall was 70% over 120 MFCAD++ models (114 of 163), and 24 of the 49 misses had no bare
  triangular face anywhere on them. Issue #111 implements this criterion as a named immutable
  query: smooth-connected patches are restricted back to one coplanar terminal region, internal
  edges are cancelled, and its actual exterior must reduce to three straight runs. It does not
  replace that exterior with a convex hull or traverse through tangent curved faces.

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
