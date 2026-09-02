# E5 public concave Blend validation

Issue #440 publishes complete concave cylindrical edge-blend chains without publishing circular
slot ends. It retains the existing `BlendCollapseIndex` proof—one same-solid, nonbranching,
same-cylinder/radius chain, one consistently proved material side, two unambiguous support regions
and complete original boundaries—and adds one public concave projection rule: two proved parallel
planar supports have no intersection edge to round, so their tangent cylinder is not a Blend.

## Authored contract

An internal-pocket fixture proves four concave radius-2 Blends coexisting with one enclosing
PrismaticPocket. Each Blend's curved face is exact defining and constituent evidence and is also a
member of the Pocket's constituent region. Rigid motion, scale and compound tests preserve side,
radius, direction and body-local identity. An authored obround passage proves parallel-wall
semicircular ends remain absent. Existing sharp, full-cylinder, CircularBlindStep, annular
Boss/Hole, incomplete, ambiguous, branching and mixed-radius controls remain negative.

The obround control was not anticipated from corpus labels: it was found by the ordinary semantic
golden suite when the initial broad projection moved a Draftwright-facing slot fixture. That broad
change was rejected rather than blessing the moved golden.

## Complete MFCAD++ result

The canonical candidate report is
[`effectiveness-mfcadpp-2500-concave-blends-47a5f04.json`](effectiveness-mfcadpp-2500-concave-blends-47a5f04.json),
SHA-256 `0e7ed19e84f847046ae5243b9b286e70aaeabb2c64e998a41556e24c2f4b9b01`.
It evaluates the complete published 2,500-model test split in raw coordinates with taxonomy v10:
2,493 models evaluate and the same seven named Hole rows remain invalid.

| Round / Blend measure | Convex-only | Narrow concave | Initial broad concave |
| --- | ---: | ---: | ---: |
| Physical Blend occurrences | 5 | 6 | 1,832 |
| Round defining faces | 5 / 13 | 6 / 13 | 6 / 13 |
| Round covered faces | 10 / 13 | 10 / 13 | 10 / 13 |
| All mapped Fillet + Blend defining precision | 5 / 224 | 6 / 225 | 6 / 2,053 |

Exactly one new occurrence survives, in model 16032. Its sole defining face is class 23 Round. The
parallel-support rule removes 1,826 of the 1,827 broad concave additions while retaining that one
independently labelled example. This is not a label-tuned predicate: it follows from whether the
two support surfaces can form the edge an edge blend replaces, and is pinned by authored internal
corner and obround controls.

MFCAD++'s 13-face Round population remains too small to predict transfer magnitude. The latest
aggregate-only MFInstSeg/Analysis Situs memo indicates concave Round geometry is much more common
there, but no individual transfer model or label decomposition entered this implementation. A
later aggregate rerun is the independent transfer test.

## Public and downstream contract

`Blend.side` now admits `"concave"`, changing the documented meaning of an existing serialized
field. ADR 0005 therefore advances `Blend` from schema version 1 to 2 even though field names and
types are unchanged. This requires a future minor release and explicit consumer opt-in. It does
not authorize a release beyond v0.4.12 in this epic.

Draftwright currently consumes `Fillet`, not `Blend`. This increment exposes deterministic
internal-round radius and face identity but does not claim drawing output until Draftwright adopts
schema version 2 in a later release cycle.

## Reproduction

```bash
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version \
  'MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823' \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v10.json \
  --limit 2500 --allow-invalid \
  --output docs/benchmarks/effectiveness-mfcadpp-2500-concave-blends-47a5f04.json
```
