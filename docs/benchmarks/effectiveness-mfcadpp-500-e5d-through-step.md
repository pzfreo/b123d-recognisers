# MFCAD++ E5d: interruption-tolerant Through Steps

Canonical result:
[`effectiveness-mfcadpp-500-e5d-e1e7e22.json`](effectiveness-mfcadpp-500-e5d-e1e7e22.json).
Metric definitions and corpus policy are in the
[`effectiveness baseline method`](effectiveness-baseline-method.md).

## Provenance

- Production and benchmark commit: `e1e7e22aa3ea1faf3c3d6dc70a986317276ba959`
- Comparison report: `effectiveness-mfcadpp-500-e5b-5248ef0.json`
- Audit: [`through-step miss anatomy`](through-step-miss-audit-mfcadpp-500.md)
- Corpus: MFCAD++ published test split; DOI
  `10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823`
- Selection: first 500 unique STEP IDs in lexical order
- Selection hash: `323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`
- Result: 500 selected, loaded and evaluated; zero invalid or empty models

## Effectiveness result

The widened family returns 92 Through Step occurrences. All 184 defining original faces carry
MFCAD++ class 8: defining-face precision is 184/184 (100%), and defining-face recall is 184/415
(44.34%). This is exactly the upper bound projected by the E5c miss audit: 53 additional
occurrences and 106 additional faces, with no projection error.

MFCAD++ supplies no native instance denominator. The explicitly non-native shared-edge same-class
proxy moves from 39/181 (21.55%) to 92/181 (50.83%) across the same 144 class-8 models. Its artifact
is
[`through-step-components-mfcadpp-500-e1e7e22.json`](through-step-components-mfcadpp-500-e1e7e22.json).

After removing only ThroughStep and mapped class-8 fields, the complete summary and all 500
per-model outputs are equal to E5b. Every pre-existing physical-family count, mapped-class metric,
reconciliation drop, predicate observation, unsupported diagnostic, empty-result state and
taxonomy-mismatch count is unchanged.

## Geometric contract

The implementation still requires two orthogonal principal planar regions, one complete straight
concave run seam, both source-solid run ends, two convex common terminals, envelope-reaching legs,
no third co-spanning concave wall, an exactly empty inferred prism and one valid source solid.

It no longer requires both wall boundaries to be pristine hole-free four-run rectangles. Inner
wires, convex straight notches, curved hole intersections and coplanar splits are allowed only when
they leave every proof above intact. An interruption crossing the seam, a material rib, a missing
terminal, a capped run, a tapered/non-principal defining wall, an ambiguous third wall, an open
shell or a cross-solid composite still fails closed. No new tolerance or dataset-specific rule was
introduced.

## Runtime result

The isolated paired MFCAD++-500 sentinel finds all 92 Through Steps and preserves every
pre-existing output. Enabled time is 239.584 seconds versus 230.409 disabled: ratio 1.0398, with a
paired median delta of 0.0160 seconds.

The complete 13-part NIST/Gramel census finds no Through Steps and preserves every pre-existing
output. Enabled time is 186.558 seconds versus 182.299 disabled: ratio 1.0234, with a paired median
delta of 0.0137 seconds. Both workloads remain below the 1.10 gate.

Detailed artifacts:

- [`MFCAD++ paired performance`](through-step-performance-mfcadpp-500-e1e7e22.json)
- [`NIST/Gramel paired performance`](through-step-performance-census-e1e7e22.json)

## Reproduction

```console
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version \
  'MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823' \
  --limit 500 \
  --output docs/benchmarks/effectiveness-mfcadpp-500-e5d-e1e7e22.json

uv run python tools/derive_mfcadpp_components.py \
  /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --class-id 8 --limit 500 \
  --output docs/benchmarks/through-step-components-mfcadpp-500-e1e7e22.json

uv run python tools/benchmark_through_steps.py mfcadpp \
  --root /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --limit 500 \
  --output docs/benchmarks/through-step-performance-mfcadpp-500-e1e7e22.json

uv run python tools/benchmark_through_steps.py census \
  --output docs/benchmarks/through-step-performance-census-e1e7e22.json
```

## Transfer and architecture

MFInstSeg was not inspected or used for development. The user supplied
`/app/workspaces/datasets/mfinstseg` as the intended aggregate transfer-baseline mount, but that
path and any MFInstSeg-like path under `/app` were absent in this runtime. The unmet E0 baseline
gate is recorded on #293; no substitute corpus was used.

ADRs 0001, 0002, 0003, 0004, 0007, 0008 and 0011 were reviewed before implementation. The final
diff changes only the existing family-private planar-region eligibility and its authored contract.
The registry remains the sole orchestrator; original graph-owned defining regions remain the only
evidence; atomic batch validation remains unchanged; the neutral exact-prism authority and all
existing tolerance/frame policies are reused; and no public record or signature changes.
