# Prior art: graph-based feature recognition

Survey notes supporting [ADR 0004](adr/0004-attributed-geometry-graph-and-residual-evidence.md), which
proposes an attributed geometry graph and cites Analysis Situs as its architectural precedent. This
page records what that precedent actually is, what the field did next, and which parts are available
to a package bound by [ADR 0001](adr/0001-standalone-geometry-only-apache-library.md) and
[ADR 0002](adr/0002-uniform-deterministic-recogniser-contract.md).

**This is not a decision.** ADR 0004 is where the decision lives; this is the reading behind it.
Assessed August 2026 — the learned-methods section is time-bound and will date faster than the rest.

## The attributed adjacency graph

Nodes are B-Rep **faces**. Arcs are **adjacency between faces**, one arc per face pair however many
edges they share; the shared edges are cached as arc attributes. Arcs carry a **dihedral-angle
classification**, and a feature is then a *subgraph*, so recognition becomes subgraph matching plus
connected-component analysis. Results are written back onto the graph as further attributes, so
recognition accretes rather than returning in one shot.

Read from `asiAlgo_AAG.h` rather than the documentation, three details matter here that the prose
pages do not give:

- **The angle taxonomy has seven values, not four**: `Undefined`, `Concave`, `Convex`, `Smooth`,
  `SmoothConcave`, `SmoothConvex`, `NonManifold`. The smooth-but-still-sided pair is the useful
  part — a tangential join still has a material side, and collapsing that distinction loses the
  thing a recogniser needs. An earlier draft of this page said "tangential", which is not a value
  the enum carries.
- **Smoothness is opt-in and gated by an *angular* tolerance.** `allowSmooth` defaults to `false`
  and `smoothAngularTol` to `1e-4`. That the gate is an angle rather than a length is significant
  for this project: an angular tolerance is dimensionless, so it sidesteps the scaling trap that
  issue #72 was about entirely.
- **`Collapse()` is the blend-suppression primitive**, and it propagates dihedral attributes to the
  newly inserted transition arcs *only where the angles are equal*. Its own header carries a
  caution that those inserted attributes are not cleaned up by `PopSubgraph()`.

The graph also keeps a **stack** of adjacency matrices (`PushSubgraph`/`PopSubgraph`), and offers
edge-filtered neighbour queries (`GetNeighborsThru`, `GetNeighborsThruX`) — so "neighbours, but not
through this edge" is a first-class operation rather than something a caller reconstructs.

Analysis Situs implements this and is the only open-source graph-based feature-recognition
framework. It is BSD 3-Clause, so Apache-2.0 compatible; ADR 0004's "pattern, not dependency or
copied algorithm" position is a design choice rather than a licensing constraint. It also ships a
rule-based path that scans faces checking surface types and normals without building a graph —
**which is what this package does today**.

Three limitations are documented by its authors and matter to any adoption here:

- **Edge-based adjacency only.** Faces meeting at a vertex only — vertex blends — have no arc
  unless vertex adjacency is added explicitly.
- **Blends must be suppressed to see through them.** Recognition needs "collapse functions" that
  virtually remove fillets while analysing what they join.
- **Face indices are per-model.** Any geometric change invalidates them and the graph is rebuilt.
  ADR 0004 independently reaches the same conclusion: raw indices are not persistent identity.

## What the field did next

The graph was not displaced. It was absorbed, and the reasoning layer above it moved:

| period | representation | matching |
| --- | --- | --- |
| 1988–2010s | AAG | subgraph isomorphism against hand-written patterns |
| ~2019–2023 | AAG / gAAG | GNN message-passing — AAGNet, UV-Net, BRepNet |
| 2024–2026 | the same graph | graph transformers with attention (BrepMFR, BRepFormer, BRT), self-supervised pretraining, synthetic-to-real domain adaptation |

The reason for the last shift is specific: message-passing architectures have restricted receptive
fields and network depths, which global attention removes. That is a limitation of the *propagation
scheme*, not of the AAG. Reported trade-offs among the learned encoders are similarly narrow —
UV-Net is rotation-variant because it consumes xyz coordinates and normals directly, while BRepNet
buys rotation invariance with weaker discrimination between geometries.

The practical reading: adopting an AAG is not backing a superseded representation. It is adopting
the one the field converged on and has not left.

## Why the learned branch is closed to this package

Everything after roughly 2019 is learned, and that conflicts with the contracts this package is
built on rather than merely being unimplemented:

- **ADR 0002** requires deterministic records pinned to byte-identical semantic goldens. A
  classifier cannot be pinned to one.
- **ADR 0001** is geometry-only and consumer-policy-free. A model artefact and the distribution it
  was trained on *are* policy, and undeclared policy at that.
- The runtime currently depends on build123d/OCP and nothing else.

There is also a deployment argument independent of the ADRs: a CAM toolpath or a drawing dimension
cannot be driven from a 94%-accurate classifier without human review, which is why deterministic
recognisers persist in production even where learned ones win on benchmarks.

So the honest position is that this package is not on the academic frontier and should not try to
be — the frontier is not reachable without giving up the properties that make it useful.

## Labelled corpora

| dataset | size | labels |
| --- | --- | --- |
| MFCAD | 15,488 models | per-face machining-feature labels, planar features |
| MFCAD++ | 59,655 models | 24 feature classes plus stock faces, 3–10 *interacting* features per model |
| MFInstSeg | 60,000+ models | semantic, instance and bottom-face labels |

All are STEP with per-face labels, distributed as `steps/`, `labels/` and `aag/` directories. The
`aag/` graphs are only useful to a consumer that has adopted the representation; a deterministic
recogniser reading STEP wants `steps/` and `labels/`.

They are directly consumable here: [`tests/test_step_round_trip.py`](../tests/test_step_round_trip.py)
proves every pinned fixture survives STEP export and re-import with byte-identical records, so the
file boundary is not a confounder.

Two cautions. MFCAD++ is known to contain topological errors — AAGNet's authors cleaned it before
training. And synthetic-to-real domain adaptation is an *active research problem*, which is direct
evidence that these labels do not transfer cleanly to real parts. They are better used as a
false-negative detector than as ground truth about capability.

Licensing: AAGNet's code is MIT, and so is [MFCAD](https://github.com/hducg/MFCAD) — its STEP
models and labels are in-repository under that licence, so a sample can be pulled without
credentials. MFCAD++ and MFInstSeg are distributed through Baidu AI Studio and Google Drive and
their terms are not stated alongside the code; check before vendoring either.

The `.face_truth` labels are Python pickles. Disassemble them with `pickletools.dis` rather than
loading them blindly. The inspected files contain only `EMPTY_LIST`, `BININT1`, and `APPENDS`, with
no `GLOBAL` or `REDUCE`; confirm that per file rather than assuming it across the full dataset.

## What this implies here

**The corpus gap is the pressing problem, not the architecture.** Proven scope currently rests on
17 hand-built fixtures. That is a thin base for [`capabilities.md`](capabilities.md), whose whole
purpose is honesty about what recognition does and does not claim — and it is demonstrably thin: a
2.5x change in `tol` reclassifies nothing in it (epic 0001, finding 2c), so the corpus barely
constrains the values it is supposed to justify.

**Measurement is cheaper than the graph, and can come first.** Counting models where
`feature_census` is empty while labels say features exist needs no new code and would find the
class of failure that [#60](https://github.com/pzfreo/b123d-recognisers/issues/60) represents —
which was found by hand-writing a single test.

**Recall scoring needs face ownership, not the whole graph.** The labels are per-face; recognisers
return records that do not say which faces they consumed. A per-run ownership map — kept alongside
the result, never inside a record, per ADR 0002 and ADR 0004's own caution about face indices — is
the minimum that makes scoring possible, and is a fraction of ADR 0004.

**The hard case is agreed.** Every source names *intersecting features* as where rule-based
recognition breaks, which is why MFCAD++ packs 3–10 interacting features per model. The current
fixtures barely exercise interaction.

**A gap in ADR 0004's acceptance evidence.** It asks that fillets and harmless face splitting "do
not flood residual diagnostics" — treating blends as *noise*. Issue #60 shows they are also
*bridges*: a chamfered groove is unrecognised because cone faces sit between the cylindrical bands
and break the contiguity the recogniser requires. Analysis Situs handles exactly this with blend
collapse. Traversing through a blend deserves its own acceptance criterion alongside not drowning
in them.

## What would change this assessment

- A deterministic subgraph-matching recogniser that handles intersecting features without
  per-feature hand-written patterns would make the graph more compelling than measurement.
- Evidence that synthetic-to-real transfer is solved would make the labelled corpora usable as
  capability ground truth rather than only as a false-negative detector.
- A learned method with a determinism guarantee — a decidable, explainable output that can be
  pinned to a golden — would reopen the branch ADR 0002 currently closes.

## Sources

- [Analysis Situs — attributed adjacency graph](https://analysissitus.org/features/features_aag.html)
- [Analysis Situs — feature recognition framework](https://analysissitus.org/features/features_feature-recognition-framework.html)
- [Analysis Situs source (BSD 3-Clause)](https://gitlab.com/ssv/AnalysisSitus) — `asiAlgo_AAG.h`
  is the graph; `asiAlgo_FeatureAngleType.h` is the arc taxonomy
- Slyadnev, Malyshev, Voevodin, Turlapov, *On the Role of Graph Theory Apparatus in a CAD Modeling
  Kernel*, GraphiCon 2020 — the heuristics that make subgraph isomorphism interactive
- Malyshev, Slyadnev, Turlapov, *[Graph-based feature recognition and suppression on the solid
  models](https://www.semanticscholar.org/paper/09b2b9e0adcb0157b611c8f1887165fe2807a290)*
- Slyadnev, Voevodin, *[Automatic Detection of Manufacturing Issues in CAD Parts for DFM
  Analysis](https://link.springer.com/chapter/10.1007/978-3-031-59652-0_6)*, 2024
- [Analysis Situs references page](https://analysissitus.org/references.html) — the authors' own list
- [AAGNet — GNN for multi-task machining feature recognition](https://www.sciencedirect.com/science/article/abs/pii/S0736584523001369)
  ([code and datasets](https://github.com/whjdark/AAGNet))
- [MFCAD dataset](https://github.com/hducg/MFCAD)
- [BrepMFR — graph transformer with domain adaptation](https://www.sciencedirect.com/science/article/abs/pii/S0167839624000529)
- [BRepFormer — transformer-based B-Rep feature recognition](https://arxiv.org/pdf/2504.07378)
- [BRT — B-Rep learning via Transformer](https://arxiv.org/html/2504.07134v1)
