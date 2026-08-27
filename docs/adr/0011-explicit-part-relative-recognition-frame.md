# ADR 0011 — Pair local recognition with an explicit part frame

- **Status:** Proposed
- **Date:** 2026-08-27
- **Decider:** Paul Fremantle
- **Evidence:** [frame-handling evaluation](../benchmarks/frame-handling-prototype.md), issue #272,
  spike #274

## Context

Recognition currently interprets several geometric predicates and reconciliation choices in world
XYZ. A rigid X30-plus-translation presentation removes 1,571 of 2,784 occurrences in the first
500 MFCAD++ development models. The same physical part can therefore produce a materially different
inventory solely because of its STEP placement.

Making every recogniser free-axis would spread frame policy and new record schemas across the
package. Hiding normalization inside the existing entry point would silently change the meaning
of legacy axis letters and let callers mistake local coordinates for caller coordinates.

## Proposed decision

Adopt the **boundary**, but revise the current **normalization mechanism** before making it public
or default:

1. A geometry-established, right-handed `PartFrame(origin, x, y, z)` maps caller-space points to a
   local recognition frame.
2. A framed recognition result pairs that frame with the existing `RecognitionResult`; all record
   coordinates and axis letters are explicitly local to the paired frame.
3. Existing `build_recognition_result(part)` behavior remains unchanged. Framed recognition is a
   separate opt-in route until its stability gate passes.
4. Frame inference is closed. Geometry with no analytic direction returns a typed refusal. A
   single established axis returns an explicit `AXIAL` gauge: its chosen roll is a deterministic
   representative and must not be treated as a semantic material axis. The prototype's remaining
   world-based line-sign convention is not accepted as production semantics.
5. Recognition still executes once through the existing registry and reconciliation stack. The
   boundary does not expose `GeometryGraph`, correspondence, candidates, or recogniser internals.

The current topology-preserving placement implementation remains experimental. It is evidence for
the contract, not a production implementation selected by this ADR.

## Evidence and gate

The complete 20-fixture golden inventory is invariant occurrence-by-occurrence under Z30, X30,
X90 and translation after independent frame inference: 75/75 same-family, with no refusal,
reclassification, absence or introduction.

On the deterministic first 500 lexical MFCAD++ test-split files used as open development data,
all 500 infer a full frame. Framed X30-plus-translation retains all 2,750 baseline occurrences,
with zero reclassifications and absences; one model introduces one extra Slot fragment. Replacing
copied BRep transformation with rigid TopLoc placement eliminated the other 12 transform-induced
occurrence differences and the macOS body-ancestry failure. A degenerate 7.1e-15 recess probe that
previously raised an OCCT domain error now fails the candidate closed.

Frame inference plus normalization consumes 16.30 seconds against 436.12 seconds of framed
recognition (3.74%). The paired framed route including that work is about 8.29% slower than the raw
paired recognition run.

Before acceptance and public exposure, a revised implementation must:

- replace the world-based positive-sign convention with geometry-established orientation,
  explicitly represent the sign gauge, or prove recogniser invariance across every admissible
  sign choice;
- preserve legacy recess semantics and publish the remaining 10098 Slot fragment as a bounded
  opt-in numerical limitation unless a frame-scoped policy can eliminate it without changing the
  legacy route;
- demonstrate deterministic results on the supported Linux, macOS and Windows CI matrix;
- repeat the named 500-model development evaluation with a checked-in machine report; and
- keep legacy public tests and goldens unchanged.

The sealed MFTRCAD holdout is not required for this architecture decision and remains unused.

## Consequences

- Callers can distinguish part placement from recognition semantics without a broad free-axis
  record migration.
- Unconstrained roll is explicit gauge rather than a hidden semantic axis; geometry with no
  analytic direction produces an explicit non-result.
- The existing public API and coordinate meaning remain compatible.
- The prototype demonstrates high value, but the placement route is not yet release quality.
- Recommendation: **revise and continue**. Do not abandon the boundary, and do not ship this
  implementation as the default recogniser path.
