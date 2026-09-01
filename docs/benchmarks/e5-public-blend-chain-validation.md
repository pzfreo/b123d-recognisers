# E5 public Blend chain validation

Issue #414 publishes the existing label-independent `BlendCollapseIndex` as a conservative
physical `Blend` family. One occurrence is one complete same-solid, same-radius native cylindrical
rolling-ball chain. `Fillet` retains precedence where its exact defining-face union covers the
chain. [ADR 0013](../adr/0013-public-blend-chain-recognition.md) records the public contract.

## Evidence protocol

- Authored geometry supplies positive convex and concave chains, small-radius and free-axis
  examples, compounds, rigid transforms, traversal-order invariance, and sharp/full-cylinder
  negatives.
- The package golden `small_convex_blends` proves the supported public result, census, and archive
  surface end to end.
- MFCAD++ is open development evidence. Discovery and ownership do not read its labels; taxonomy
  v9 adds `blends` beside `fillets` only for class 23, `Round`.
- MFInstSeg remains sealed for this development increment. No individual model, miss, instance,
  face, or class decomposition is inspected or used to shape the implementation.
- Analysis Situs comparison is deferred until the reviewed implementation is merged to `main`.

## Complete-corpus invalid-model policy

The standard lexical first 500 MFCAD++ models contain only one Round face, so the effectiveness
gate uses the complete lexical 2,500-model test split. A clean fail-closed diagnostic found that
all 2,500 STEP files import, but aggregate recognition rejects these seven models before scoring.
The diagnostic implementation commit is
`7be23930bab485dfab52e886e8e137865ba18086` (tree
`ad45310b83fa2ccf9fce3d1bcf50a394d5bfa200`):

`12939`, `13975`, `14052`, `14307`, `18628`, `22386`, and `22439`.

Every rejection is the same pre-existing Hole ownership invariant:
`Hole cylindrical evidence does not prove one valid solid`. The label-independent diagnostic ran
`_take_inventory` over every selected model and did not inspect semantic labels. These seven cases
are retained as named `invalid` rows and excluded from every evaluated-face denominator; they are
not converted into Blend misses. A change in this exact ID/reason set invalidates the policy and
must be investigated before accepting a later report.

The canonical report command is:

```bash
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version \
  'MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823' \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v9.json \
  --allow-invalid \
  --output docs/benchmarks/effectiveness-mfcadpp-2500-blends-<commit>.json
```

The final report, measured result, independent review, and merge authority will be added after the
corpus run completes.
