# E5 — Passage mouth wire-order validation

## Why

The two-ended enclosure rule left 281 labelled six-sided faces at its straight-polygonal-section
gate in the first 500 MFCAD++ models. Inspection showed that both mouths had six line edges, but
`Wire.vertices()` did not enumerate their unique vertices in boundary order. The section builder
therefore rejected valid polygons before any Passage policy or material test ran.

## Rule and architecture

This correction derives each polygon corner as the one shared topological vertex between
consecutive ordered wire edges. Individual edge orientation is irrelevant. No tolerance,
label-specific branch, admission rule, Candidate schema, public evidence, or reconciliation policy
changes.

The final diff conforms to ADRs 0007, 0009 and 0010: topology construction stays in the neutral
`_section_passages` producer; Passage remains the only policy and Candidate issuer; and exact
original-face evidence remains behind the existing facade.

Authored controls exercise triangular, rectangular and six-sided wires with reversed individual
edge orientations. Existing tests retain interrupted-passage transformation, ownership, STEP,
evidence, blind, circular and shared-enclosure boundaries. A crossed void already decomposed into
historical cycles gains no additional fallback occurrence.

## Production effectiveness

The full taxonomy-v10 comparison evaluates 2,493 valid models from the lexical first 2,500
MFCAD++ test files and preserves the same seven known invalid-model dispositions. It compares
implementation `85ec17c` with the preceding two-ended-enclosure baseline:

| Measure | Parent | Edge incidence | Change |
| --- | ---: | ---: | ---: |
| physical Passage records | 1,580 | 1,775 | +195 |
| triangular mapped records | 625 | 626 | +1 |
| rectangular mapped records | 471 | 560 | +89 |
| six-sided mapped records | 503 | 613 | +110 |
| triangular face coverage | 0.6822 | 0.6869 | +0.0047 |
| rectangular face coverage | 0.7576 | 0.8085 | +0.0509 |
| six-sided face coverage | 0.5172 | 0.6418 | +0.1246 |
| six-sided defining-face recall | 0.4670 | 0.6023 | +0.1353 |
| taxonomy-mismatched defining faces | 15,577 | 15,525 | -52 |
| unmapped records, all families | 14,707 | 14,681 | -26 |

This is production output, not the broader audit ceiling. One-vs-class Passage precision is not a
useful regression signal here because legitimate rectangular and six-sided Passage faces share
the family-wide prediction denominator; mismatches and unmapped output both improve.

Machine evidence:
[`effectiveness-mfcadpp-2500-wire-order-85ec17c.json`](effectiveness-mfcadpp-2500-wire-order-85ec17c.json),
SHA-256 `dcddb1365d27c97e35f0c4b91c35617c7c0bc7a36630ee738cbc58b159ff7570`.

## Residual gate census

The label-blind audit constructs two-ended regions, removes occurrences already found by the
historical cycle path, and records the first fallback gate. For six-sided labelled faces:

| First outcome | Unique faces | Pure regions |
| --- | ---: | ---: |
| existing cycle | 2,858 | 449 |
| accepted fallback | 1,001 | 117 |
| opposed openings or solid | 679 | 104 |
| mouth congruence | 228 | 0 |
| planar mouth seed | 190 | 20 |
| straight polygonal sections | 0 | 0 |
| axial interval | 0 | 0 |
| material or open ends | 0 | 0 |

The correction eliminates the entire straight-section rejection bucket. The opposed-opening/solid
gate is now the largest pure residual and should be investigated separately rather than loosened
as part of this fix. Production proposes 613 dominant six-sided occurrences; the audit's raw
partitions are diagnostic reach and must not be subtracted directly from production face coverage.

Machine evidence:
[`mfcadpp-passage-rejection-census-85ec17c.json`](mfcadpp-passage-rejection-census-85ec17c.json),
SHA-256 `ba56b7df5623034cbe4bf5a65278c4242db89e7d5eb89b612d6405f8f7f537fe`.

Generate both reports with:

```console
uv run python tools/run_effectiveness_baseline.py mfcadpp \
  /path/to/MFCAD++_dataset/step/test \
  --dataset-version \
  "MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823" \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v10.json \
  --limit 2500 --workers 4 --allow-invalid \
  --checkpoint-dir .cache/effectiveness/mfcadpp-2500-85ec17c \
  --output /tmp/effectiveness-mfcadpp-2500-wire-order.json

uv run python tools/audit_mfcadpp_passage_rejections.py \
  /path/to/MFCAD++_dataset/step/test --limit 2500 \
  --output /tmp/mfcadpp-passage-rejection-census.json
```
