# ADR 0004 — Attributed geometry graph and residual evidence

- **Status:** Proposed
- **Date:** 2026-08-15
- **Decider:** Paul Fremantle

## Context

Current recognisers repeatedly traverse faces and encode adjacency assumptions locally. That makes
it difficult to explain why a feature was accepted, detect important geometry no recogniser
claimed, or prevent two recognisers from silently owning the same region.

Analysis Situs demonstrates a useful substrate: an attributed adjacency graph whose nodes
represent B-rep faces and whose arcs capture neighbourhood and transition properties. This ADR
adopts the architectural pattern, not an Analysis Situs runtime dependency or copied algorithm.

## Proposed decision

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

## Required evidence before acceptance

- A graph can represent split cylindrical faces, interrupted bores and slanted transitions.
- Existing recogniser outputs remain stable for a characterization corpus.
- At least two recogniser families reuse graph evidence instead of rescanning topology.
- A synthetic unrecognised recess is reported as residual evidence.
- Fillets, stock faces and harmless face splitting do not flood residual diagnostics.
- Graph construction and recognition stay within a measured performance budget.

## Consequences

The graph creates a coherent substrate for future rule or subgraph recognisers and enables honest
unclaimed-geometry diagnostics. It also adds memory, identity and tolerance complexity, so it is
proposed separately from the initial mechanical extraction.

