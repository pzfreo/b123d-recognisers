# E5 — Floor-seeded Prismatic Pocket validation

## Geometry and contract

Issue #460 addresses polygonal pockets whose mouth-side wall cycle is broken by a deeper side
opening while the original floor remains intact. The fallback starts from that floor rather than
reconstructing a template from corpus labels. It requires one straight-edged, non-four-sided,
principal-plane floor wire; exactly one concave original planar wall support per floor edge; one
principal run and valid owning solid; the floor as the sole cap at one end and no cap at the mouth;
a completely empty section through the run and exterior mouth slab; and material immediately
behind the floor.

The exact floor-adjacent walls are defining evidence. Those walls and the floor are constituent
evidence. Faces from the intersecting side opening are not absorbed. Curved, multiply wired,
breached or four-sided floors, missing or duplicate supports, inconsistent or tapered walls,
through/enclosed topology and ambiguous ownership fail closed. Four-sided recovery is deliberately
left to `Pocket` and `RectangularBlindSlot`: after the mouth cycle is broken, the floor alone cannot
distinguish those more specific contracts.

The proof remains inside `prismatic_pockets`, before Candidate issuance. It publishes no traversal
API and reads no labels, sibling Candidates, reconciliation outcome or completed evidence. ADRs
0007 and 0010 record this narrow extension. Authored tests cover exact evidence, a deeper-opening
positive, four-sided and breached-floor refusals, covariance, compound ownership, scale and STEP
round trip; the existing suite retains sharp, treated-mouth, through, enclosed and reconciliation
boundaries.

## Full MFCAD++ development evidence

The paired runs use the published MFCAD++ test split, lexical first 2,500 unique model IDs, raw
recognition, Python 3.12.14, build123d 0.11.1, OCP 7.9.3.1, taxonomy v10 SHA-256
`838c4daeb7c3a44f50dd8790d0dff526ff31747d3824d0a4438ed0cc4f2f2176`, and selection SHA-256
`ad92768788d88e3c4e3866bc2a614e7a345fea7fc52463dfc9f0b9b9e850058e`. Parent `24914d5` and
floor-seeded source commit `a492231` each evaluate 2,493 models, retain the same seven known invalid
inputs and return no empty aggregate result.

| Measure | Parent `24914d5` | Floor seeded `a492231` | Change |
| --- | ---: | ---: | ---: |
| accepted physical Prismatic Pockets | 1,659 | 1,671 | +12 |
| class-13 mapped records | 831 | 833 | +2 |
| class-15 mapped records | 697 | 707 | +10 |
| triangular defining recall | 2,493 / 3,892 (0.6405) | 2,499 / 3,892 (0.6421) | +6 faces |
| triangular constituent coverage | 3,408 / 3,892 (0.8756) | 3,412 / 3,892 (0.8767) | +4 faces |
| six-sided defining recall | 4,182 / 5,707 (0.7328) | 4,242 / 5,707 (0.7433) | +60 faces |
| six-sided constituent coverage | 4,961 / 5,707 (0.8693) | 5,022 / 5,707 (0.8800) | +61 faces |
| rectangular constituent coverage | 4,503 / 4,895 (0.9199) | 4,503 / 4,895 (0.9199) | 0 |
| taxonomy-mismatched defining faces | 15,506 | 15,506 | 0 |
| all-family unmapped records | 14,669 | 14,669 | 0 |

Exactly twelve model rows change after excluding runtime. Each gains one accepted physical
Prismatic Pocket and maps uniquely to the intended class: two triangular and ten six-sided. Every
other physical-family count and every reconciliation-disposition count is identical. No class
loses face coverage. The mapped-family precision denominators for classes 13–15 each include all
66 newly claimed PrismaticPocket walls by scorer design; that shared denominator is not a claim
that every occurrence belongs to all three mutually exclusive corpus labels.

Machine evidence:
[`effectiveness-mfcadpp-2500-floor-seed-a492231.json`](effectiveness-mfcadpp-2500-floor-seed-a492231.json),
SHA-256 `4f8dcd5456be4a08c399067a5167d94c3ab55cfe14dc0e1d49f5eb8425bae524`.

## Residual audit

The residual audit builds each model's complete aggregate Candidate inventory before reading its
labels. Labels then select connected same-label component proxies and measure already-issued
evidence; they never author a proposal or geometry predicate. MFCAD++ has no native instance IDs,
so these are explicitly component proxies rather than instance recall.

| Class | Parent missing | Floor-seeded missing | Change | Untouched change | Complete change |
| --- | ---: | ---: | ---: | ---: | ---: |
| triangular pocket (13) | 484 | 480 | -4 | 98 → 97 | 837 → 838 |
| rectangular pocket (14) | 392 | 392 | 0 | 19 → 19 | 804 → 804 |
| six-sided pocket (15) | 746 | 685 | -61 | 87 → 80 | 702 → 708 |

The exact-topology cap refinement leaves every `not_single_cap` residual unchanged. This matters:
an earlier exploratory version accepted zero-thickness closing faces when volume beyond them
looked exterior. Requiring the selected floor to be the sole topological cap removed those cases.
A subsequent all-family comparison exposed two accepted four-sided records that were geometrically
ambiguous with rectangular blind slots; excluding four-sided floors removed both, restored the
unmapped and mismatch totals exactly, and cost only three tentative rectangular coverage faces.

Residual evidence:
[`mfcadpp-polygonal-pocket-residuals-parent-24914d5.json`](mfcadpp-polygonal-pocket-residuals-parent-24914d5.json),
SHA-256 `249e3d3fa46c5b114d804f3f99b90d1e90294cecf24fdaced970d26660ea3f76`, and
[`mfcadpp-polygonal-pocket-residuals-a492231.json`](mfcadpp-polygonal-pocket-residuals-a492231.json),
SHA-256 `421a9759c1585775a9eaf442a4985a49438f2eca841b3808c6e0d495a315b48b`.

MFInstSeg is not rerun or inspected for this increment. It remains the pseudo-blind aggregate
transfer corpus.

## Reproduction

```console
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version \
  'MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823' \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v10.json \
  --limit 2500 --workers 4 --allow-invalid \
  --output docs/benchmarks/effectiveness-mfcadpp-2500-floor-seed-a492231.json

uv run python tools/audit_mfcadpp_polygonal_pocket_residuals.py \
  /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --limit 2500 --workers 4 --allow-invalid \
  --output docs/benchmarks/mfcadpp-polygonal-pocket-residuals-a492231.json
```

## Remaining Pocket work

This closes a bounded intact-floor subset, not general cavity propagation. The remaining
polygonal residual is 1,557 faces: 1,305 are in components whose direct ring probe first fails at
`not_simple_cycle`. Rectangular work remains a separate membership problem, while split floors,
curved interruptions, shared cavities and cases without one exact floor wire need independent
geometric contracts rather than a wider version of this rule.
