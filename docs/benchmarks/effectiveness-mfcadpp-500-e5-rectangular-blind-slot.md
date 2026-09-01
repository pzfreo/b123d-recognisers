# E5 rectangular blind-slot effectiveness

Canonical reports:

- [`effectiveness-mfcadpp-500-rectangular-blind-c6381c6.json`](effectiveness-mfcadpp-500-rectangular-blind-c6381c6.json)
- [`rectangular-blind-slot-component-audit-c6381c6.json`](rectangular-blind-slot-component-audit-c6381c6.json)
- [`rectangular-blind-slot-performance-census-c6381c6.json`](rectangular-blind-slot-performance-census-c6381c6.json)

## Contract and scope

Commit `c6381c6f163e656594a9819af6dea466320efc85` adds the principal-axis,
edge-open rectangular blind-slot family. A valid occurrence has one rectangular planar cap, two
opposed planar sides, one planar floor, complete concave section relations, a run mouth and depth
opening on the owning solid's envelope, and an exactly empty cap extrusion to the run mouth. Its
run is at least its section width and distinctly longer than its depth so role assignment does not
depend on axis or traversal order.

Enclosed pockets, through or doubly open channels, short notches, curved or non-principal sections,
cross-solid evidence, material bridges, invalid/open solids and competing role interpretations
fail closed. Coplanar split caps retain all original-face evidence. Pocket reconciliation removes
only a candidate whose complete constituent evidence is a subset of the accepted slot's complete
defining evidence.

The authored contract covers X/Y/Z rotations, both opening and depth signs, translation, 0.001 and
1000 scale factors, framed recognition, STEP round-trip, split faces, compound order and ownership,
material obstruction, invalid input, tolerance boundaries, role ties, direct/aggregate parity and
reconciliation controls.

## MFCAD++-500 result

The fixed selection is the first 500 unique test-split model IDs in lexical order. All 500 were
loaded and evaluated, with zero invalid or empty models. Its selected-ID SHA-256 is
`323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`; taxonomy v6 SHA-256 is
`aceb550388ef6965e460957e8b447ff5531ba827c1d038471d66c10ed8b9c92d`.

For class 17, Rectangular blind slot:

| Measure | Result |
| --- | ---: |
| Defining-face recall | 84/178 (47.19%) |
| Defining-face precision | 84/92 (91.30%) |
| Exact face coverage, all families | 134/178 (75.28%) |
| Mapped same-label component proxies fully covered | 21/43 |
| Mapped physical records | 21 |
| Emitted rectangular-blind-slot records | 23 |

MFCAD++ does not publish native feature-instance relations, so the 43 components are explicitly a
shared-edge, same-label proxy rather than native instance recall. The new family fully covers and
touches 21 of them. Across all families, constituent evidence touches 42/43 and fully covers 25/43.
Three additional apparent components have interrupted side or floor boundaries, so accepting them
would overstate the complete rectangular U-section contract; they remain intentional misses.

Two emitted records have all four defining faces labelled class 22, Rectangular blind step. The
same geometry satisfies the package's edge-open one-cap U-section contract, so this is disclosed as
a taxonomy disagreement rather than hidden with a corpus-specific exception. It accounts for the
8 non-class-17 defining faces in the precision denominator. Reconciliation removes 8 prior
Pocket fragments with the new named reason. Every other existing physical-family count is
unchanged; the resulting class 14/16/18 precision-denominator changes come only from those removed
Pocket claims. Class-22 defining recall moves from 449/607 to 444/607 while exact face coverage
moves from 510/607 to 511/607, making the disagreement visible rather than claiming a universal
improvement.

## Runtime and regression boundary

The paired 13-part NIST/Gramel census alternates enabled/disabled order. The enabled total is
254.64 seconds versus 250.82 seconds disabled, a ratio of 1.015 against the 1.10 gate; paired median
delta is -0.017 seconds. The corpus contains no accepted occurrence, which is useful false-positive
evidence rather than recall evidence. Every non-target aggregate output is identical and every
Pocket delta is explained by the named reconciliation reason.

Focused family, aggregate, inventory, registry, golden and architecture checks pass 99/99. Ruff,
mypy and `git diff --check` pass. Applicable ADRs 0003, 0004, 0008 and 0011 were reviewed before
implementation and against the frozen diff: discovery remains order-independent; evidence is
complete and run-local; reconciliation is explicit; records are serializable geometric values;
ownership is body-local; numerical floors are feature-relative; and the principal-axis contract is
covered through the explicit framed route.

## Reproduction

```console
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version \
  'MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823' \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v6.json \
  --limit 500 \
  --output docs/benchmarks/effectiveness-mfcadpp-500-rectangular-blind-c6381c6.json

uv run python tools/audit_mfcadpp_component_overlap.py \
  /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --class-id 17 --mapped-family rectangular_blind_slots --limit 500 \
  --output docs/benchmarks/rectangular-blind-slot-component-audit-c6381c6.json

uv run python tools/benchmark_rectangular_blind_slots.py census \
  --output docs/benchmarks/rectangular-blind-slot-performance-census-c6381c6.json
```
