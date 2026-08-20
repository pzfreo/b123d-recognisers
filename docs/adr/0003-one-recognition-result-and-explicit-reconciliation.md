# ADR 0003 — One recognition result and explicit reconciliation

- **Status:** Accepted
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

## Decision

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

## Required evidence

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
  it is the residual-evidence half of ADR 0004, which is decided in principle and not yet built,
  and this is the first argument for it that comes from measurement rather than from
  architecture.

## Amendment (0.2.6, issue #127)

**There is one inventory. Any other view of a part is a projection of it, never a second
orchestration that is expected to agree.**

This record says one call produces one result, and says nothing about what a *second* entry point
into the same recognition may do. `feature_census` was such an entry point: it called the same
recognisers in its own order, with its own choices about what to inject into each, and reported
counts. Nothing forced the two to stay aligned, and they did not — measured over 73 parts, a real
turned screw was a plate to one and not to the other, because the two had written the same gate
differently. Each difference between them (a memo injected here and not there, countersinks fed
to the hole recogniser on one side only) was a divergence nobody had decided.

Two rules follow.

- **A view counts or filters the one inventory; it does not re-run recognition.** The census is
  now a projection of what `build_recognition_result` returns, so the two cannot answer
  differently about a part. Where a view *deliberately* differs, the difference is a named
  reconciliation rule applied to the shared inventory rather than a different sequence of calls —
  `steps_that_are_not_grooves` is the only such rule today, and it is a compatibility rule under
  the decision above: both records survive, only the count is corrected.
- **The state a run shares is one object, not a set of optional arguments.** The graph, the claim
  ledger, the face-edge memo and the cylinder scan are facts about a run over a part. Threaded
  individually they are also individually forgettable, and a recogniser with no parameter to
  receive one derives its own — silently, correctly, and twice. A public standalone recogniser
  still constructs what it needs; internal orchestration passes one run.

Neither is a new architecture. Both are what "one aggregate run performs each expensive substrate
analysis once", in the evidence list above, has to mean if it is to be checkable rather than
aspirational — and it is now checked by counting derivations rather than by inspection.
