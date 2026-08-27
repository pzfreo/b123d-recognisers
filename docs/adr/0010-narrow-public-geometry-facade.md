# ADR 0010 — Publish a narrow geometry facade; keep correspondence optional

- **Status:** Accepted
- **Date:** 2026-08-26
- **Accepted:** 2026-08-27
- **Decider:** Paul Fremantle
- **Evidence:** [epic 0004 retrospective](../epics/0004-architecture-retrospective.md),
  [F7 geometry facade spike](../f7-geometry-facade-spike.md)

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

## Amendment (F7 consumer spike, issue #262)

**The permitted surface in the decision above is wider than the evidence supports, and the
roster is narrower than a facade.** The spike recorded in
[`docs/f7-geometry-facade-spike.md`](../f7-geometry-facade-spike.md) ran two consumers through a
provisional `GeometryGraph`. Polygonal Boss — in-package — exercised the whole surface, which
proves the facade is *sufficient* and is not evidence that any consumer *needs* it. Draftwright's
real workflow, declaring a fillet from its cylindrical face, needed one analytic fact and one
on-surface anchor. Constructing a graph around a single face is conceptually larger than the
problem, so the spike returned no-go on publishing `GeometryGraph` and go on the graph-independent
`inspect_face(face)` contract.

Two consequences for the decision above.

**Blend facts, collapsed views and intrinsic section values leave the initial roster.** They are
named as permitted, and no installed-wheel Draftwright operation consumes them. They remain
private until a reviewed consumer demonstrates a need, on the same rule this ADR already applies
to correspondence.

**The initial roster is the declared-feature inspection family, not a geometry facade.** Every
declared feature in Draftwright needs the same shape of answer — one closed analytic fact off one
face, so that a declared feature and a detected one agree. Read from
`src/draftwright/model/declare.py` at Draftwright 0.4.16.dev0 (`a81c418`), five already exist,
spelled five different ways:

| declared feature | current entry point | status |
| --- | --- | --- |
| fillet | `experimental_geometry.inspect_face` | consumed in production, Draftwright #1347 |
| countersink | `cone_rims` | root export, countersink-family module |
| chamfer | `classify_bevel` / `BevelReject` | root export, chamfer-family module |
| double-D | `profiled_bores.read_double_d_tool` | public module, not root-exported |
| pocket floor | `floor_face_anchor` | root export |

Four of the five reach into a recogniser family's own module, which is why they read as ad hoc.
Unifying them behind one `inspect_*` contract is a smaller and more stable surface than anything
graph-shaped, and it serves the requirement they were each written for: declared/detected parity.

`experimental_geometry` stays absent from the package root exports and the capability manifest
until that roster is reviewed and accepted under #262.
