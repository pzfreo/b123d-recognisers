# F7 GeometryGraph consumer spike

## Decision

**No-go on publishing `GeometryGraph` in its present form. Go on retaining the small projection
pattern and extracting a still smaller face-inspection API first.**

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

`polygonal_bosses` remains responsible for the six-support-cycle policy. It now reaches recovered
surface facts, blend-chain discovery, selected collapse and expanded occurrence provenance only
through `b123d_recognisers.experimental_geometry`. It no longer imports `EffectiveSurfaceIndex`,
`BlendCollapseIndex`, `CollapsedGraphView` or their provenance values.

The base recognition and evidence path still uses private `FaceGraph`. That is intentional and
honest: the aggregate evidence writer owns that exact graph today. This spike did not invent a
second graph or weaken same-run evidence authority merely to claim a complete migration.

### Draftwright declared fillet

`draftwright.model.declare.fillet(face)` previously opened `BRepAdaptor_Surface` itself and called
the recogniser-specific `fillet_anchor` helper. It now uses only the provisional facade to obtain:

- the analytic cylinder kind;
- canonical axis and radius parameters;
- the midpoint of the trimmed surface domain as an on-round leader anchor;
- a closed refusal for a non-cylindrical face.

This is a production workflow, not a demonstration endpoint. Existing declared-versus-detected
anchor parity and drawing tests continue to pass.

## Provisional surface

The spike module is absent from the package root exports and capability manifest. Its values are
run-local and nonserializable:

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
- source guards preventing Draftwright private-package imports and preventing Polygonal Boss from
  constructing the private surface/blend classes directly.

Focused receipts at the spike head:

- 109 Polygonal Boss/blend/ring tests passed;
- 11 facade authority/schema/surface/blend/transform/STEP tests passed;
- 13 existing Draftwright fillet tests passed;
- 3 Draftwright spike/boundary tests passed.

## Performance

`tools/benchmark_geometry_spike.py` performs seven samples per process. Three independent process
runs gave these medians:

| Operation | Direct private seam | Facade | Interpretation |
|---|---:|---:|---|
| Complete blend query | 68.9 ms | 76.5 ms | facade micro median about 11% slower; individual rounds ranged from slightly faster to 21% slower |
| One-face fillet read | 11.7 µs | 196.6 µs | about 0.185 ms absolute overhead; irrelevant to drawing runtime but evidence that a graph is oversized for this task |

Peak process RSS stayed within roughly 0.2% in all modes.

The decision-relevant comparison ran the complete Polygonal Boss recogniser against an archived
`main` source tree and the spike in alternating fresh processes. Across three rounds, the median
baseline was 75.8 ms and the median spike was 71.9 ms; peak RSS differed by about 0.08%. This does
not claim a speed-up—the workload is noisy—but it rules out a material consumer regression.

## Simplest next step

1. Do not publish or manifest `experimental_geometry`.
2. Extract a tiny graph-independent `inspect_face(face)` result containing the closed analytic
   fact and surface anchor; validate it against Draftwright's fillet and flat declaration paths.
3. Keep the graph/blend projection private for Polygonal Boss until a second out-of-tree workflow
   needs adjacency or selected-collapse provenance.
4. If that workflow appears, publish `GeometryGraph` with only the operations exercised by both
   consumers. Otherwise publish only face inspection and leave graph/blend private.
5. Continue to exclude F6 correspondence and section placement from F7.

This preserves the epic's useful authority boundaries while avoiding another large compatibility
surface whose only external consumer uses one face.
