# ADR 0010 — Publish a narrow geometry facade; keep correspondence optional

- **Status:** Proposed
- **Date:** 2026-08-26
- **Decider:** Paul Fremantle
- **Evidence:** [epic 0004 retrospective](../epics/0004-architecture-retrospective.md)

## Context

Epic 0004 established graph-owned identity, analytic-surface facts, blend-collapsed views,
canonical sections, defining evidence and private cross-run correspondence. The private substrate
is intentionally rigorous, but its full implementation surface is too broad to freeze merely
because Draftwright needs some neutral geometry queries.

## Decision

F7 will publish one facade in `b123d_recognisers.geometry`, selected from concrete installed-wheel
Draftwright use cases. It may expose graph-owned opaque face/boundary/blend references, neutral
surface and blend facts, explicit collapsed views with complete provenance, and intrinsic section
values.

It will not expose or require correspondence snapshots, body-boundary descriptors, rigid or
partition matching, Candidate/evidence, registry, reconciliation, issuers, run tokens or private
cache classes. Correspondence remains an optional private upper layer until a separately reviewed
consumer demonstrates a need.

Remove superseded private schema construction paths only after a closed caller/artifact audit.
Other internal refactoring is deferred until a concrete consumer change is blocked by the current
structure. Infrastructure tidiness alone is not an F7 deliverable.

## Consequences

- Draftwright receives a smaller API and compatibility burden.
- Private implementation modules remain replaceable behind facade projections.
- F6 retains its proven capability without becoming a mandatory dependency or public framework.
- F7 starts with a consumer fitness spike rather than an export inventory.
- A future correspondence API requires a new ADR/API-major decision; it is not an additive detail
  of the initial geometry facade.

The detailed evidence and simplification programme are recorded in
`docs/epics/0004-architecture-retrospective.md`.
