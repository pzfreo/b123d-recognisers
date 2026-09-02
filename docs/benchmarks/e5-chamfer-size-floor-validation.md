# E5 chamfer size-floor validation

Issue #438 tests one bounded recognition change: remove the default 0.3 mm chamfer-leg floor
while retaining the existing explicit `tol=` filter. The former floor represented whether an
edge treatment was worth dimensioning, not whether its geometry was a chamfer. ADR 0001 assigns
that reporting decision to consumers; ADR 0008 is amended accordingly. No record schema,
ownership rule, reconciliation rule, or other geometric predicate changes.

## Evidence

The exact same lexical first 500 models from the published MFCAD++ test split were evaluated in
raw coordinates with taxonomy v10. The parent report is
[`effectiveness-mfcadpp-500-oriented-slot-72541af.json`](effectiveness-mfcadpp-500-oriented-slot-72541af.json)
(SHA-256 `a32620f37e29851c6f7f78b74dbb7ce5b08a38c513ef4decd87affb84ea9f1fa`). The candidate report is
[`effectiveness-mfcadpp-500-chamfer-af054c9.json`](effectiveness-mfcadpp-500-chamfer-af054c9.json)
(SHA-256 `8eb64eccdf41c3d6d7f3453f669e938e57b0d2955f3d0a8cc8eff2487ccbb5f0`). Both evaluated all 500
selected models with no invalid rows.

| Class 0 Chamfer metric | Parent | Candidate | Delta |
| --- | ---: | ---: | ---: |
| Defining faces | 69 / 214 (32.2%) | 82 / 214 (38.3%) | +13 faces, +6.1 pp |
| Covered faces | 97 / 214 (45.3%) | 110 / 214 (51.4%) | +13 faces, +6.1 pp |
| Defining precision | 69 / 94 (73.4%) | 82 / 107 (76.6%) | +3.2 pp |
| Physical Chamfer records | 86 | 99 | +13 |

The 13 new records occur in 12 models. Only class 0's summary changes; all other class summaries
are identical. This confirms the earlier counterfactual census and shows that aggregate ownership
and reconciliation preserve the gain without introducing an observed off-class tradeoff.

## Reproduction

```bash
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version \
  'MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823' \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v10.json \
  --limit 500 --allow-invalid \
  --output docs/benchmarks/effectiveness-mfcadpp-500-chamfer-af054c9.json
```

MFInstSeg is deliberately not a development gate for this change. Its previous aggregate result
provided direction; individual examples remain pseudo-blind and can be evaluated separately.
