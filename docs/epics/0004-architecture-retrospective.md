# Epic 0004 architecture retrospective

## Conclusion

The geometry-foundation direction is sound, but its implementation and assurance burden grew
beyond what an initial Draftwright consumer should inherit. Graph-owned identity, complete
provenance, recogniser-owned policy, canonical section values and fail-closed publication are
durable benefits. The schema-3 correspondence and partition matcher is a specialised optional
capability, not the default public substrate.

The next step is therefore not to publish every private type. F7 must first prove a small facade
against concrete out-of-tree Draftwright tasks. Private implementation breadth is not evidence that
the same breadth belongs in a supported API.

**Outcome follow-up:** the completed F7 spike found that Draftwright needed one graph-independent
face inspection plus four existing declared-feature family reads, not a graph facade. ADR 0010 and
#186 therefore publish `b123d_recognisers.inspection`; `GeometryGraph`, blend views, sections, and
correspondence remain private or experimental. The pre-spike recommendations below are retained as
the reasoning record, not as the current export roster.

## What the epic bought

- Geometry references are issued by one graph and cannot be replaced by ordinal, hash, copied
  wrapper or rounded-record coincidence.
- Native and recovered analytic facts retain refusal, orientation and recovery provenance.
- Blend collapse is an explicit selected view whose synthetic nodes and arcs expand to complete
  original geometry; it is never automatic feature ownership.
- Feature policy remains in each recogniser. F3b demonstrates that Polygonal Bosses can consume a
  collapsed view without changing Polygonal Stock, Fillets, reconciliation or unrelated families.
- Defining evidence describes the geometry that physically establishes an occurrence.
- Canonical sections and issuer-bound body descriptions make deterministic cross-run reasoning
  possible without treating OCCT traversal presentation as identity.
- Late failure and ambiguity do not publish a plausible-looking partial answer.

These properties address observed defects. They are not candidates for removal merely to reduce
line count.

They are also not all delivered user capability. F1 completed analytic fitting and neutral query
authority, but not recogniser migration: the current reader roster has 0 of 64 sites migrated (29
raw-topology, 16 pending-migration, 13 orientation-deferred and 6 torus-deferred). A NURBS-only
round-trip of the simple through-hole fixture recovers all 9 faces as analytic facts while
`feature_census` still returns zero throughout. F1 stages 1 and 2 work; stage 3, the consumer
migration that creates recognition value, has not started.

F4b has a similarly bounded win. A whole part rotated away from the principal axes can retain its
Section Passage, but an oblique feature inside an otherwise upright part remains unrecognised. It
removes part-presentation bias, not the measured internal feature-obliquity gap.

## What cost more than expected

Four individually reasonable objectives compounded: kernel-presentation independence,
mutation-resistant authority, deterministic cross-run matching and exhaustive ambiguity instead
of heuristic selection. F6 consequently became a bounded geometric matching engine rather than a
small feature-recognition helper.

At this review point, the principal graph/surface/blend/section/body/correspondence modules contain
roughly 9,100 source lines. The corresponding principal test modules exceed 11,500 lines. Line
count is not a quality measure, but here it reflects real cognitive, review, runtime and maintenance
cost. Small changes can cross geometry, identity, cache, tolerance, provenance and lifecycle
contracts simultaneously.

The private correspondence implementation proves bounded edit hypotheses and closes ambiguity
defects in that diagnostic. It has one package orchestration caller and no public or Draftwright
consumer, so its product value is unproven. That is a reason to stop extending or publishing it,
not a claim that its existing tests should be discarded.

Performance also remains a constraint rather than a delivered benefit. The epic baseline already
recorded a 134-second census workload against a 109.651-second ceiling. New facade or consumer work
must measure the complete workload instead of assuming neutral infrastructure is free.

The F3b holdout adds no external-population confidence: its sole authorised bucket-37 attempt found
no matching models and stopped before annotations, STEP import or recognition. This is
inconclusive, not negative evidence. F3b has strong constructed, transformed and STEP evidence, but
its frequency and value in the external corpus remain unknown.

## Simplifications that preserve the benefits

1. **Keep correspondence optional.** Draftwright's initial dependency ends at graph, surface,
   blend and intrinsic-section queries. Snapshot, body-boundary, rigid matching and split/merge
   modules remain private and lazily imported unless a concrete consumer requires them.
2. **Publish one narrow facade.** Public opaque references and facts project from private
   authority. Concrete `FaceGraph`, issuer, cache and matcher classes do not become supported API.
3. **Remove superseded private schema implementations.** After an exact caller/artifact audit,
   reject obsolete run-local snapshot schemas without retaining their old construction paths.
4. **Create value before tidying internals.** Migrate recovered surfaces into one or two concrete
   recogniser families and measure the result. Split orchestration, centralise mechanics, regenerate
   guards or consolidate tests only when that consumer work is demonstrably blocked. F6 remains
   explicitly bounded to its existing LINE/CIRCLE, PLANE/CYLINDER, RRP/pure-prism grammar.

## Non-negotiable invariants

Simplification must not restore tuple position, ordinal, hash or wrapper identity as semantic
evidence; compatibility values as discovery authority; greedy/first-witness selection; tolerance
chaining; partial publication; provenance sets where occurrence multiplicity matters; copied
handles as same-run authority; or automatic blend removal for every recogniser.

## Draftwright fitness gate

Before F7 production exports, implement a small installed-wheel spike for two or three named
Draftwright operations. Record every geometry symbol it actually uses. The reviewed public facade
is the intersection of those needs and the neutral substrate contract, not the union of existing
private capabilities.

The spike must demonstrate graph ownership, at least one native/recovered surface decision, an
explicit blend selection with expanded provenance and one intrinsic section operation. It must not
import correspondence, registry, Candidate/evidence, reconciliation or private modules.

F7 then publishes only that bounded facade with a separate geometry API manifest. Any later
Draftwright need for correspondence requires its own use case, compatibility declaration and
review. Success is measured by a smaller supported surface and shorter reasoning paths while all
existing recognition, provenance, authority and deterministic-output tests remain unchanged.
