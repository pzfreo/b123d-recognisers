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

## Graduation outcome (issue #186)

The five-operation roster was reviewed and promoted in 0.4.4 as
`b123d_recognisers.inspection`, with its own closed format-1 `inspection_api.json` contract. The
recognition capability manifest remains byte- and schema-independent. Existing root,
family-module, and `experimental_geometry.inspect_face` paths are identity-preserving aliases so
the publication does not fork behavior or require a flag-day consumer migration.

Only the graph-independent surface values and operation roster graduated. `GeometryGraph`, its
opaque identities, adjacency, blend collapse, sections, correspondence, evidence, registry, and
reconciliation did not. This is the final interpretation of the original `geometry` namespace
wording above: consumer evidence selected a narrower inspection namespace, while the broader
facade remains an experiment.

## Amendment (within-run recognition evidence, issue #375)

Issue #368 supplies the consumer evidence the earlier graph-facade spike lacked: a downstream
consumer must associate one accepted, occurrence-preserving feature with the exact original faces
that define it and, later, the wider faces that constitute it. Reconstructing that association
from record coordinates would create a second attribution authority; importing private Candidate,
EvidenceIndex or FaceNode values would freeze the framework rather than a consumer contract.

Publish a separate narrow `b123d_recognisers.evidence` view over one completed raw recognition
inventory. It issues opaque `FeatureRef` and `FaceRef` values, exposes the existing immutable
`RecognitionResult`, maps a feature reference to its exact accepted record and defining face
references, and resolves a face reference to the borrowed build123d face from the exact caller
part. Equal-valued feature occurrences retain different references. References are issuer-created,
compare only by same-view object identity, cannot be serialized, and fail closed when forged,
copied or supplied to another view.

This is **run-local reference**, not persistent naming. A face reference contains no public index,
kernel hash, geometry-derived pseudo-identity or cross-run equality. The caller must not mutate the
part while using the view. Equivalent re-imports and rigid transforms may produce equivalent
records and face geometry, but never interchangeable references. Symmetric faces may be genuinely
indistinguishable; any future persistent API must use the separately reviewed correspondence layer
and represent ambiguity rather than resolve it through traversal order.

The view does not publish adjacency, blend collapse, graph construction, Candidate/evidence
objects, reconciliation, issuers, run tokens or correspondence. It runs the existing aggregate
once and projects its accepted inventory; it neither calls recognisers again nor changes
recognition. Constituent membership is added by #368 only after its defining-subset invariant is
reviewed. Framed recognition is excluded until it can map evidence back to faces of the caller's
part; a working-shape face must not silently escape as caller identity.

The new namespace has an independent closed installed API manifest. It does not change inspection
format 1 or the recognition capability manifest, because neither document describes run-local
reference operations.

## Amendment (constituent face projection, issue #368)

The same run-local view may project an accepted occurrence's **constituent** faces alongside its
existing **defining** faces. Defining evidence keeps its exact meaning: it is the evidence that
establishes the record and remains the only face set consulted by claims, reconciliation,
dispositions, diagnostics and correspondence. Constituent evidence is physical membership for
downstream selection and coverage; it is not ownership or precedence.

The terminal evidence issuer enforces `defining` as a subset of `constituent`, exact graph-issued
identity and one valid solid. Omission means constituent is the exact defining set, so an
unmigrated family fails closed rather than guessing from adjacency. A face may be constituent to
more than one accepted occurrence, and membership queries preserve occurrence identity and
proposal order without turning overlap into a contest.

Wider membership must retain identities already selected by the recogniser's accepted geometry
proof. It must not be reconstructed later by coordinate matching, adjacency flood-fill, corpus
labels or a second recognition pass. In particular, interrupted or blend-owned faces do not
become constituents merely because they touch a feature. The public
`RecognitionEvidence.constituent_faces()` method is therefore an additive projection through the
existing `FeatureRef` and `FaceRef` carrier; it adds no durable face name and does not alter the
format-1 manifest boundary.

## Amendment (Prismatic Pocket cap membership, issue #403)

The neutral ring proof retains the exact graph nodes whose end-bounded adjacency establishes each
cap instead of reducing them immediately to two booleans. `PrismaticPocket` publishes the cap at
its accepted closed end as constituent evidence together with its defining wall ring. Defining
evidence, claims, reconciliation and the public record remain wall-only and unchanged.

This is retention at the existing decision site, not a later floor search. All cap patches that
the unchanged proof accepts at the closed end are retained; none is chosen by corpus label,
coordinate rematching or adjacency expansion after recognition. Passages and rejected enclosed
cavities publish no Prismatic Pocket evidence. Non-exclusive membership remains valid when an
accepted cap patch is also constituent to another occurrence.

## Amendment (Pocket bounded-region membership, issue #420)

The prohibition on reconstructing wider membership later by adjacency flood-fill remains. A narrow
exception is admitted inside the final neutral Pocket proposal proof: an exact inner-wire seed may
traverse concave or smooth original graph arcs and associate the resulting bounded region with the
exact retained wall, cap and floor nodes. This occurs before Candidate issuance; the public evidence
view performs no search or rematch. Both association directions must be one-to-one, and invalid or
ambiguous cases fall back to the existing constituent set. The opening face is proof context, not a
constituent, and defining evidence is unchanged.

This is physical run-local membership, not ownership or persistent identity. It publishes no
adjacency, cavity API, graph type or durable face name.

## Amendment (public oriented Slot projection, issue #310)

`OrientedSlot.source` does not expose the private section graph. It nests the already supported
immutable `SectionPassage` value so callers receive the exact frame, span, serialized rectangle
and open-end proof that authored the projection. Original-face identity remains available only
through the run-scoped evidence facade.
