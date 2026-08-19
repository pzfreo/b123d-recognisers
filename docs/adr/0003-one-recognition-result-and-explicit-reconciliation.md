# ADR 0003 — One recognition result and explicit reconciliation

- **Status:** Proposed
- **Date:** 2026-08-15
- **Decider:** Paul Fremantle

## Context

Independent recognisers can describe overlapping physical regions: a groove floor may resemble a
turned step, a pocket floor a global level, and a pattern both a group and several member
features. First-match ownership scattered among consumers produces different answers from the same
solid. A plain empty result also cannot distinguish absence, ambiguity, rejection and unsupported
topology.

Draftwright ADR 0017 identified the problem, but mixed recognition decisions with downstream
requirement and annotation identity. This project owns only the geometry-side portion.

## Proposed decision

One call to `recognise(part)` produces one immutable `RecognitionResult` containing:

- reusable geometry inventories;
- proposed candidates and their evidence claims;
- accepted feature records and physical measurables;
- explicit rejected, ambiguous and unsupported outcomes;
- deterministic feature, region and measurable identities.

Candidate discovery and reconciliation are separate stages. A recogniser proposes a plausible
interpretation; a named reconciler accepts, combines or rejects conflicting claims and records the
reason. No universal constraint solver is required: family-specific rules may migrate behind the
one reconciliation protocol incrementally.

**Claims are written during discovery and read only afterwards** (#92). A recogniser records the
faces a candidate was established by, into a run-local append-only claim ledger; nothing consults
those claims while recognisers run. The ledger is deliberately *not* the face graph: the graph
holds geometric fact, a claim is an interpretation of that fact, and separating them keeps the
graph immutable and reusable while each run gets its own ledger. A claim also names a **role** —
`defining` today — because a feature does not relate to every face it touched the same way, and
treating consultation as consumption would manufacture conflicts. This is what makes "every
claimed region is traceable" achievable at all —
without it, whether two records describe one feature can only be answered by comparing coordinates
each family derived by its own procedure, which is how passage/slot reconciliation was first
written and is the defect that prompted this amendment.

Writing claims during discovery does **not** merge the two stages, because the separation this ADR
protects is against *order dependence*: a recogniser that declined a face because another family
had already claimed it would make the census depend on which family ran first. That remains
forbidden. Recording what a recogniser used cannot change what any recogniser returns.

Overlapping claims are evidence, not a verdict. The reconciler applies an explicit compatibility
or precedence rule; two candidates sharing a defining face may both survive, as a pattern and its
members do.

This is close to what the prior art does. Analysis Situs marks feature candidate faces on its
attributed adjacency graph and writes recognition results back as further attributes, so
recognition accretes rather than returning in one shot; see
[`docs/prior-art-feature-recognition.md`](../prior-art-feature-recognition.md). It corroborates
the decision rather than settling it — the local evidence is what settles it, and the sidecar
ledger is a deliberate divergence taken to keep the graph immutable. An earlier reading of this
ADR treated it as forbidding claims outright, which it never did.

Identity is derived from geometry under documented tolerance. It must not use Python identity,
kernel traversal order, display labels, page coordinates or a bare solid enumeration index.

**That rule governs persistent semantic identity — what a record is, and what a consumer may
store, serialise or compare across runs.** It does not govern a *run-local handle*, which exists
only to let two stages of one run refer to the same face, is never serialised, and stops meaning
anything the moment the part changes. `FaceNode` is such a handle: it carries a kernel traversal
position and is compared by Python identity, both of which are forbidden to a record and both of
which are correct here, because identity by construction is exactly what makes a foreign node
impossible to mistake for a local one. The two must not be conflated in either direction — a
handle must never leak into a record, and a record's identity must never be derived from one.

Consumer lifecycle caches are outside the result. A consumer may cache a result, but cannot make
its cache semantics part of this package's aggregate value.

## Required evidence before acceptance

- One aggregate run performs each expensive substrate analysis once.
- Equivalent re-imports produce identical serialized results and identities.
- Conflicting groove/step, pocket/level and pattern/member fixtures have explicit outcomes.
- An ambiguous or unsupported fixture cannot return clean absence.
- Every accepted candidate has one reconciliation outcome and every claimed region is traceable.

## Consequences

Consumers receive one explainable physical feature universe. Migration can be feature-family by
feature-family, but temporary partial results must say which families were not evaluated.

## Amendment (0.2.6, epic 0002)

**A reconciler corrects double-counting. It does not correct recall, and the failure it leaves
behind is quieter than the one it fixes.**

This record gives a reconciler three verbs -- accept, combine, reject -- and its consequences do
not record what happens when the families being reconciled disagree by *omission* rather than by
overlap. Measured per face over 2,000 MFCAD++ models: the rule that drops a chamfer whose face an
angled step claimed leaves 28 chamfer records still landing on faces the corpus labels
*Triangular blind step* -- the exact faces that rule exists to remove. It did not remove them
because `recognise_angled_steps` never claimed them: its blind-end test requires a neighbour of
exactly three edges, and a neighbouring feature subdividing that triangle makes it four or five.

So when family A misses a feature family B also proposes, reconciliation converts **A's false
negative into B's false positive**. The census then reports one record for the face, under the
wrong family, and every count in it looks correct. That is harder to notice than a double count,
and it is the mirror of the failure the shared-predicate arrangement had before a rule replaced
it, where two call sites disagreeing could make a feature vanish claimed by neither.

Two consequences follow, and neither changes the decision above.

- **A rule's ceiling is the recall of the weakest family it reconciles.** Precedence between two
  families is worth having exactly as far as both can see the feature. Evidence offered for a
  reconciliation rule should therefore include what the *losing* family recognises, not only that
  the winner's records survive.
- **There is no fourth verb.** A reconciler cannot say "this face is contested and I am not
  deciding", and nothing in the result can carry that. Whether one is needed is not settled here:
  it is the residual-evidence half of ADR 0004, which remains Proposed, and this is the first
  argument for it that comes from measurement rather than from architecture.
