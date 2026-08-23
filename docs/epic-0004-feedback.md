# Review feedback: Epic 0004 — Geometry foundation generalisation

Review of [`docs/epics/0004-geometry-foundation-generalisation.md`](epics/0004-geometry-foundation-generalisation.md)
at commit `479fed6` (branch `codex/foundation-epic`), 23 August 2026. Companion to
[`scorecard.md`](scorecard.md), whose projected post-epic grades assume this epic's exit gates.

**Overall: sound, and a faithful translation of the scorecard's gaps into the house's evidence
discipline.** The plan preserves the epic-0003 phase boundary (canonicalisation as neutral
context derivation that cannot issue Candidates), prefers immutable views over destructive
rewriting, sequences measurement (F0) before capability, and gates every phase on
byte-identical goldens. All checkable claims — baseline `44e74df`/`0.3.2.dev0`, ADR references,
named symbols (`RecognitionContext`, `EvidenceSink`, `FaceNode`, `FaceGraph`, `smooth_region`,
`ArcKind`, the `axis: str` recess fields), epic numbering and file conventions — verified
against the tree at that commit.

## Findings

1. **F1 torus recovery exceeds the documented OCCT seam.** F1's contract mandates torus
   recovery from B-splines, but `ShapeAnalysis_CanonicalRecognition` (OCCT 7.7+) documents
   only plane/cylinder/cone/sphere fits. Torus matters here — turned-stock fillets and grooves
   are the toroidal consumers — so it will need bespoke fitting machinery. The risk table
   should carry a row for it before implementation starts, with a containment (e.g. torus
   recovery as a separately gated increment) so a slip does not fail the whole F1 exit gate.

2. **The cited scorecard needs a link and a merge-order decision.** The epic's motivation
   cites "the 3D geometry scorecard", which at `479fed6` exists only on the
   `claude/3d-geometry-scorecard-gkspkr` branch, with no link. Either merge the scorecard
   branch first or link [`scorecard.md`](scorecard.md) from the epic — epic 0003 links its
   source review (#162), so a link matches house style.

3. **ArcKind target count — resolved in the epic's favour.** F2's smooth-neutral /
   smooth-concave / smooth-convex taxonomy (4 → 6 values) initially contradicted the
   scorecard's "four to seven values". The epic is correct: `unknown` already covers Analysis
   Situs's `Undefined`, and non-manifold input is out of scope, so only the smooth-sided pair
   is needed. The scorecard has been corrected; no epic change required.

## Sequencing recommendation: split F4, land its schema half early

F4 carries the oblique half of the geometric-generality improvement plus the entire coverage
improvement, yet sits sixth of seven in the recommended order. It is also the only package
with a clock on it: every release shipped meanwhile pins the axis-span schemas deeper into the
ADR 0005 compatibility window and the downstream contract. Partial completion is the realistic
case for a seven-package epic on a bus factor of one, and under the current order a
half-finished epic yields canonical recovery while leaving the axis-aligned corner intact.

F4 as written bundles two very different risks:

- **the schema** — the versioned `LocalFrame`/`PlanarSection` records, deterministic
  frame/winding tie-breaks, and dual projection parity for principal-axis inputs: additive,
  cheap, and requiring no recogniser changes;
- **the oblique predicates** — the genuinely hard geometry work in the `_recess_*` subsystem.

Recommendation: land the schema immediately after F0, before F1; deliver the oblique
predicates family-by-family later (the shape F5 already prefers). This defuses the 1.0 corner
even if the epic stalls, and lets F1's equivalence fixtures, F5's evidence migration and the
section-supersedes-fragment reconciliation rule be written once against the final schema
instead of twice.

## Adopted: F7 — Published substrate (framework) API

Direction accepted by the project owner (August 2026): once the epic's neutral APIs settle,
the substrate becomes a public product. Proposed as a new terminal work package in the epic's
own style:

### F7 — Published substrate API

Promote the neutral geometry substrate to a public, versioned framework contract so that
third-party recognisers can build alongside this package without forking it. Adjudication
remains closed: an external recogniser consumes the substrate and returns its own records; it
does not enter `build_recognition_result`, reconciliation, the census, or the capability
manifest.

Required contract:

- the published surface covers, at minimum: graph construction and queries (`FaceGraph`,
  arc kinds including the F2 smooth-sided values, `smooth_region`), the F1 effective-surface
  query with residual and provenance, the F3 collapsed-view queries, and the F4
  `LocalFrame`/`PlanarSection` primitives;
- the registry, disposition table, `FamilyId`, evidence sink/index and reconciliation remain
  private; no dynamic registration, filesystem discovery or plugin import path is introduced;
- the substrate API is versioned and manifest-declared under ADR 0005 discipline, with a
  documented compatibility window, and its exports are enumerated by a completeness test the
  same way recogniser exports are;
- determinism guarantees are stated per query (same part, same facts, any platform) and pinned
  by golden evidence, so external consumers inherit the same contract internal families rely
  on;
- a documented graduation path states what an out-of-tree family must present to enter the
  closed registry: fixtures, semantic goldens, capability row, corpus evidence — the same bar
  `adding-a-recogniser.md` sets internally.

Sequencing: strictly after F1–F4 settle the APIs being published. Freezing the substrate
mid-epic would tax every subsequent package; publishing at epic exit costs almost nothing.
This is the one package that moves the scorecard's ecosystem-reach grade, and it converts the
project's governance ceiling (one maintainer's evidence throughput) into an ecosystem: external
families become a nursery, proving themselves out-of-tree and graduating with evidence in hand.

Exit gate: a demonstration out-of-tree recogniser (separate package, not vendored) builds a
working family against only the published API and documented contracts; the substrate API is
covered by the capability manifest and a versioned compatibility test; no internal adjudication
symbol is reachable from the public surface.

## Review provenance

Single-pass inline review (no separate adversarial verify stage); findings verified against
the repository tree at `479fed6` rather than taken from the diff alone.
