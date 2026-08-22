# Minimum recogniser framework API

**Status:** Proposal for review  
**Scope:** Internal architecture; no immediate public API commitment  
**Related:** ADR 0002, ADR 0003, ADR 0004, ADR 0007, ADR 0009

## Purpose

The project now has one orchestration, a shared `FaceGraph`, an append-only `ClaimLedger`, and
several explicit reconciliation rules. Newer recognisers fit that architecture well, but they do
so through slightly different call signatures and result-handling conventions. Older families
still depend on local topology scans or implicit filtering.

This proposal defines the **minimum common API** by which every recogniser participates in one
clean lifecycle:

1. receive immutable run facts;
2. discover candidates independently;
3. attach evidence without reading sibling claims;
4. reconcile candidates centrally;
5. project accepted records and diagnostics into `RecognitionResult`.

It does not define a universal feature algorithm, graph pattern language, constraint solver, or
base record class. Family-specific geometry remains family-owned.

## How this fits the current code

This is an evolution of the existing architecture, not a replacement. Most of the necessary
parts already exist; the proposal gives them consistent boundaries and makes currently informal
rules enforceable through types and architecture tests.

| Proposed concept | Current implementation | Migration required |
| --- | --- | --- |
| `RecognitionContext` | `RecognitionRun` owns `FaceGraph`, `FaceEdges`, `ClaimLedger` and the cylinder inventory | Separate immutable facts from the append-only evidence sink; gradually replace multiple optional injection parameters |
| `Candidate` | A public record object acts as both proposal and claimant | Wrap each proposal in a run-local identity-safe object while leaving public record equality unchanged |
| `Evidence` | `Claim` and `ClaimLedger.defining` | Preserve defining claims; add consulted and derived roles only when consumers exist |
| `CandidateSet` | Each recogniser returns a deterministically sorted `list[Record]` | Wrap the completed list with an explicit family identifier |
| `Disposition` | `RecessDisposition` records accepted/rejected recess outcomes | Generalize the protocol to other conflict families, then add ambiguous/unsupported outcomes |
| `ReconciliationResult` | `ReconciledRecesses` plus separate filtering helpers | Keep named family rules but return one complete identity-safe trace shape |
| Registry | `MIGRATED`, imports, result fields, capability metadata and test rosters are maintained separately | Add one explicit internal family roster that drives orchestration and completeness checks |
| Projection | `build_recognition_result`, census, snapshots and attribution contain projection work | Make discovery, reconciliation and projection explicit functions; views consume the accepted result and, where needed, its reconciliation trace |

### The existing prototype

Recess reconciliation is already the closest implementation of this framework. `Slot`, `Pocket`,
`PrismaticPocket`, `Passage` and `SemicircularBottomBlindSlot` discovery completes before policy
runs. Their claims are resolved by candidate identity, and `reconcile_recesses` returns accepted
inventories plus exactly one accepted/rejected `RecessDisposition` per proposal. The migration
should generalize this proven seam rather than introduce a parallel framework.

The fillet/circular-step and chamfer/angled-step paths are one step behind. Their discovery is
independent and evidence-based, but their reconciliation helpers return filtered record lists
rather than a complete disposition trace. They are the next bounded migrations after recesses.

Most other recognisers need no geometric algorithm change. Their current aggregate call shape:

```python
records = recognise_family(
    part,
    graph=run.graph,
    face_edges=run.face_edges,
    ledger=run.ledger,
)
```

would become an internal framework call:

```python
candidates = FAMILY.discover(context, evidence_sink)
```

The public `recognise_family(part)` facade would still return that family's direct records. An
existing caller would not need to construct a context, handle candidates, read claims, or invoke
cross-family reconciliation.

### What materially changes

1. Public records stop doubling as internal candidate identity.
2. Discovery receives a write-only evidence interface, making claim-read order dependence
   structurally impossible.
3. Every proposal receives an explicit outcome instead of disappearing inside a filtered list.
4. The current orchestration is separated into discovery, reconciliation and projection phases.
5. One registry becomes the authoritative internal family roster and integration checklist.

The project therefore does not need a new AAG or wholesale recogniser rewrite. The main unfinished
work is applying the disposition and diagnostic lifecycle consistently across all families and
making the already-intended phase boundaries mechanically enforceable.

## Design principles

- **One run, one substrate.** Face edges, AAG facts, analytic-surface inventories, tolerances and
  the claim ledger are derived once.
- **Discovery is independent.** A recogniser cannot call a sibling recogniser, inspect accepted
  results, or read claims to decide whether to propose a candidate.
- **Evidence and records are separate.** A public record describes measurable geometry. Evidence
  explains why that particular candidate was proposed.
- **Candidate identity is run-local.** Equal-valued records proposed from different geometry must
  remain distinguishable during reconciliation.
- **Every proposal gets a disposition.** Acceptance, rejection, ambiguity and unsupported evidence
  must not be represented by silently dropping a record.
- **Public standalone functions remain simple.** A caller may continue to call
  `recognise_slots(part)` without constructing framework objects.
- **The framework standardizes lifecycle, not recognition semantics.** A ring, an opposed-wall
  recess, an analytic open profile and an angled step should not be forced into one geometric
  abstraction.

## The minimum core types

The names below are illustrative. Exact spelling can change during implementation, but the roles
should not be combined.

### 1. `RecognitionContext`: immutable shared facts

```python
@dataclass(frozen=True, slots=True)
class RecognitionContext:
    part: Part
    face_edges: FaceEdges
    graph: FaceGraph
    cylinders: FrozenCylinderInventory
    tolerances: RecognitionTolerances
```

This is the read-only input to discovery. It replaces the growing combination of optional
`face_edges=`, `graph=` and `cyls=` parameters inside aggregate orchestration.

The context contains facts, not interpretations. It must not contain accepted features, sibling
candidates, claims or downstream policy. Additional expensive neutral substrates may be added
only when at least one orchestration owns their lifetime and reuse is measured.

`RecognitionRun` can evolve into this object or own it. The important distinction is that the
append-only evidence sink below is not presented as immutable fact.

### 2. `Candidate`: identity-safe proposal plus evidence

```python
RecordT = TypeVar("RecordT")

@dataclass(frozen=True, eq=False, slots=True)
class Candidate(Generic[RecordT]):
    family: FamilyId
    record: RecordT
    evidence: Evidence
```

`eq=False` is deliberate. Two records may compare equal while coming from distinct bodies or
distinct source regions. Reconciliation operates on candidate identity; public record equality
continues to describe value equality.

A candidate is private and run-local. It is never serialized as the stable identity of a public
feature. A `FamilyId` is a closed identifier owned by the registry, not a module name inferred at
runtime. The type variable is invariant: the generated dataclass initializer consumes a record,
so covariance is not type-safe. Heterogeneous disposition boundaries use `Candidate[Any]`.

### 3. `Evidence`: explicit roles over graph nodes

```python
@dataclass(frozen=True, slots=True)
class Evidence:
    defining: frozenset[FaceNode] = frozenset()
    consulted: frozenset[FaceNode] = frozenset()
    derived: tuple[EvidenceFact, ...] = ()
```

The initial implementation only needs `defining`; `consulted` and `derived` can be introduced
without changing the candidate lifecycle. Their meanings are:

- `defining`: source regions represented by the record and eligible for ownership comparison;
- `consulted`: stock, terminal or neighbouring context used to prove the candidate but not owned
  by it;
- `derived`: serializable neutral facts such as `empty_sweep`, `complete_concave_seam`, or
  `unsupported_boundary`, with no live OCP objects.

An empty defining set is permitted as an explicit evidence state, not as a claim. Reconciliation
must never treat it as containment. This preserves current end-cap-derived candidates while
making the absence visible.

Candidates are created through the evidence sink rather than directly:

```python
candidate = sink.propose(family, record, Evidence(defining=nodes))
```

This makes graph-provenance validation atomic: an unvalidated candidate cannot circulate while
the ledger separately tries to associate it with evidence. The existing `ClaimLedger` can remain
the indexed storage implementation during migration, but it becomes the index over candidate
evidence rather than a second owner of that evidence.

Only `defining` lands in the first migration. `consulted` and `derived` are reserved until #161
provides a real consumer; reserving their meaning in the type design must not create unused data.

### 4. `CandidateSet`: one family’s complete discovery output

```python
@dataclass(frozen=True, slots=True)
class CandidateSet(Generic[RecordT]):
    family: FamilyId
    candidates: tuple[Candidate[RecordT], ...]
```

This small wrapper establishes two invariants:

- discovery for the family is complete before reconciliation begins;
- deterministic candidate ordering is the family’s responsibility and can be tested uniformly.

It is not a mutable builder and does not expose sibling results.

### 5. `Disposition`: exactly one decision per candidate

```python
class Outcome(Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"

@dataclass(frozen=True, eq=False, slots=True)
class Disposition:
    candidate: Candidate[object]
    outcome: Outcome
    reason: ReasonCode
    related: tuple[Candidate[object], ...] = ()
```

`ReasonCode` is a closed, namespaced code such as
`recess.slot_fragment_superseded_by_passage`, not an arbitrary string. `related` identifies the
candidate or candidates that caused a decision and remains run-local.

Every candidate must receive exactly one disposition. Reconcilers may also create an accepted
combined candidate, but must disposition every input and state which inputs produced the new one.
The first implementation may keep `AMBIGUOUS` and `UNSUPPORTED` internal until their stable public
diagnostic projection is designed.

### 6. `ReconciliationResult`: accepted candidates plus complete trace

```python
@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    accepted: tuple[Candidate[object], ...]
    dispositions: tuple[Disposition, ...]
```

This generalizes the existing `ReconciledRecesses` protocol. It does not imply one global solver.
Several named reconcilers may contribute to one result. They run in explicit source order, like
the family registry, and the coordinator rejects a second disposition for the same candidate.
Rules that depend on one another stay inside one named reconciler: the cascading Pocket, Slot,
Passage and PrismaticPocket rules remain one recess policy rather than becoming order-dependent
cross-reconciler communication.

## The minimum callable APIs

### Discovery

```python
class Discoverer(Protocol[RecordT]):
    family: FamilyId

    def discover(
        self,
        context: RecognitionContext,
        evidence: EvidenceSink,
    ) -> CandidateSet[RecordT]: ...
```

Rules:

- may read only `RecognitionContext` and family-private pure helpers;
- may append its own evidence;
- may not read the evidence sink;
- may not import or call sibling `discover`/`recognise_*` functions;
- must return deterministic ordering;
- must use unrounded geometry for decisions and round only public record projection;
- must fail closed when the record cannot truthfully express the observed geometry.

`EvidenceSink` is intentionally narrower than `ClaimLedger`: it exposes append operations but no
lookup operations. Reconciliation receives a separate read-only `EvidenceIndex`. This makes the
write-only discovery rule structural rather than conventional.

### Reconciliation

```python
class Reconciler(Protocol):
    name: ReconcilerId

    def reconcile(
        self,
        candidates: CandidateIndex,
        evidence: EvidenceIndex,
    ) -> tuple[Disposition, ...]: ...
```

Rules:

- receives only completed candidate sets and evidence;
- cannot inspect the part, call a recogniser, or create missing geometric evidence;
- applies one named compatibility, precedence or combination policy;
- compares candidates by identity and geometry-derived evidence, never list position;
- cannot use an empty defining set as subset evidence;
- returns deterministic, closed reason codes.

A family with no conflicts needs no custom reconciler. The coordinator gives each unchallenged
candidate a default `accepted/no_conflict` disposition.

### Reconciliation lookups

`CandidateIndex` is the frozen, minimal lookup surface over completed discovery:

```python
class CandidateIndex(Protocol):
    def by_family(self, family: FamilyId) -> tuple[Candidate[Any], ...]: ...

class EvidenceIndex(Protocol):
    def defining_of(self, candidate: Candidate[Any]) -> frozenset[FaceNode]: ...
    def claims_of(self, node: FaceNode) -> tuple[Candidate[Any], ...]: ...
```

Reconcilers do not scan heterogeneous lists with local `isinstance` conventions and do not gain
access to mutable discovery state. More lookup methods are added only when a second real rule
needs them.

### Projection

```python
def project_result(
    context: RecognitionContext,
    reconciliation: ReconciliationResult,
) -> RecognitionResult: ...
```

Projection is the only stage that builds the public aggregate. It:

- groups accepted candidate records into typed `RecognitionResult` fields;
- derives pattern/member views from accepted members;
- creates stable serialized diagnostics from internal dispositions when supported;
- never reruns discovery or applies a second hidden reconciliation policy.

Patterns remain a projection rather than candidates: pattern/member face sharing is legitimate
and there is no conflict consumer requiring candidate identity today.

Snapshots are pure projections of the accepted result. Per-face attribution consumes the result's
accepted candidates and evidence index. Census currently also reads evidence for the
step-versus-groove compatibility correction; under this framework that compatibility rule becomes
a reconciler which accepts both records with a `related` link, allowing census to count physical
features from the reconciliation trace rather than rerunning policy. The result and its trace are
therefore the one inventory product; the public `RecognitionResult` alone need not expose internal
dispositions.

## Registration and orchestration

A small explicit registry replaces the manually synchronized family roster without relying on
module discovery:

```python
@dataclass(frozen=True, slots=True)
class RecogniserDefinition(Generic[RecordT]):
    family: FamilyId
    record_type: type[RecordT]
    result_field: str
    discoverer: Discoverer[RecordT]
    applicability: Applicability = always
```

The registry is ordered in source control. It drives orchestration, contract tests and capability
completeness checks. It does **not** automatically define public exports or serialized schema;
those remain reviewed compatibility surfaces.

The aggregate lifecycle becomes:

```python
context = make_context(part, supplied_cylinders)
sink = make_evidence_sink(context.graph)

candidate_sets = tuple(
    definition.discoverer.discover(context, sink)
    for definition in REGISTRY
    if definition.applicability(context)
)

trace = reconcile_all(CandidateIndex(candidate_sets), sink.freeze())
result = project_result(context, trace)
```

Applicability gates decide whether a family is meaningful for this part classification. They may
read neutral context only and must not duplicate feature recognition.

## Standalone public recognisers

Existing public functions remain compatibility facades:

```python
def recognise_slots(part: Part, ...) -> list[Slot]:
    context, sink = standalone_context(part, ...)
    proposed = SLOT_DEFINITION.discoverer.discover(context, sink)
    return [candidate.record for candidate in proposed.candidates]
```

Standalone functions return that family’s direct proposals, preserving current behaviour where
aggregate reconciliation deliberately differs. They do not invoke cross-family reconciliation.
Optional legacy injection parameters can be deprecated gradually once internal orchestration uses
the context API throughout.

## What remains family-owned

The framework must not absorb:

- what topology constitutes a slot, passage, step, fillet or analytic profile;
- which AAG/gAAG query a family opts into;
- boundary sewing and geometric completeness policy specific to one record;
- dimensional measurements and record construction;
- family-specific adversarial fixtures;
- compatibility policy between particular feature meanings.

Neutral facts such as coplanar regions, same-cylinder regions, material-side arc classes and exact
solid occupancy may live below families. A helper moves there only when its contract is factual
and at least two real consumers agree on that contract. “Looks reusable” is not sufficient.

## Required architecture guards

The framework should be enforced mechanically:

- family modules cannot import sibling family modules;
- discoverers cannot call or alias sibling `recognise_*`/`discover` functions;
- discovery receives a write-only evidence interface;
- reconcilers cannot import family discoverers, inspect `Part`, or call graph-building code;
- only orchestration imports the full registry;
- projection cannot invoke discovery;
- every registered public record participates in frozen/serialization, manifest, result-field and
  census contract tests;
- every candidate in a test run receives exactly one disposition;
- equal-valued, distinct candidate objects remain distinct through evidence and dispositions.

## Minimum migration sequence

This should be consolidation work, not another feature expansion.

1. Introduce `Candidate`, `Evidence`, `CandidateSet` and the narrow evidence sink/index interfaces
   behind existing behaviour.
2. Adapt `reconcile_recesses` to the generic disposition types without changing its rules.
3. Split current orchestration into explicit discovery, reconciliation and projection functions.
4. Move the existing fillet/circular-step and chamfer/angled-step rules behind the same protocol.
5. Add default accepted dispositions for families with no conflicts.
6. Migrate recogniser call signatures one family at a time to `RecognitionContext`; retain public
   standalone facades.
7. Add internal ambiguous/unsupported outcomes and one residual diagnostic fixture.
8. Decide the stable public diagnostic schema only after several families exercise it.

At no point should this migration change the supported geometry of a recogniser merely to make it
fit the framework.

## Review questions

1. Is `Candidate(record, evidence)` the correct identity boundary, or should evidence remain only
   in an indexed ledger keyed by candidate identity?
2. Should `consulted` evidence land in the first migration, or be reserved while only `defining`
   has active consumers?
3. What concrete conflict would justify promoting patterns from projection to candidates? Until
   one exists, they remain projection-only.
4. What concrete consumer would justify exposing dispositions? Until #161 exercises them, all
   fields remain private and the reason taxonomy is not a compatibility contract.
5. What measured performance problem would justify per-family substrate declarations? Until one
   exists, the context owns its bounded substrate uniformly and the registry carries no speculative
   substrate configuration.

## Acceptance criteria

The proposal is implemented only when:

- all current aggregate outputs and public standalone outputs remain stable unless separately
  approved;
- every discovered candidate has identity-safe evidence and exactly one disposition;
- no discoverer can read sibling claims through its provided interface;
- every substrate owned by `RecognitionContext` is derived at most once per aggregate run;
- census, snapshots and attribution consume the one accepted inventory product (result, trace and
  evidence index) without rerunning discovery or hidden policy;
- at least recess, chamfer/angled-step and fillet/circular-step conflicts use the common protocol;
- architecture and contract tests make adding a nonconforming recogniser fail visibly;
- performance remains within the recorded composite budget.
