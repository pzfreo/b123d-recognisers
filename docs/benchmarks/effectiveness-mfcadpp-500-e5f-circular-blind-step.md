# MFCAD++ E5f: Circular Blind Steps

Canonical result:
[`effectiveness-mfcadpp-500-e5f-6946256.json`](effectiveness-mfcadpp-500-e5f-6946256.json).
Metric definitions and corpus policy are in the
[`effectiveness baseline method`](effectiveness-baseline-method.md).

## Provenance

- Production and benchmark commit: `6946256cc8a19e97c7aa452454dfcf1ba634d544`
- Comparison report: `effectiveness-mfcadpp-500-e5d-e1e7e22.json`
- Geometry audit: [`Circular Blind Step miss anatomy`](circular-blind-step-miss-audit-mfcadpp-500.md)
- Corpus: MFCAD++ published test split; DOI
  `10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823`
- Selection: first 500 unique STEP IDs in lexical order
- Selection hash: `323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`
- Taxonomy: `effectiveness-taxonomy-v2.json`, SHA-256
  `67f092a2aa8d08be94e9be409c1fb338350626c7f4d1398c2f78be3123977f3b`
- Result: 500 selected, loaded and evaluated; zero invalid or empty models

Taxonomy v2 changes only class 21 from the historical Fillet proxy to the dedicated
`circular-blind-steps` family. Version 1 remains immutable for historical reports.

## Effectiveness result

The aggregate returns 118 Circular Blind Step occurrences. All 236 original defining faces carry
MFCAD++ class 21: defining-face precision is 236/236 (100%) and defining-face recall is 236/354
(66.67%). This reproduces the audit's 118-occurrence projection exactly. The non-native
shared-edge component proxy remains 117/173 (67.63%); MFCAD++ supplies no native instance relation.

All 118 raw proposals survive. Reconciliation removes exactly 114 Fillets whose defining curved
wall is contained in a surviving Circular Blind Step's two-face evidence. Fillets therefore move
from 170 to 56; Plates remain 234. Every other pre-existing physical-family count is unchanged.
The paired enabled/disabled run independently confirms that every output other than the new tuple
and this named Fillet reconciliation is identical on all 500 models. Its strengthened exact check
also proves the enabled Fillet tuple equals the disabled tuple minus precisely the candidates with
the named Circular Blind Step disposition.

The taxonomy transition makes cross-version aggregate mapped-class and mismatch totals
non-comparable for classes 21 and 23: v1 treated class-21 faces as Fillet evidence, while v2 treats
remaining class-21 Fillets as taxonomy mismatches. The report retains those values rather than
presenting the mapping correction as a production regression.

## Geometry and evidence contract

The recogniser accepts an inward native or certified quarter-cylinder on one principal axis, one
concave principal interior terminal, the opposite same-solid envelope opening, two convex
transverse principal sides, one convex axial opening face and an exactly empty terminal-sector
sweep. The separately named angular parameter tolerance is `1e-7` radians; authored tests pin both
sides and both signs of its boundary.

The immutable record retains terminal-to-opening centreline direction and a canonical transverse
quarter-section. Each Candidate owns exactly the original cylindrical wall and planar terminal,
including effective-surface provenance, and the complete proposal batch validates before issuance.
Authored exclusions cover bores, through/capped/non-quarter cylinders, external, conical, oblique
and enclosed lookalikes, invalid shells, foreign evidence and cross-solid composition.

## Runtime result

The paired MFCAD++-500 sentinel at review-fix commit `df4e4c1` finds 118 raw and accepted
occurrences, reconciles exactly 114 Fillets and preserves every other output. Enabled time is
232.800 seconds versus 226.653 disabled: ratio 1.0271, with a paired median delta of 0.0087
seconds.

The complete 13-part NIST/Gramel census finds no Circular Blind Steps and preserves every
pre-existing output. Enabled time is 189.311 seconds versus 191.522 disabled: ratio 0.9885, with a
paired median delta of -0.1106 seconds. Both workloads remain below the 1.10 gate, and both report
`all_fillet_reconciliations_exact=true`.

Detailed artifacts:

- [`MFCAD++ paired performance`](circular-blind-step-performance-mfcadpp-500-df4e4c1.json)
- [`NIST/Gramel paired performance`](circular-blind-step-performance-census-df4e4c1.json)

## Reproduction and transfer status

```console
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version \
  'MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823' \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v2.json \
  --limit 500 \
  --output docs/benchmarks/effectiveness-mfcadpp-500-e5f-6946256.json

uv run python tools/benchmark_circular_blind_steps.py mfcadpp \
  --root /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --limit 500 \
  --output docs/benchmarks/circular-blind-step-performance-mfcadpp-500-df4e4c1.json

uv run python tools/benchmark_circular_blind_steps.py census \
  --output docs/benchmarks/circular-blind-step-performance-census-df4e4c1.json
```

MFInstSeg was not inspected or used for development. At validation time both requested candidate
mounts, `/app/workspaces-codex/datasets/mfinstseg` and `/app/workspaces/datasets/mfinstseg`, were
absent. No substitute corpus was used; #293 remains open.

ADRs 0001, 0002, 0003, 0004, 0005, 0007, 0008 and 0011 were reviewed before implementation. The
final-diff audit and two bounded independent reviews are recorded in the implementation PR.
