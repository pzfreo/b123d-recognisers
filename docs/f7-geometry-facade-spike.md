# F7 GeometryGraph consumer spike

## Decision

**No-go on publishing `GeometryGraph` in its present form. Go on reviewing the graph-independent
`inspect_face(face)` contract for publication.**

The spike is successful as an experiment: two real consumers run through one provisional module,
existing recognition remains unchanged, authority and provenance survive projection, and real
Polygonal Boss performance is neutral. It does not, however, prove that Draftwright needs a graph.
Its concrete workflow—declaring a fillet from its cylindrical face—needs one analytic face fact and
one on-surface anchor. Constructing a graph around that single face is safe but conceptually larger
than the problem.

Publishing the facade now would therefore repeat the mistake identified by the epic retrospective:
freezing infrastructure because it exists rather than because a consumer needs it.

## Concrete consumers

### Polygonal Boss

`polygonal_bosses` remains responsible for the six-support-cycle policy, but all of its geometry
now arrives through `GeometryGraph`: inventory, adjacency, normals, bounds, effective surfaces,
blend selection, collapse and expanded occurrence provenance. It imports none of `FaceGraph`,
`EffectiveSurfaceIndex`, `BlendCollapseIndex` or `CollapsedGraphView`.

Evidence crosses one package-private bridge. The bridge accepts facade `FaceRef` values only from
the writer's exact run, resolves borrowed proposal faces against that authority, validates every
occurrence before the first publication, and then delegates issuance to the existing writer. This
preserves the original graph as the sole evidence authority without exposing it to the recogniser
or creating a second aggregate graph. Multi-solid discovery still uses per-solid facades and
re-resolves the six borrowed defining faces against the whole-run authority at publication.

### Draftwright declared fillet

`draftwright.model.declare.fillet(face)` previously opened `BRepAdaptor_Surface` itself, then used
a one-face `GeometryGraph` during the first spike. It now calls only `inspect_face(face)` to obtain:

- the analytic cylinder kind;
- canonical axis and radius parameters;
- the midpoint of the trimmed surface domain as an on-round leader anchor;
- a closed refusal for a non-cylindrical face.

This is a production workflow, not a demonstration endpoint. Existing declared-versus-detected
anchor parity and drawing tests continue to pass.

## Provisional surface

The spike module remains absent from the package root exports and capability manifest. It now has
two deliberately different surfaces:

- `inspect_face(face) -> FaceInspection`, a graph-independent value containing only a closed
  analytic fact and optional trimmed-surface anchor;
- a run-local, nonserializable graph surface for the in-package Polygonal Boss experiment:

- `GeometryGraph`, `FaceRef`, `BoundaryRef`, `BlendRef`;
- `AnalyticSurface | RefusedSurface`;
- `BlendFact`, `CollapsedBridge`, `GeometryProvenance`;
- face inventory, borrowed face, adjacency, arcs, smooth regions, bounds and normals;
- effective surface fact and trimmed-surface anchor;
- blend facts and explicit selected collapsed bridges.

It deliberately excludes correspondence, snapshots, body descriptors, matching, sections,
Candidate/evidence, registries, reconciliation, codecs, persistent IDs and plugin discovery.

The collapsed API is smaller than the private implementation: consumers receive only synthetic
support bridges and complete original face/boundary provenance. Private logical nodes, internal
cache values, issuers, run tokens and raw OCCT occurrence objects do not escape.

## Evidence

The spike tests cover:

- foreign and copied face-reference refusal;
- native cylinder parameters and an on-surface anchor;
- exact BSpline analytic recovery with recovered-unoriented provenance;
- a closed unsupported-surface refusal value;
- six selected convex blend bridges with exact occurrence multiplicity;
- translation, rotation and combined rigid transforms;
- STEP export/import round-trip;
- Draftwright's actual declared-fillet success and planar-face refusal;
- source guards proving Draftwright imports only `AnalyticSurface` and `inspect_face`, and proving
  Polygonal Boss imports only the facade rather than graph/surface/blend internals;
- same-run evidence publication plus foreign-run, copied/stale reference, incomplete inventory,
  invalid-solid and zero-prefix refusal behavior.

Final receipts for the simplified spike:

- 135 facade, Polygonal Boss/Stock authority, run-context and architecture tests passed;
- 2,265 of 2,266 package tests passed in the complete no-coverage run; the sole failure was the
  installed-wheel mypy check, which exposed a missing `GeometryGraph.bounds` return annotation;
- after adding that annotation, the isolated installed-wheel runtime/manifest/mypy test passed;
- 13 existing Draftwright fillet tests and 3 Draftwright spike/boundary tests passed;
- Ruff, mypy and diff-whitespace checks passed for the touched surfaces.

The normal coverage-instrumented full run was stopped after 450 passing tests because tracing an
unrelated F6 `math.nextafter` threshold loop had consumed 34 minutes. The same F6 test passed in
15.7 seconds without coverage. This is recorded as a verification-environment limitation, not
presented as a green full-coverage receipt.

## Performance

`tools/benchmark_geometry_spike.py` performs seven samples per process. Three independent process
runs gave these medians:

| Operation | Direct private seam | Facade | Interpretation |
|---|---:|---:|---|
| Complete blend query | 68.9 ms | 76.5 ms | facade micro median about 11% slower; individual rounds ranged from slightly faster to 21% slower |
| One-face fillet read | 13.7 µs | 124.3 µs | `inspect_face` adds about 0.11 ms; immaterial to drawing runtime and no graph leaks into the consumer |

Peak process RSS stayed within roughly 0.2% in all modes.

The decision-relevant comparison ran the complete Polygonal Boss recogniser against an archived
`main` source tree and the spike in alternating fresh processes. Across three rounds, the median
baseline was 75.8 ms and the median spike was 71.9 ms; peak RSS differed by about 0.08%. This does
not claim a speed-up—the workload is noisy—but it rules out a material consumer regression.

## Publication recommendation

1. Do not publish or manifest `experimental_geometry`.
2. Treat `inspect_face` as the only publication candidate. Give its naming, refusal model and
   optional-anchor behavior a normal API review; the Draftwright fillet consumer now proves the
   contract without knowing a graph exists.
3. Keep the graph/blend projection experimental for Polygonal Boss until a second out-of-tree workflow
   needs adjacency or selected-collapse provenance.
4. If that workflow appears, publish `GeometryGraph` with only the operations exercised by both
   consumers. Otherwise publish only face inspection and leave graph/blend private.
5. Continue to exclude F6 correspondence and section placement from F7.

The implementation answers the spike question cleanly: the architecture can hide the internals
without semantic or authority loss, but that fact alone does not justify publishing the graph.
The small face API has concrete external demand; the graph facade currently has only one internal
consumer and should stay provisional.
