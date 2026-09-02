# E5 — Partial-mouth Prismatic Pocket validation

## Geometry and contract

Issue #460 addresses a specific failure of the equal-span wall-ring recogniser: treating only part
of a polygonal pocket mouth with a chamfer or rolling blend shortens at least one wall and breaks
the ring, although the cavity remains a constant-section, one-ended pocket.

The fallback starts from one original principal-plane inner wire and walks only exact concave or
smooth cavity incidences. It accepts only one same-solid region with a direct cycle of at least
three original planar wall supports, one distinct floor plane, an empty complete section from
mouth to floor, an empty exterior mouth slab, and material immediately behind the floor. The wall
cycle—not the treated wire—defines the section. Multiple or intersecting mouths, broken or
branching wall cycles, through voids, floor breaches, and every deeper non-mouth interruption fail
closed.

The planar supports remain defining evidence. The exact retained wall, treatment, and floor region
is constituent evidence; the opening stock face is consulted context only. The fallback stays in
`prismatic_pockets`, which remains the only record and evidence issuer. It creates no public cavity
graph, post-acceptance flood fill, second recognition authority, or corpus-derived predicate.

Authored tests cover partial chamfer and fillet treatments on triangular, rectangular, and
six-sided pockets; exact record/evidence identity; defining and constituent membership; through
void and drilled-floor refusal; signed-axis covariance; equal geometry on separate solids; STEP
round trip; and the existing sharp, completely treated, enclosed, reconciliation, and foreign-
graph controls. The final diff conforms to ADRs 0002, 0003, 0004, 0007, 0008, 0009, 0010, 0011,
and 0013. ADRs 0007 and 0010 contain the narrow issue-#460 amendment.

## Full MFCAD++ development evidence

The paired reports use the published MFCAD++ test split, lexical first 2,500 unique model IDs, raw
recognition, Python 3.12.14, build123d 0.11.1, OCP 7.9.3.1, taxonomy v10 SHA-256
`838c4daeb7c3a44f50dd8790d0dff526ff31747d3824d0a4438ed0cc4f2f2176`, and selection SHA-256
`ad92768788d88e3c4e3866bc2a614e7a345fea7fc52463dfc9f0b9b9e850058e`. Both evaluate 2,493
models, preserve the same seven known invalid dispositions, and return no empty aggregate result.

| Measure | Parent `c1f1368` | Partial mouths `b2e63f8` | Change |
| --- | ---: | ---: | ---: |
| accepted physical Prismatic Pockets | 1,626 | 1,659 | +33 |
| class-13 mapped records | 821 | 831 | +10 |
| class-14 mapped records | 934 | 942 | +8 |
| class-15 mapped records | 682 | 697 | +15 |
| triangular defining recall | 2,463 / 3,892 (0.6328) | 2,493 / 3,892 (0.6405) | +30 faces |
| triangular constituent coverage | 3,375 / 3,892 (0.8672) | 3,408 / 3,892 (0.8756) | +33 faces |
| rectangular defining recall | 2,154 / 4,895 (0.4400) | 2,186 / 4,895 (0.4466) | +32 faces |
| rectangular constituent coverage | 4,471 / 4,895 (0.9134) | 4,503 / 4,895 (0.9199) | +32 faces |
| six-sided defining recall | 4,092 / 5,707 (0.7170) | 4,182 / 5,707 (0.7328) | +90 faces |
| six-sided constituent coverage | 4,864 / 5,707 (0.8523) | 4,961 / 5,707 (0.8693) | +97 faces |
| class-0 constituent coverage | 577 / 1,017 (0.5674) | 601 / 1,017 (0.5910) | +24 treatment faces |
| taxonomy-mismatched defining faces | 15,506 | 15,506 | 0 |
| all-family unmapped records | 14,669 | 14,669 | 0 |

All 152 new defining claims belong to the intended Pocket classes: 30 triangular, 32 rectangular,
and 90 six-sided faces. Exactly 43 model rows change after excluding runtime: 33 gain one accepted
Prismatic Pocket, while 10 form one additional rectangular proposal that the existing Pocket
precedence correctly drops. Every other physical-family count is identical. No class loses face
coverage, and no mismatch or unmapped-record total increases.

Machine evidence:
[`effectiveness-mfcadpp-2500-pocket-mouth-b2e63f8.json`](effectiveness-mfcadpp-2500-pocket-mouth-b2e63f8.json),
SHA-256 `1601e17facb357ad4a93fc6980232addd11670550e97144419a5192d081b8457`.

MFInstSeg is not rerun for this increment. It remains the pseudo-blind aggregate transfer corpus;
no individual MFInstSeg model was inspected.

## Reproduction

Run the command below at the named clean commit. The seven published malformed inputs are retained
as explicit invalid dispositions rather than silently removed.

```bash
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version \
  "MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823" \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v10.json \
  --limit 2500 \
  --workers 4 \
  --allow-invalid \
  --output docs/benchmarks/effectiveness-mfcadpp-2500-pocket-mouth-b2e63f8.json
```

## Remaining Pocket work

This validates partial mouth treatments, not general cavity propagation. Deeper chamfer/blend
interruptions, split wall rings, shared/intersecting cavities, circular-end discovery, and the
remaining rectangular constituent-membership gap retain separate geometric contracts. Those
residuals must not be widened into this deliberately bounded rule from label evidence alone.
