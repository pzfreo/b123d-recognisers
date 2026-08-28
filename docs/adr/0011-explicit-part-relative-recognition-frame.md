# ADR 0011 — Pair local recognition with an explicit part frame

- **Status:** Accepted
- **Date:** 2026-08-27
- **Decider:** Paul Fremantle
- **Evidence:** [frame-handling evaluation](../benchmarks/frame-handling-prototype.md), issue #272,
  spike #274, shipped framed route 0.4.3, working-shape contract #282

## Context

Recognition currently interprets several geometric predicates and reconciliation choices in world
XYZ. A rigid X30-plus-translation presentation removes 1,571 of 2,784 occurrences in the first
500 MFCAD++ development models. The same physical part can therefore produce a materially different
inventory solely because of its STEP placement.

Making every recogniser free-axis would spread frame policy and new record schemas across the
package. Hiding normalization inside the existing entry point would silently change the meaning
of legacy axis letters and let callers mistake local coordinates for caller coordinates.

## Decision

Adopt the explicit framed boundary as an opt-in public route:

1. A geometry-established, right-handed `PartFrame(origin, x, y, z)` maps caller-space points to a
   local recognition frame.
2. A successful framed recognition result owns that frame, the exact topology-preserving local
   working `Shape` passed to recognition, and the existing `RecognitionResult`. All evaluated shape
   coordinates, record coordinates, and axis letters are local to the paired frame. Consumers must
   retain the successful result while relying on the working shape's identity relationship to
   topology-bearing evidence.
3. Existing `build_recognition_result(part)` behavior remains unchanged. Framed recognition stays
   a separate opt-in route; making it the aggregate default requires its own compatibility
   decision and release plan.
4. Frame inference is closed. Geometry with no analytic direction returns a typed refusal. A
   single established axis returns an explicit `AXIAL` gauge: its chosen roll is a deterministic
   representative and must not be treated as a semantic material axis. The prototype's remaining
   representative is explicitly a gauge choice, not production material-axis semantics.
5. Recognition still executes once through the existing registry and reconciliation stack. The
   boundary does not expose `GeometryGraph`, correspondence, candidates, or recogniser internals.

The selected implementation uses rigid `TopLoc` placement. It changes evaluated coordinates
without rebuilding topology and exposes the exact placed object so consumers do not create a
second normalization authority.

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

Acceptance is supported by the following evidence:

- directed axes use geometry-established orientation where observable; `ORTHOGONAL` and `AXIAL`
  explicitly publish the remaining gauge instead of claiming a material direction;
- the legacy route and its recess semantics remain unchanged, while the framed route's one known
  Slot fragment is recorded as a bounded opt-in numerical limitation;
- the supported Linux, macOS and Windows matrix exercises the deterministic framed contract;
- the named 500-model MFCAD++ development evaluation is checked in as a machine report; and
- legacy public tests and goldens remain unchanged.

Acceptance does not make framing the default aggregate behavior. That is a separate compatibility
decision and release plan under Epic 0005.

The sealed MFTRCAD holdout is not required for this architecture decision and remains unused.

## Consequences

- Callers can distinguish part placement from recognition semantics without a broad free-axis
  record migration.
- Unconstrained roll is explicit gauge rather than a hidden semantic axis; geometry with no
  analytic direction produces an explicit non-result.
- The legacy public API and coordinate meaning remain compatible. The framed result's required
  working-shape field is a pre-1.0 minor-version compatibility event.
- The topology-preserving placement route is release quality as an explicit opt-in API.
- Making it the default recogniser path remains deferred to a separate compatibility decision.
