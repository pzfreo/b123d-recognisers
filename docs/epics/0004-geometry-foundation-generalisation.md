# Epic 0004 — Geometry foundation generalisation

**Status:** proposed
**Owner:** @pzfreo
**Opened:** 2026-08-23
**Baseline:** `44e74df` (`0.3.2.dev0`, after epic 0003 and the `0.3.1` release)

## Purpose

Epic 0003 made recognition execution coherent: every physical result now passes through one
candidate, evidence, freeze, disposition and projection lifecycle. The next limitation is not
orchestration. It is the geometry substrate exposed to family predicates and the public shapes
available to describe what they find.

This epic strengthens that substrate before feature-family expansion resumes. It addresses the
foundational gaps identified by the [3D geometry scorecard](../scorecard.md) (review feedback
incorporated here is recorded in [`epic-0004-feedback.md`](../epic-0004-feedback.md)):

1. exact analytic geometry exported as B-splines currently fails closed;
2. the AAG cannot distinguish smooth joins by material side;
3. recognisers can cross smooth subdivisions but cannot inspect a feature through a removable
   blend chain;
4. several mature records and predicates encode world-axis spans rather than a free local frame;
5. accepted records have run-local Candidate identity but no stable correspondence across runs;
6. defining evidence remains absent for some physical families, limiting measured ownership and
   future interaction rules;
7. the neutral substrate is private, so a third party can build on this package's geometry
   reasoning only by forking it.

The work remains deterministic and rule-based. It does not add a learned recogniser, a plugin
system, machining policy, defeaturing mutations, or a new public feature family.

## Outcome

At completion, a recogniser should be able to consume an imported B-Rep through one documented
geometry pipeline:

```text
imported shape
    -> bounded canonical analytic view
    -> immutable attributed face graph
    -> optional immutable blend-collapsed view
    -> family-owned predicate in a local frame
    -> Candidate with defining evidence
    -> existing freeze / disposition / projection lifecycle
    -> optional cross-run correspondence
```

The public aggregate must remain byte-identical for geometry already inside the current supported
domain, except where a separately reviewed schema migration explicitly authorises a richer record.

## Design principles

### Preserve the epic 0003 phase boundary

Canonicalisation and graph-view construction are neutral context derivation. They happen before
physical discovery and cannot issue Candidates. Family discovery remains write-only. Reconciliation
continues to receive only completed CandidateSets and frozen evidence; it cannot inspect a Part,
canonicalise geometry, collapse a graph or invoke discovery.

### Prefer views to destructive rewriting

The imported Part remains the source of truth. Canonical analytic recovery and blend collapse must
retain provenance back to the original faces. A recogniser may reason over an effective face or
collapsed region, but defining evidence must name the original `FaceNode` objects that established
the record. Nothing in this epic edits or defeatures the caller's model.

Shape-level canonical replacement may be used internally when OCCT requires it, but it must produce
an immutable run-owned analysis shape and an explicit original-to-analysis provenance map. It must
not silently replace the public Part or make record coordinates depend on replacement order.

### New geometry facts are total; acceptance stays family-owned

The shared AAG reports analytic candidates, smooth-sided arc kinds, collapsed regions and local
frames as neutral facts. It does not label machining features or discard awkward topology.
Recognisers decide whether those facts are sufficient for their own contract, following ADR 0009.

### Fail closed with a bounded residual

Canonical recovery is accepted only when the fitted primitive stays within a declared local
residual and preserves the topology required by downstream graph construction. Blend collapse is
accepted only when a complete, unambiguous chain satisfies its neutral contract. Unsupported or
ambiguous geometry remains visible as the original graph and produces no expanded recognition.

No corpus-derived numerical threshold may enter these predicates. Length comparisons use ADR 0008
and the smallest controlling local nominal.

### Public schemas change by supersession

An axis-aligned record cannot be made oblique by broadening the meaning of `axis="x"`. Free-axis
support therefore uses a local orthonormal frame and section-based geometry in a new schema or a
new versioned record. Existing record meanings remain stable through their documented compatibility
window. Reconciliation may prefer the richer complete record over a legacy fragment only through a
named identity/evidence rule.

## Work packages and sequence

Each package is a separate PR-sized issue. Later packages may depend on earlier neutral APIs, but
no PR may combine a substrate change with a new feature predicate merely to demonstrate it.

### F0 — Baseline, external evidence and invariants

Freeze the evidence before changing geometry semantics.

Deliverables:

- record the exact current golden, NIST, MFCAD++ and performance results;
- add an external-corpus scanner for MFTRCAD instance and relationship annotations without
  vendoring the complete dataset;
- document MFTRCAD licence, file/annotation identity, taxonomy mapping and known invalid-topology
  handling before any sample enters the repository;
- select deterministic development and sealed holdout manifests by rule, not by observed success;
- inventory and freeze the existing native-analytic/B-spline, blend-chain, oblique-frame,
  traversal, mirror and scale adversaries, adding a fixture only where that inventory finds a gap;
- pin current empty output on unsupported variants so later gains are attributable.

MFTRCAD is evidence, not an oracle. Its feature-instance and relationship labels can identify
interactions and false negatives, but its taxonomy does not define this package's record contracts
or reconciliation policy. Synthetic-corpus measurements remain separate from real-part evidence.

Exit gate: the scanner reproduces a documented baseline without changing source recognition code;
the holdout stays sealed.

### F1 — Bounded canonical analytic recovery

Introduce one neutral service that can recognise a plane, cylinder, cone, sphere or torus represented
as a B-spline and provide an effective analytic surface plus residual and provenance.

Required contract:

- recovery is deterministic for equivalent geometry and configured tolerance;
- every recovered primitive reports type, parameters, maximum residual and original faces;
- native analytic faces pass through unchanged;
- a failed or ambiguous fit returns the original surface with an explicit refusal reason;
- topology, orientation and material-side interpretation remain invariant;
- `RecognitionContext` derives the canonical inventory once per run;
- discoverers consume the injected effective-surface query rather than calling OCCT recovery;
- no family becomes responsible for fitting its own B-spline.

Implementation must first compare two seams: an analysis-shape pre-pass and a provenance-preserving
effective-surface adapter. The chosen seam needs an ADR amendment because surface-type reads are
currently distributed across family modules. A pre-pass is preferred only if it proves stable
face provenance and does not mutate caller geometry.

Torus is a known seam gap: OCCT's `ShapeAnalysis_CanonicalRecognition` documents plane, cylinder,
cone and sphere fits only, so torus recovery — which turned-stock fillet and groove evidence
depends on — needs its own fitting machinery. Torus recovery is therefore a separately gated
increment of F1: the four documented primitives may land and exit first, and a torus slip narrows
scope explicitly rather than failing the whole package.

Exit gate: native-analytic and canonically equivalent B-spline fixtures return identical records
and defining-face attribution; deliberately non-analytic B-splines still fail closed; existing
goldens are byte-identical; runtime and memory remain within a newly recorded canonicalisation
budget.

### F2 — Complete smooth-sided AAG semantics

Replace the single `smooth` arc interpretation with the minimum material-side-aware taxonomy needed
by collapse and family predicates. The intended distinction is smooth-neutral, smooth-concave and
smooth-convex; exact names require design review.

Required contract:

- arc classification is symmetric and traversal-order invariant;
- unknown orientation or failed normal evaluation remains `unknown`, never guessed;
- every existing caller explicitly chooses whether it needs any-smooth or one smooth-sided kind;
- `smooth_region` preserves its current behaviour through a named any-smooth predicate;
- graph construction caches each geometric query once and exposes immutable results;
- split tangent faces, reversed edges, seams, closed surfaces and degenerate normals have
  adversarial tests.

This package changes neutral facts only. No recogniser may tighten or relax acceptance in the same
PR. Any observed output delta is a blocker until explained as an existing classification defect and
approved separately.

Exit gate: all public recognition output is unchanged; the richer arc matrix is independently
verified on synthetic and imported STEP topology.

### F3 — Immutable blend-collapsed graph views

Add a derived graph view that lets a family analyse logical neighbours as though an eligible blend
chain were absent while retaining all original nodes and evidence provenance.

Required contract:

- the base `FaceGraph` remains immutable and complete;
- collapse consumes only neutral arc/surface/boundary facts and emits no feature label;
- eligible chains require complete smooth-sided support, unambiguous spring/cross boundaries and
  one-solid ownership;
- branching, mixed-radius, partial, vertex-only, ambiguous-side and cross-solid chains refuse;
- a logical arc maps to the exact original arcs and faces it represents;
- push/pop mutation, hidden global state and destructive face removal are forbidden;
- families opt into the view explicitly; no global automatic collapse changes all predicates;
- defining evidence always expands to original nodes before Candidate issuance.

The first production consumer should be an existing family with a known blend-obscured fixture,
but consumer enablement is a separate PR after two independent accepts of the neutral view.

Exit gate: collapse construction is order-, mirror- and split-invariant; refusing a chain gives the
same base graph; non-consuming families and all existing goldens remain unchanged.

### F4 — Free-axis local frames and section records

Provide one shared immutable local-frame representation for geometry that is not aligned with world
X/Y/Z, then migrate the recess contracts that cannot truthfully express oblique geometry.

Minimum internal values:

```python
@dataclass(frozen=True)
class LocalFrame:
    origin: tuple[float, float, float]
    run: tuple[float, float, float]
    u: tuple[float, float, float]
    v: tuple[float, float, float]

@dataclass(frozen=True)
class PlanarSection:
    frame: LocalFrame
    boundary: tuple[tuple[float, float], ...]
```

Exact public names are deferred, but the invariants are not:

- `run`, `u` and `v` form a canonical right-handed orthonormal frame;
- sign and basis tie-breaks are deterministic under equivalent topology;
- sections have canonical winding and start vertex;
- record identity includes body, frame, run interval and section geometry;
- principal-axis inputs continue to project byte-identical legacy records during migration;
- oblique geometry is represented by a section record, never squeezed into `axis: str` spans;
- reconciliation names when a complete section record supersedes an axis-span fragment;
- schema/version/capability changes follow ADR 0005 and downstream golden migration.

This package is explicitly split into two halves with different risk and different clocks:

- **F4a — the schema**: the versioned frame/section records, canonical tie-breaks, and
  dual-read/dual-project parity for principal-axis inputs. Additive, requires no recogniser
  changes, and is the only work in this epic with a deadline pressure — every release shipped
  meanwhile pins the axis-span schemas deeper into the ADR 0005 compatibility window. F4a lands
  early (see the recommended order) so the 1.0 corner is escaped even if later packages slip,
  and so F1 fixtures, F5 evidence and the section-supersedes-fragment rule are written once
  against the final schema.
- **F4b — the oblique predicates**: the hard geometry work in the `_recess_*` subsystem,
  delivered family-by-family whenever ready, with no shared cliff.

Sequence within the halves: neutral frame primitives; versioned record proposal;
dual-read/dual-project migration (F4a); then family-private oblique predicates; only then
deprecation (F4b). Do not rewrite the whole `_recess_*` subsystem in one PR.

Exit gate: all rotations, mirrors and traversal permutations give canonical frames; principal-axis
goldens remain stable; a separately authorised oblique corpus set gains records with zero off-target
defining claims; Draftwright explicitly reviews the schema transition before production pin movement.

### F5 — Complete defining-evidence migration

Move every physical registry definition from deliberate empty evidence to truthful defining
evidence where the record has a geometric ownership proof.

Required contract:

- registry metadata states whether a family is `attributed` or deliberately `unattributed` with a
  non-empty reason;
- a returned attributed record occurrence has non-empty defining evidence;
- evidence names only original graph nodes that establish the record, not stock/context faces;
- direct recognition remains unchanged with or without the writer;
- equal-valued occurrences stay identity-distinct;
- empty evidence never proves containment, precedence or compatibility;
- corpus reports distinguish measured ownership precision from fitted record counts.

Families migrate independently. A family does not gain a reconciliation rule merely because it now
has claims; a rule requires an observed overlap, a named geometry relation and separate review.

Exit gate: every physical definition has an explicit attribution disposition; capability evidence
truthfully distinguishes attributed and unattributed families; per-face tools consume the same
frozen inventory and no parallel claim path remains.

### F6 — Persistent cross-run feature correspondence

Add an optional sidecar that matches accepted records between recognition runs without changing
record equality or Candidate identity.

Required contract:

- correspondence consumes two completed immutable inventory products; it is not discovery or
  reconciliation;
- exact stable fingerprints use record type, body signature, canonical frame/location and defining
  geometry summaries;
- matching distinguishes unchanged, moved, resized, split, merged, added and removed occurrences;
- ambiguity is explicit and never resolved by traversal index or nearest-neighbour guess alone;
- run-local Candidate IDs and kernel face indices never become public persistent IDs;
- public records remain plain values; persistence metadata is a separate versioned projection;
- equivalent unchanged geometry produces stable correspondence across STEP round-trips and platform
  traversal differences.

This package begins as a private diagnostic consumed by tests and tooling. A public identity schema
requires its own ADR and downstream consumer before publication.

Exit gate: edit-sequence fixtures pin identity through harmless re-export, translation and dimension
changes, while split/merge ambiguity fails closed; recognition results remain unchanged.

### F7 — Published substrate API

Promote the neutral geometry substrate to a public, versioned framework contract so that
third-party recognisers can build alongside this package without forking it. Adjudication
remains closed: an external recogniser consumes the substrate and returns its own records; it
does not enter `build_recognition_result`, reconciliation, the census, or the capability
manifest.

Required contract:

- the published surface covers, at minimum: graph construction and queries (`FaceGraph`, the F2
  smooth-sided arc kinds, `smooth_region`), the F1 effective-surface query with residual and
  provenance, the F3 collapsed-view queries, and the F4a frame/section primitives;
- the registry, disposition table, `FamilyId`, evidence sink/index and reconciliation remain
  private; no dynamic registration, filesystem discovery or plugin import path is introduced;
- the substrate API is versioned and manifest-declared under ADR 0005 discipline, with a
  documented compatibility window, and its exports are enumerated by a completeness test the
  same way recogniser exports are;
- determinism guarantees are stated per query (same part, same facts, any platform) and pinned
  by golden evidence, so external consumers inherit the contract internal families rely on;
- a documented graduation path states what an out-of-tree family must present to enter the
  closed registry: fixtures, semantic goldens, capability row, corpus evidence — the same bar
  `adding-a-recogniser.md` sets internally.

Sequencing: strictly after F1–F4a settle the APIs being published; freezing the substrate
mid-epic would tax every subsequent package, while publishing at epic exit costs almost
nothing. This package converts the governance ceiling — one maintainer's evidence throughput —
into an ecosystem: external families become a nursery, proving themselves out-of-tree and
graduating with evidence in hand.

Exit gate: a demonstration out-of-tree recogniser (separate package, not vendored) builds a
working family against only the published API and documented contracts; the substrate API is
covered by the capability manifest and a versioned compatibility test; no internal adjudication
symbol is reachable from the public surface.

## Review and delivery process

Every child follows the evidence gate used for recent recogniser work:

1. State the exact neutral or family contract and adversaries before implementation.
2. Freeze development evidence and, when recognition semantics may change, a disjoint sealed
   holdout selected without inspecting outcomes.
3. Implement the smallest coherent slice with no unrelated family expansion.
4. Pass focused tests, the full suite, Ruff, mypy, diff-check, manifest regeneration, package-wheel
   contract and the composite performance/memory budget.
5. Obtain two independent reviews: one geometry/correctness review and one architecture/ADR review.
6. Resolve every blocking counterexample and re-review the exact final head.
7. Reveal a sealed holdout only after both accepts when a new predicate or recovery decision can
   change recognition. A neutral refactor proves unchanged existing holdouts and does not invent a
   reveal ceremony.
8. Record exact commit, commands, counts and benchmark convention in the child issue/PR.
9. Merge children in dependency order; do not stack an unreviewed semantic consumer on a neutral
   substrate PR.

MFTRCAD development and holdout partitions must be disjoint by published dataset identity or a
deterministic manifest rule. Once revealed, a holdout becomes regression evidence; further fitting
requires a fresh draw.

## Architecture guards

The epic is not complete until tests make these properties executable:

- canonical recovery and graph views live below family policy and cannot import recognisers,
  reconciliation, registry execution or projection;
- discovery cores receive neutral context plus `EvidenceSink`, never an evidence reader;
- reconciliation receives no Part, canonicaliser, graph builder, collapsed-view builder or
  discoverer;
- collapsed/effective nodes always expand to same-run original `FaceNode` evidence;
- physical Candidate inventory and exactly-one-disposition coverage remain complete;
- registry definitions declare canonical, collapsed-view and local-frame dependencies explicitly;
- projection remains typed and manual; registry metadata cannot silently publish a schema;
- public result fields, capability records, census bindings and downstream goldens have independent
  completeness checks;
- no filesystem discovery, dynamic recogniser import, learned classifier or implicit plugin path is
  introduced;
- tolerance and canonical residual policies have named tests and no corpus-fitted constants.

## Global acceptance criteria

- [ ] Native analytic geometry returns byte-identical records and evidence to the baseline.
- [ ] Supported B-spline encodings return the same records as their native analytic equivalents.
- [ ] Unsupported/non-analytic B-splines fail closed with bounded private diagnostics.
- [ ] The AAG exposes reviewed smooth-sided semantics without changing family output by itself.
- [ ] Blend-collapsed views are immutable, provenance-complete and opt-in.
- [ ] At least one existing blend-obscured case is recovered in a separately reviewed consumer PR.
- [ ] Free-axis frames and sections are deterministic under rotation, mirror, traversal and STEP
      round-trip.
- [ ] No oblique feature is represented by misusing an axis-aligned public record.
- [ ] Every physical family declares truthful defining-evidence support or an explicit exclusion.
- [ ] Cross-run correspondence is a sidecar and does not alter records or Candidate identity.
- [ ] MFCAD++, MFTRCAD and real-part evidence is reported separately with provenance and limitations.
- [ ] Public API, capability schema, census and Draftwright contracts follow ADR 0005 transitions.
- [ ] The neutral substrate is published as a versioned public API with closed adjudication, a
      completeness test, and a demonstrated out-of-tree consumer.
- [ ] Full quality, package, cross-platform and performance gates pass at every semantic landing.
- [ ] All child issues close with exact-head logic and architecture accepts.

## Explicit non-goals

- adding through steps, threads, sheet-metal features, ribs or another recogniser family;
- training or embedding MFTReNet/BRepFormer or any learned model;
- treating a corpus label as geometric truth at an interaction;
- mutating or defeaturing the caller's Part;
- general free-form surface recognition beyond bounded recovery of analytic primitives;
- assembly mates, machining operations, tool selection, tolerances or drawing policy;
- public plugin discovery or third-party registry mutation;
- publishing residual diagnostics or persistent IDs before a real consumer and separate ADR.

## Principal risks

| Risk | Containment |
| --- | --- |
| Canonicalisation changes topology or face identity | analysis-only shape, explicit provenance, analytic-equivalence fixtures, fail closed |
| Torus recovery exceeds the documented OCCT canonical seam | torus is a separately gated F1 increment; the four documented primitives exit independently |
| Publishing the substrate freezes APIs still in motion | F7 runs strictly last; no public substrate export before F1–F4a settle |
| Richer arc kinds silently alter existing predicates | neutral-only F2 PR; explicit any-smooth compatibility helper |
| Collapse becomes hidden defeaturing policy | immutable opt-in view; no global automatic consumer |
| Oblique migration creates two competing truths | versioned section record, named precedence, ADR 0005 migration |
| Candidate search space harms performance | cheap applicability gates, derive-once context, per-package budget |
| Synthetic datasets encourage taxonomy fitting | geometry contracts first, real-part controls, sealed draws |
| Persistent matching invents certainty | explicit ambiguity, no traversal/face-index identity |
| Epic becomes another feature-expansion programme | non-goals enforced; each PR changes substrate or one existing consumer only |

## Recommended issue order

1. F0 baseline and MFTRCAD ingestion/audit.
2. F4a versioned frame/section schema with byte-identical principal-axis projection — first
   because it is the only package whose cost grows with every release that pins the axis-span
   schemas deeper, and because later fixtures and evidence should be written against the final
   schema once rather than twice.
3. F1 canonical analytic recovery design and neutral implementation (torus as a separately
   gated increment).
4. F2 smooth-sided AAG taxonomy.
5. F3 immutable collapsed views.
6. F5 defining-evidence migration, parallelised by independent family only after the neutral APIs
   settle.
7. F4b family-by-family oblique predicates, and the axis-span deprecation window.
8. F6 persistent correspondence after canonical frames and attribution are stable.
9. F7 published substrate API, strictly last: it freezes the neutral APIs the earlier packages
   are still shaping.

The first implementation goal should stop after F0 and the design review for F1. Canonicalisation
has the largest leverage, but it also sits beneath every recogniser; evidence and a reviewed seam
must precede code.
