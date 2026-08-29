# ADR 0009 — Filtering belongs to a recogniser, not a shared reduction

- **Status:** Accepted
- **Date:** 2026-08-19
- **Decider:** Paul Fremantle

F4b keeps section-ring discovery neutral. Passage policy alone requires two open ends and maps the
neutral occurrence to the public record. Legacy principal-axis projection happens only after rich
Passage reconciliation; it is not a shared reduction and cannot filter or create physical
Candidates.
- **Evidence:** [epic 0002](../epics/0002-one-substrate-before-more-recognisers.md), item 0

## Context

`_recess_faces._planar_faces` reduces a solid's faces to the data three families need, and drops
any planar face whose normal is not axis-aligned:

```python
axis = _dominant_axis(nrm)
if axis is None:
    continue
```

Slots, pockets and channels all call it. None of them mentions the restriction, and no consumer
can observe it.

Measured per face over 2,000 MFCAD++ models, the consequence is the largest single recall gap in
the package:

| class | labelled faces | claimed |
| --- | ---: | ---: |
| Rectangular pocket | 3,888 | 38% |
| 6-sided pocket | 4,493 | 4% |
| Triangular pocket | 3,163 | **0%** |

The comparison that identifies the cause is `recognise_passages`, which walks face adjacency and
asks no wall to be axis-aligned. On the same solids it scores 61%, 59% and 49% across the same
three cross-sections — flat, where the recess families collapse.

**The distinction that matters is not orientation. It is where the rejection happens.** ADR 0008
drew a comparable line for lengths, between a proportional tolerance and an absolute
minimum-evidence threshold. The line here is between a gate and a filter:

| | a **gate**, inside a recogniser | a **filter**, inside a shared reduction |
| --- | --- | --- |
| visibility | belongs to the family that applies it | invisible to every family that inherits it |
| effect | rejects a candidate | discards the geometry |
| recoverable | relax the gate | nothing downstream holds the face |
| measurable | rejections can be counted per gate | there is nothing left to count |

That last row is why this went unnoticed for so long. `recognise_chamfers` can attribute its
recall loss across five named gates because they are gates. The pocket loss has no such
breakdown: 3,163 faces produce zero candidates, and no instrumentation inside the recogniser can
say why, because the faces never arrived.

`FaceGraph` already obeys the rule this record states. Its nodes carry `normal`, `bounds`,
`surface` and `edges`, and no `axis` field; every face of the part gets a node whether or not any
recogniser will want it.

## Decision

**A reduction shared by more than one recogniser is total over its input.** One output entry per
input element, with an attribute that does not apply represented as absent rather than by omitting
the entry.

Rejecting a candidate is a recogniser's decision, and belongs where it can be named, counted and
tested. A shared layer may *derive* — normals, bounds, adjacency, surface type — and may leave a
derivation undefined for an element it does not fit. It may not decide that an element is not
worth carrying.

Where a shared reduction cannot be made total, the exclusion it imposes is documented on every
family that inherits it, in [`capabilities.md`](../capabilities.md), naming the shared function.
A restriction applying to three families that appears in the documentation of none is the failure
this record exists to prevent.

**Laziness is what makes totality affordable**, and is therefore part of the decision rather than
an optimisation beside it. Carrying every face costs nothing if attributes are computed on first
ask, which is the property `FaceGraph` was built with and the reason it can afford to have no
admission criterion. A total reduction that computed eagerly would trade this record's benefit
for the cost the filter was avoiding.

## Consequences

More faces reach each recogniser, so per-family gates grow and the work each family does to
reject a candidate becomes visible. That is the intended trade: a longer, testable gate list in
one family is better than a short one shared silently by three.

This is narrower than it may read. It does not require every recogniser to handle oblique
geometry, and it does not settle whether oblique recesses are in scope — that stays a capability
decision with its own evidence. It requires only that the answer be *a recogniser's* to give, and
therefore visible to anyone reading that recogniser or measuring its output.

It also does not reopen the graph-versus-rules question. ADR 0004 decides for an attributed
graph and against subgraph matching; a total reduction is compatible with entirely procedural
recognisers, which is what `recognise_passages` demonstrates.

## Amendment (Channel wall attribution, issue #225)

Channel attribution does not add a shared-reduction filter. `_planar_faces` remains total over
planar faces and retains graph identity; Channel discovery itself continues to decline oblique or
edge-ineligible walls and carries only the accepted opposed pair into its proposal. The floor and
boundary facts consulted by the predicate do not become defining evidence merely because the
shared reduction exposed them.

The neutral #234 provenance carrier does not add a filter. Geometry-only and provenance reads use
the same Slot/Pocket candidates and reducers; the latter merely retain exact nodes and cap clusters.
Ambiguous competing physical cap clusters refuse only the private provenance read, while the frozen
record-only compatibility projection keeps its historical first-win behavior.

Issue #235 does not move any Slot predicate into the evidence layer. The same proposal inventory,
merge/collapse decisions and cap selection establish both writer-free records and writer-enabled
occurrences. The writer adapter validates identity and one-body provenance only; it neither reads
other family outputs nor adds an acceptance or reconciliation filter.

Issue #236 adds no Pocket admission predicate. Writer-enabled discovery publishes the exact
sources retained by the same proposal and reduction path after identity and one-solid validation;
writer-free discovery retains the historical record-only ambiguity behavior.

## Amendment (Polygonal Boss blend-cycle gate, issue #192)

F3b adds no filter to `_blend_view`, `_effective_surfaces` or `FaceGraph`. Those neutral layers
continue to expose every supported fact or a closed refusal. Polygonal Boss alone applies the
visible consumer gate: six retained planar vertical supports, exactly six eligible convex singleton
chains, one degree-two cycle, no touching competing eligible chain, and the existing regular-hex,
cap and height predicates. A missing, partial, concave, multi-node, ambiguous or competing cycle is
declined by this recogniser without changing the neutral result or any sibling family. Polygonal
Stock and all other consumers remain base-graph-only.

Issue #297 adds no shared filter. `FaceGraph` still exposes every face and the shared bevel reader
still returns every supported single-axis oblique plane. `recognise_paired_ramp_steps` alone applies
the visible mirror-pair, principal-run, arc, exterior-opening and terminal gates.
