# MFCAD++-500 class-0 Countersink mapping decision

## Decision

MFCAD++/MFInstSeg class 0, `Chamfer`, maps to both `chamfers` and
`countersinks` in immutable effectiveness taxonomy v8. Do not add
`prismatic-pockets`.

This is a comparison decision only. It changes no recogniser, evidence ownership,
reconciliation, public record, or aggregate output.

## Geometry justification

The exact MFCAD++-500 class-0 audit at shipped main `1432138` covers all 214
labelled faces in 180 shared-edge label-component proxies across 136 models.

Chamfer evidence covers 61 faces and touches 58 components, fully covering 54.
Countersink evidence covers eight conical faces in six components:

- models `10260`, `10812`, and `12729` contain singleton conical label components
  fully and exclusively owned by accepted Countersink records;
- models `11145` and `11186` contain four-face smooth conical bevel groups partitioned
  into two valid Chamfers and two valid Countersinks;
- model `1201` contains a three-face group partitioned into two Chamfers and one
  Countersink.

The public families intentionally remain narrower: Chamfer excludes internal cones,
while Countersink proves a conical hole-mouth seat from its major rim, bore rim and
included angle. The dataset's broader `Chamfer` label covers both external bevels and
these internal conical bevels. Mapping both families records that vocabulary relation
without weakening either production contract.

PrismaticPocket evidence is different. It touches nine separate singleton planar
label components and never overlaps accepted Chamfer or Countersink evidence. Eight
are non-principal slanted faces and one is principal. Each is only one defining wall
within an accepted complete floored pocket; the public PrismaticPocket record owns a
constant planar cross-section and floor, not a bevel occurrence. Mapping the entire
pocket family from these isolated labels would make unrelated pocket faces eligible
for class 0 and mistake single-assignment face labelling for physical-feature
equivalence. The proposal is therefore rejected.

## Exact comparison

Both reports use the fixed lexical first-500 selection, selection SHA-256
`323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`, and the
published test split identified by DOI
`10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823`.

| Class-0 measure | taxonomy v7 (`chamfers`) | taxonomy v8 (+ `countersinks`) |
| --- | ---: | ---: |
| Defining-face recall | 61/214 (28.50%) | 69/214 (32.24%) |
| Defining-face precision | 61/87 (70.11%) | 69/95 (72.63%) |
| Exact all-family face coverage | 91/214 (42.52%) | 91/214 (42.52%) |
| Mapped records | 61 | 69 |
| Corpus taxonomy-mismatch defining faces | 3,203 | 3,195 |

All 500 normalized production rows are exactly equal between the v7 report at
`b277522` and the v8 report at `80d6f51`; every non-class-0 model and summary class
row is also equal. Physical family counts, dispositions, diagnostics, source hashes,
empty-result state and accepted records did not move. The v8 run evaluated 500/500
models with no invalid or empty models in 324.749 seconds (median 0.615 seconds,
p95 1.158 seconds). This is runtime metadata rather than a paired performance claim,
because the taxonomy is not executed during recognition.

## Artifacts and reproduction

- `mfcadpp-class0-chamfer-counter-pocket-audit-1432138.json`: complete per-component
  and per-family audit;
- `effectiveness-taxonomy-v8.json`: immutable mapping;
- `effectiveness-mfcadpp-500-class0-countersink-80d6f51.json`: canonical exact report.

Reproduce at the artifact commits (`1432138` for the audit and `80d6f51` for the
effectiveness report):

```console
python tools/audit_mfcadpp_component_overlap.py \
  /path/to/MFCAD++_dataset/step/test \
  --class-id 0 --mapped-family chamfers \
  --compare-family chamfers --compare-family countersinks \
  --compare-family prismatic_pockets --limit 500 \
  --output docs/benchmarks/mfcadpp-class0-chamfer-counter-pocket-audit-1432138.json

python tools/run_effectiveness_baseline.py \
  mfcadpp /path/to/MFCAD++_dataset/step/test \
  --dataset-version "MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823" \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v8.json --limit 500 \
  --output docs/benchmarks/effectiveness-mfcadpp-500-class0-countersink-80d6f51.json
```

## Transfer and architecture

The aggregate-only MFInstSeg summary directionally reports the same contested class,
but its corpus mount is unavailable and no individual model was inspected. A canonical
v8 transfer rerun remains an E0/E6 milestone item.

The decision conforms to ADRs 0002, 0003, 0004, 0005, and 0007: deterministic family
contracts and output are unchanged; discovery and reconciliation remain separate;
evidence roles stay explicit; stable family identifiers are reused; and no module seam
changes. Final-diff conformance and one independent exact-head review remain required
before merge.
