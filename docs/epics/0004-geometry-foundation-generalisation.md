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

Introduce a private, lazy, run-owned `EffectiveSurfaceIndex` keyed only by the original
`FaceGraph`'s issuer-owned `FaceNode` values. F1 rejects an analysis-shape pre-pass: a second
topology universe would require a face bijection before Candidate evidence could remain truthful.
The index reads `graph.face(node)`, caches one immutable result per node, never substitutes the
caller Part or graph, and retains that exact original node as the only evidence provenance.

The closed result is native analytic, uniquely recovered analytic, or refused original. Native and
recovered plane, cylinder, cone and sphere facts contain canonical finite numeric parameters,
original node, a closed orientation capability (`NATIVE_ORIENTED` or `RECOVERED_UNORIENTED`),
requested tolerance, kernel-reported deviation and the separate
verified acceptance bound. Refusals retain the original surface behind a private query and use a
closed reason: unsupported kind, unavailable fit, invalid/nonfinite result, bound exceeded,
or ambiguous primitive. An oriented-view request against `RECOVERED_UNORIENTED` separately refuses
as `ORIENTATION_UNPROVEN`; this is not a geometry-recovery failure. Native analytic faces use a
zero-recovery fast path. Only B-spline/Bezier faces enter recovery; torus recovery remains an
explicit unsupported refusal until a separately reviewed fitter, residual proof and performance
gate exist.

`ShapeAnalysis_CanonicalRecognition.GetGap()` is recorded only as `kernel_reported_gap`; F1 does
not independently rename that scalar a maximum. The acceptance certificate is the documented OCCT
`ShapeAnalysis_CanonicalRecognition` face operation itself: OCCT's official shape-healing contract
defines recognition by the maximum-distance criterion over the input face. Each primitive attempt
uses a fresh/reset recogniser, requires success and status zero, records `GetGap()`, and requires it
not exceed the requested tolerance. The supported OCCT version and source/documentation contract
are pinned by test and ADR. A finite UV sample is only an adversary, never the certificate. If that
upstream maximum-distance contract changes or cannot be established for the installed version,
recovery refuses globally rather than substituting a sampled bound.

All four eligible primitive fits are evaluated independently. Canonical parameters use deterministic
run/sign, closest-axis-point and frame conventions. Multiple materially non-equivalent passing
facts produce `AMBIGUOUS_PRIMITIVE`; call order is never precedence. Degenerate trims, huge-radius
near-planes, cylinder/cone ambiguity, sphere poles/seams and split faces fail closed unless the
same uniqueness and bound are proven.

Topology, boundaries, adjacency, `TopAbs_Orientation`, material-side probes and Candidate evidence
always use the original face/solid/graph. F1 deliberately recovers **unoriented primitive
geometry**: canonical axis/frame signs are serialization conventions, not material-side facts.
Recovered geometry may not answer normals, concavity, outwardness or any orientation-dependent
family rule. Those readers remain classified raw/deferred until F2 supplies its separately reviewed
material-side semantics; a request for oriented recovered geometry returns
`ORIENTATION_UNPROVEN`. This removes the unsafe one-anchor/global-parity claim while preserving
current original-face behaviour. Effective facts cannot replace topology or decide a family
predicate.

Recovery tolerance is an ADR 0008 same-geometry policy fixed before corpus measurement:
`fit_tol = relative * local_nominal + coordinate_floor`. For trimmed-face area `A > 0` and physical
trim-boundary length `P >= 0`, the rotation/translation-invariant nominal is
`min(sqrt(A), 2*A/P)` when `P > 0`, otherwise `sqrt(A)`. Area and boundary length are measured on
the original face in model units. `P` counts each physical boundary component once and excludes
periodic seam pairs and degenerate representation edges; a topologically closed face therefore has
`P == 0` regardless of seam parameterisation. Nonfinite/nonpositive area or a nonfinite/negative
perimeter refuses. This makes long-thin patches width-controlled without using a world AABB, while
closed sphere-like faces use their area scale. Same geometry with different STEP seam
parameterisation must produce the same nominal. The exact relative coefficient and coordinate floor are
named and justified in ADR 0008 before corpus inspection. Requested tolerance, kernel-reported gap
and the OCCT maximum-distance certificate remain distinct full-precision values.

F1 is staged rather than migrating every distributed surface read in one PR:

1. land the neutral four-primitive index, refusals, caching, provenance and architecture guards
   with zero recognition-output change;
2. freeze a machine-checked roster of every `BRepAdaptor_Surface.GetType`, `Face.geom_type`,
   `graph.is_planar` and equivalent decision, classifying each as migrated, deliberately raw
   topology, orientation-deferred, or torus-deferred. Every non-migrated entry requires a named
   rationale; raw surface classification may not remain a family-acceptance escape hatch;
3. migrate consumers in explicitly ordered family slices. Private cores receive a restricted
   read-only surface query; public wrappers construct one graph/index for standalone use and
   registry adapters inject `RecognitionContext.surfaces`. Families cannot construct or invoke
   the fitter. Cylinder analysis and every public/aggregate caller must share one surface universe.

The neutral slice changes no public signature, capability manifest, record, Candidate, disposition
or reconciliation policy. ADR 0004 owns original-node provenance and the immutable view; ADR 0007
owns the module/core-wrapper and reader-roster seams; ADR 0008 owns the residual policy; ADR 0002
is amended when standalone/aggregate injection first changes. ADR 0005 applies only if a later
slice changes a public signature or capability contract.

Exit gate: native and supported equivalent encodings return byte-identical records, ordering and
defining `FaceNode` identities for every migrated consumer; unsupported, ambiguous and unbounded
B-splines refuse; direct and aggregate entry points agree; one recovery occurs per original node
per run; semantic goldens remain byte-identical. Measure native-only index overhead separately from
B-spline recovery runtime/peak RSS without rebasing existing ceilings. The two-review and holdout
chronology applies separately to any slice that changes recovery acceptance. Torus remains named
unsupported unless independently authorised.

F1 neutral-slice delivery chronology: after the recovery contract was frozen, two independent
exact-head reviews accepted it, the full non-holdout suite passed, and the composite budget passed,
MFTRCAD buckets 10–19 were authorised for reveal. The run reached a pre-existing Slot-recognition
`Standard_DomainError` while constructing a probe box and aborted before producing a complete
report. The lazy F1 index has no production consumer in this slice and was not queried by that
failure, so the attempt supplies no F1 score, pass, regression conclusion, or recovery-quality
evidence. Those buckets are nevertheless revealed and permanently consumed. The only post-reveal
implementation delta is generic refusal-branch test coverage; no recovery predicate, tolerance,
certificate, or production source changed.

### F2 — Complete smooth-sided AAG semantics

Preserve the current closed `ArcKind = convex | concave | smooth | unknown` and `None`-for-
non-adjacency contract byte-for-byte. Add a separate private closed `SmoothSide = neutral | convex |
concave | unproven`, queried only when the legacy pair arc is `smooth`. A named `is_any_smooth`
reads only the legacy first-order fact. `smooth_region` and every existing direct smooth caller
migrate through that helper, while exact nonsmooth callers keep their present comparison. No family
consumes `SmoothSide` in F2, so unavailable enrichment cannot tighten or relax recognition.

Sidedness is certified only from original closed-solid topology; F1 recovered facts remain
`RECOVERED_UNORIENTED`, and `oriented_fact` continues to refuse them. At each shared edge the graph
requires exactly two distinct incident faces owned by exactly one same original closed manifold
solid. Open faces/shells, cross-solid pairs, seams/self-adjacency, duplicate or ambiguous face
ownership, non-manifold incidence and ownership lookup failure make only `SmoothSide` unproven;
they never rewrite the legacy pair arc.

The legacy pair result is computed and cached first by today's exact midpoint/all-shared-edge
algorithm. Closed-solid eligibility and every second-order check gate only `SmoothSide`; they can
never veto or rewrite that legacy result. If the legacy result is `smooth`, then for each regular
nondegenerate shared edge sample deterministic arc-length fractions 1/4, 1/2 and 3/4. At each
sample, obtain each original face's outward normal and its inward boundary co-normal from the
face-oriented edge walk. Project that co-normal into the surface's first derivatives and evaluate
signed normal curvature from the second fundamental form:

`k = dot(n, a*a*duu + 2*a*b*duv + b*b*dvv) / |a*du + b*dv|^2`.

The sign convention is frozen by constructed geometry: negative outward-normal curvature is
smooth-convex and positive is smooth-concave. Curvature is made dimensionless with local length
`L = min(edge_length, sqrt(face_a_area), sqrt(face_b_area))`. `L` must be finite and positive.
With ADR-0008 constant `SMOOTH_CURVATURE_GAP = 1e-6`, `neutral` requires a stronger continuation
certificate: the two original surfaces must both be native analytic and have equivalent canonical
plane/cylinder/cone/sphere parameters. A new topology-free private `_analytic_surfaces` leaf owns
canonicalisation, finite/domain validation and equivalence; both `_effective_surfaces` and
`_adjacency` depend on it, and it imports only OCP plus `_geometry`. It owns no graph/node,
recovery, orientation, evidence or cache. This refactors F1 authority without changing recovery.

For local `L`, equivalence length tolerance is `1e-9 * L + COORD_FLOOR`; axis equivalence requires
`1 - abs(dot) <= 1e-9`; cone semi-angle difference is at most `1e-9` radians. Plane offsets use
the length tolerance. Cylinders require axis, closest-axis-line distance and radius agreement;
cones require axis, apex and semi-angle agreement; spheres require centre and radius agreement.
No kernel-handle identity shortcut is allowed because one surface may be instanced with different
placements. Curvature equality alone never proves neutral; a plane joined to a quartic tangent
surface is therefore `unproven` even when both boundary curvatures are zero.

Without that continuation certificate, each sample can prove a side only when the normalized
curvatures are materially unequal. A zero is omitted from sign unanimity only when its source is a
proven plane. Any other `abs(k*L) <= gap`, `abs((k_a-k_b)*L) <= gap`, empty remaining sign set, or
opposite strict signs is `unproven`. All remaining values strictly negative prove `convex`; all
strictly positive prove `concave`. Unavailable/degenerate D2 data, projection failure,
contradictory samples, seam/pole instability or unreliable orientation are also `unproven`.

Each immutable per-edge sided observation is cached against the exact original unordered node pair
and shared-edge identity, including `unproven`. The authoritative legacy pair arc remains in its
existing unordered-pair cache; the `SmoothSide` reduction has its own unordered-pair cache. All
three sided observations on every shared edge must agree, and multiple shared edges must agree;
otherwise the side is `unproven`. Swapping nodes, reversing edge traversal, kernel face order and
shared-edge order cannot change either fact.

Freeze an AST caller roster before migration. Current production dispositions are exact
nonsmooth comparisons in `_recess_core` and any-smooth traversal in `FaceGraph.smooth_region`;
tests/tools are classified too. Compatibility traversal uses `is_any_smooth(arc)`; sided reads use
only `smooth_side`. Truthiness and negative inference from `unknown`/`None` are forbidden after F2.
`_adjacency` retains ownership of both facts, observations and caches and may not import F1,
families, orchestration, claims or reconciliation.

Required evidence includes coplanar and same-cylinder/sphere/cone neutral splits; a plane-to-quartic
tangent false-neutral refusal; external boss and internal pocket rounds; unequal same-sign
curvature; an inflection/opposite-sign refusal;
mirror, rigid transform, scale, node/edge permutation and reversed orientation; periodic seams,
poles, degenerate edges/D2, open Face, two-solid Compound and non-manifold refusal; agreeing and
disagreeing multi-edge pairs; STEP round-trip; and mutation tests for all four `SmoothSide`
branches. Exact public records/order/to_dict, Candidate defining-node identities, full goldens and
performance remain unchanged. Close #129 as satisfied/superseded, retaining only this richer
smooth residual in #181.

Because F2 has no sided consumer and must preserve recognition output, it does not spend another
recognition holdout. Freeze algorithm and ADR-0008 constants before development-arc inspection,
then require synthetic/imported-development arc matrices, full/static/package/performance evidence
and two exact-head accepts. A future F3 or first sided consumer owns a separately predeclared
untouched holdout; consumed MFTRCAD buckets 10–19 may never be reused.

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
class SectionVertex:
    point: tuple[float, float]
    bulge: float  # tan(signed circular sweep / 4); zero is a line

@dataclass(frozen=True)
class PlanarSection:
    boundary: tuple[SectionVertex, ...]

@dataclass(frozen=True)
class SectionEnds:
    low_capped: bool
    high_capped: bool

@dataclass(frozen=True, eq=False)
class SectionOccurrence:
    body: BodyRef
    frame: LocalFrame
    run_interval: tuple[float, float]
    section: PlanarSection
    ends: SectionEnds
```

The bulge form is the closed line/arc union: each vertex starts the segment ending at the next
vertex; zero is a line and a finite non-zero value is the circular arc whose signed sweep is
`4*atan(bulge)`. It represents the existing polygonal sections without loss and does not force
obround slots/pockets into a false polygon. A full circle uses at least two arcs.

`PlanarSection` is intrinsic 2-D geometry. Placement, run extent, end topology and run-owned body
identity belong only to `SectionOccurrence`. `SectionEnds(False, False)` represents a through
section; the current blind adapter requires exactly one capped end, preserving which end is open.
An orchestration-owned issuer creates and validates `BodyRef`; records and callers cannot construct
or copy one into another run.

Canonical winding, area and centroid are analytic over the complete line-and-circular-arc loop,
not over its chord polygon or vertex mean. For bulge `b`, sweep is `4*atan(b)` and the circular
segment's signed area and Green-theorem first moments are included. Equivalent subdivision of an
arc therefore leaves area, centroid, frame origin and reconstructed geometry unchanged within the
named local geometry tolerance. Reversal maps each reversed edge to the negated bulge of the
oppositely directed original edge before choosing the canonical cyclic start. Non-adjacent
line/line, line/arc and arc/arc crossings, overlaps and tangencies are rejected; adjacent segments
may meet only at their shared endpoint. Bulges use a separate dimensionless serialization
precision, and serialization fails closed if a non-zero arc becomes zero or reconstruction moves
beyond the local tolerance.

Exact public names are deferred, but the invariants are not:

- `run`, `u` and `v` form a canonical right-handed orthonormal frame;
- intrinsic sections are origin-centred and frame origins are perpendicular to `run`, so inverse
  section/frame or origin/interval translations cannot create a second encoding of one geometry;
- sign and basis tie-breaks are deterministic under equivalent topology;
- sections have canonical winding and start vertex;
- run-local occurrence identity includes an orchestration-owned body reference, frame, run
  interval, section geometry and end topology; the pure frame/section values do not contain
  kernel objects;
- principal-axis inputs continue to project byte-identical legacy records during migration;
- oblique geometry is represented by a section record, never squeezed into `axis: str` spans;
- reconciliation names when a complete section record supersedes an axis-span fragment;
- schema/version/capability changes follow ADR 0005 and downstream golden migration.

The version-1 proposal also owns a normative consumer contract: world reconstruction uses the
rounded serialized basis directly (`origin + t*run + x*u + y*v`), never an unspecified
re-orthonormalization; serialized frame residuals have explicit validation bounds; vector lengths,
finite non-boolean numerics, end booleans, interval order and positive simple boundary winding are
validated. Length values are millimetres under the current capability contract. The nested value
inherits the future enclosing family record's capability-manifest `schema_version`; it does not
start a second version-negotiation protocol.

The discrete canonical-frame gauge is chosen from the six-decimal serialized run (positive
dominant component, ties Z→Y→X), while analytic vectors remain full precision. A consumer derives
the same expected basis for validation but reconstructs with the serialized vectors unchanged.
Serialized intrinsic centring and origin/run perpendicularity have explicit projection-derived
bounds. Every private occurrence read/projection revalidates the canonical frame, section, interval,
end topology and run-owned body provenance so reflection or foreign-state mutation fails closed.

This package is explicitly split into two halves with different risk and different clocks:

- **F4a — the schema**: private frame/section primitives, canonical tie-breaks, concrete
  legacy→section→legacy parity adapters for records that already carry truthful sections, and an
  independently reviewed versioned public proposal. It requires no recogniser changes. F4a lands
  early (see the recommended order) so F1 fixtures, F5 evidence and later F4b records are written
  once against the final geometry shape. The primitives remain private until F7; the first F4b
  family that emits a richer feature record owns the ADR 0005 public-schema transition.
- **F4b — the oblique predicates**: the hard geometry work in the `_recess_*` subsystem,
  delivered family-by-family whenever ready, with no shared cliff.

Sequence within the halves: neutral private frame primitives; versioned public proposal; exact
private compatibility adapters (F4a); then family-private oblique predicates and an authorised
public record transition; only then deprecation (F4b). Do not rewrite the whole `_recess_*`
subsystem in one PR. The package has no public deserializer, so "dual read" means consumer-owned
reading of the proposal; this repository proves only pure legacy→section→legacy projection.

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
