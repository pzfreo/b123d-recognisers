# E0 circular through-slot scope audit

Issue [#356](https://github.com/pzfreo/b123d-recognisers/issues/356) audits the dataset mapping
that historically treated MFCAD++ class 7, `Circular through slot`, as the package's `Slot`
family. This is a scope correction, not a recognition improvement: production geometry and every
accepted physical record are unchanged.

## Geometric contract

The shipped `Slot` is an enclosed through recess established by two opposed parallel walls. Its
record carries their separation, long span, through span and principal axes. Sharp and obround
ends may close the long span, but the two wall faces remain the defining size evidence.

MFCAD++ class 7 instead denotes a semicylindrical groove. That geometry has a radius and cylinder
axis, but no opposed planar walls and no value the current `Slot.width` could represent honestly.
Mapping it to `Slot` therefore made unsupported geometry look like a zero-recall defect. Adding a
circular-groove record would be a separate, consumer-backed vocabulary decision.

## Complete lexical-500 audit

The audit used the same published test archive and exact lexical selection as the paired Slot
precision report:

- 500 models selected and loaded; 0 invalid and 0 empty;
- selected-ID SHA-256
  `323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`;
- 47 models contain class 7, with 78 labelled faces;
- 70 faces are native cylinders and 8 are planes;
- every cylindrical face has an exact trimmed angular span of π (70/70);
- the eight planar fragments occur in models `10908`, `11512`, `11905`, and `12794`; each is
  topologically joined to class-7 cylindrical material created by intersecting operations rather
  than forming a two-opposed-wall Slot occurrence.

The audit deliberately inspected MFCAD++ geometry, which is open development evidence. No
individual MFInstSeg geometry was inspected.

## Immutable taxonomy result

[`effectiveness-taxonomy-v3.json`](effectiveness-taxonomy-v3.json), SHA-256
`e8945b09e2ccc3188cc91e333fe4033a9441bbae92320e477bcf38b1f041baba`, differs from v2 only at
class 7: its family list becomes empty and its status becomes `unsupported`. Versions 1 and 2
remain immutable for their historical reports. MFInstSeg inherits the same 25-class vocabulary,
so a future canonical MFInstSeg rerun must use v3; rounded prose from the earlier external summary
is not sufficient to reconstruct corrected numerators or denominators.

The exact v3 report is
[`effectiveness-mfcadpp-500-class7-scope-a8b5cdf.json`](effectiveness-mfcadpp-500-class7-scope-a8b5cdf.json),
SHA-256 `ccf37ed039e9ee4c603c1a82831161419990a720e23066da3001368d35e91ff0`.
It was produced with:

```bash
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version published-test-split \
  --limit 500 \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v3.json \
  --output docs/benchmarks/effectiveness-mfcadpp-500-class7-scope-a8b5cdf.json
```

Compared with the v2 Slot-closure report at `1ced915`:

- all physical-family record counts, predicate observations, reconciliation drops, unsupported
  diagnostics, source hashes and non-mapping per-model fields are exactly equal;
- `Slot` remains 45 accepted records, and rectangular class-6 precision remains 31/88 (35.23%)
  with recall 31/237 (13.08%);
- class 7 changes from incorrectly supported 0/88 precision and 0/78 recall to unsupported;
- taxonomy-mismatch defining occurrences fall 3,243→3,237 because six class-7 fragments are no
  longer treated as supported false ownership; this is a denominator classification, not a new
  correct claim;
- total runtime is 256.000 seconds versus 263.495 seconds (ratio 0.9716), descriptive only because
  no production path changed.

The comparison proves the correction changes only mapping-dependent interpretation. It does not
claim that circular grooves are recognised, improve the reported rectangular Slot result, or
close the separate free-axis rectangular Slot contract in issue #310.
