# E0 O-ring decomposition audit

Issue [#360](https://github.com/pzfreo/b123d-recognisers/issues/360) audits the historical mapping
from MFCAD++/MFInstSeg class 11, `O-ring`, to the package `Boss` family. The result is a
many-to-many evidence correction, not a production change or a new recognition family.

## Geometric contract

The corpus assigns one feature label to an external cylindrical wall, an annular planar face and
an internal cylindrical wall. The package deliberately decomposes that geometry: `BossRecord`
owns the external cylinder and `HoleRecord` owns the internal cylinder. The annular plane is
consulted context for those recognisers but is not a defining face owned by either record. Mapping
only `bosses` therefore hid legitimate Hole evidence; mapping the plane would instead invent
ownership that the package does not claim.

This decomposition follows ADR 0005's stable-family boundary: no public family, record schema,
manifest entry, aggregate field or downstream contract changes. It changes only how the external
single-label taxonomy is compared with two existing physical families.

## Complete lexical-500 audit

The published test archive's exact lexical selection contains 147 models / 669 class-11 faces.
There are 453 cylindrical and 216 planar labelled faces in 207 exact label-connected components:

| labelled component geometry | count |
| --- | ---: |
| Two cylinders and one plane | 173 |
| Three cylinders and one plane | 16 |
| One cylinder and one plane | 6 |
| One cylinder only | 4 |
| Five cylinders and two planes | 2 |
| Four cylinders and one plane | 2 |
| Other intersected variants | 4 |

The aggregate recogniser claims 211 class-11 faces as Boss evidence and 230 as Hole evidence. It
also claims 21 as structural FaceLevel evidence, one as Fillet evidence and one as Plate evidence;
those structural/incidental claims are not added to the physical taxonomy mapping. In total, 464
distinct class-11 faces have some package claim and 205 are unclaimed. MFCAD++ does not provide an
instance relation, so component counts are descriptive topology evidence rather than instance
recall. No individual MFInstSeg geometry was inspected.

## Immutable taxonomy result

[`effectiveness-taxonomy-v5.json`](effectiveness-taxonomy-v5.json), SHA-256
`7eb11e73ef8bd4b754d04339a1d2a71f387b66eab8a8f2a6ad3caf0c8e43b84b`, differs from v4 only by
mapping class 11 to both `bosses` and `holes` and documenting that decomposition. Earlier mappings
and reports remain immutable.

The exact v5 report is
[`effectiveness-mfcadpp-500-oring-ec8b003.json`](effectiveness-mfcadpp-500-oring-ec8b003.json),
SHA-256 `2fa220a8e63f425e9a9aefaf2a5fd6d3f301340c9c98443837f681573f481dc5`, generated at commit
`ec8b003` using:

```bash
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version published-test-split \
  --limit 500 \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v5.json \
  --output docs/benchmarks/effectiveness-mfcadpp-500-oring-ec8b003.json
```

Compared with the exact v4 report:

- all physical records, predicate observations, reconciliation drops, unsupported diagnostics,
  source hashes and non-mapping, non-runtime per-model evidence are exactly equal;
- class-11 defining-face agreement changes from Boss-only 211/211 precision and 211/669 recall to
  the combined decomposition's 441/854 precision and 441/669 recall;
- mapped class-11 physical records increase from 199 to 400 and total taxonomy mismatches fall
  from 3,237 to 3,007 because 230 legitimate Hole defining faces are now mapped;
- total runtime is 232.551 seconds versus 251.121 seconds (ratio 0.9261), descriptive only because
  production behavior is unchanged.

The lower combined precision is expected: its denominator now includes every Hole claim in models
whose single corpus class is O-ring, including Hole faces carrying another label. It must not be
read as a production precision regression. MFInstSeg inherits the same 25-class mapping and must be
regenerated from canonical model rows before its O-ring metrics are restated.
