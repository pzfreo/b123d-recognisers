# Review feedback: Epic 0004 — Geometry foundation generalisation

Review of the epic plan as first proposed at `479fed6` (branch `codex/foundation-epic`),
23 August 2026. The epic document is carried on this branch **with every amendment below
already applied**, so this page is the review record, not a to-do list. Companion to
[`scorecard.md`](scorecard.md), whose projected post-epic grades assume the amended epic's
exit gates.

**Overall: sound, and a faithful translation of the scorecard's gaps into the house's evidence
discipline.** The plan preserves the epic-0003 phase boundary (canonicalisation as neutral
context derivation that cannot issue Candidates), prefers immutable views over destructive
rewriting, sequences measurement (F0) before capability, and gates every phase on
byte-identical goldens. All checkable claims — baseline `44e74df`/`0.3.2.dev0`, ADR references,
named symbols (`RecognitionContext`, `EvidenceSink`, `FaceNode`, `FaceGraph`, `smooth_region`,
`ArcKind`, the `axis: str` recess fields), epic numbering and file conventions — were verified
against the tree at `479fed6`.

## Findings and their resolutions

1. **F1 torus recovery exceeded the documented OCCT seam.** F1's contract mandated torus
   recovery from B-splines, but `ShapeAnalysis_CanonicalRecognition` (OCCT 7.7+) documents
   only plane/cylinder/cone/sphere fits — and torus matters here, because turned-stock fillets
   and grooves are the toroidal consumers. *Applied:* F1 now names the seam gap, makes torus a
   separately gated increment so a slip narrows scope explicitly instead of failing the
   package, and the risk table carries a containment row.

2. **The cited scorecard was absent from the tree, with no link.** The epic's motivation cited
   "the 3D geometry scorecard", which existed only on a different branch. *Applied:* the epic
   and [`scorecard.md`](scorecard.md) now travel in the same PR, and the epic links both the
   scorecard and this feedback record — matching epic 0003's practice of linking its source
   review (#162).

3. **ArcKind target count — resolved in the epic's favour.** F2's smooth-neutral /
   smooth-concave / smooth-convex taxonomy (4 → 6 values) initially contradicted the
   scorecard's "four to seven values". The epic was correct: `unknown` already covers Analysis
   Situs's `Undefined`, and non-manifold input is out of scope, so only the smooth-sided pair
   is needed. *Applied:* the scorecard was corrected; the epic is unchanged on this point.

## Sequencing amendment: F4 split, schema half early

F4 carried the oblique half of the geometric-generality improvement plus the entire coverage
improvement, yet sat sixth of seven — and it is the only package with a clock on it, since
every release shipped meanwhile pins the axis-span schemas deeper into the ADR 0005
compatibility window. Partial completion is the realistic case for an epic this size on a bus
factor of one, and under the original order a half-finished epic would have yielded canonical
recovery while leaving the axis-aligned corner intact.

*Applied:* F4 is split into **F4a** (the versioned `LocalFrame`/`PlanarSection` schema with
byte-identical principal-axis projection — additive, cheap, no recogniser changes) and **F4b**
(the family-by-family oblique predicates in `_recess_*`). F4a moves to second in the
recommended order, immediately after F0, so the 1.0 corner is escaped even if the epic stalls
and later fixtures are written against the final schema once instead of twice.

## Adopted addition: F7 — Published substrate API

Direction accepted by the project owner (August 2026) and *applied* as the epic's new terminal
package: once F1–F4a settle the neutral APIs, the substrate — graph and arc queries, the
effective-surface query, collapsed views, frames and sections — is promoted to a public,
versioned framework contract under ADR 0005 discipline. Adjudication stays closed (registry,
dispositions, evidence machinery and reconciliation remain private; no plugin path), so the
determinism and manifest guarantees are untouched; extension moves out-of-tree, with a
documented graduation path into the closed registry at the same evidence bar
`adding-a-recogniser.md` sets internally.

This is the one package that moves the scorecard's ecosystem-reach grade, and it converts the
project's governance ceiling — one maintainer's evidence throughput — into an ecosystem:
external families become a nursery, proving themselves out-of-tree and graduating with
evidence in hand. It runs strictly last because publishing earlier would freeze APIs the other
packages are still shaping. Full contract and exit gate: see F7 in the
[epic](epics/0004-geometry-foundation-generalisation.md).

## Review provenance

Single-pass inline review (no separate adversarial verify stage); findings verified against
the repository tree at `479fed6` rather than taken from the diff alone.
