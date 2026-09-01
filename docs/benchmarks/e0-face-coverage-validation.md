# E0 face-coverage validation

Issue [#367](https://github.com/pzfreo/b123d-recognisers/issues/367) adds face coverage to
effectiveness report format version 2. The metric counts class-labelled faces present in the
defining evidence of any accepted candidate, irrespective of the family to which that candidate
maps. It remains separate from defining-face precision and recall and does not change recognition,
ownership, reconciliation, or taxonomy policy.

## Exact MFCAD++-500 result

The exact taxonomy-v4 report is
[`effectiveness-mfcadpp-500-face-coverage-f4881f8.json`](effectiveness-mfcadpp-500-face-coverage-f4881f8.json),
SHA-256 `dc66a143715ebd2f3846eceba33dc74351d7ed80208ab7b69c7b98e96ba7f972`, generated at
implementation commit `f4881f8` using:

```bash
PYTHONPATH=src:. .venv/bin/python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version published-test-split \
  --limit 500 \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v4.json \
  --output docs/benchmarks/effectiveness-mfcadpp-500-face-coverage-f4881f8.json
```

The report validates against the version-2 schema. After removing format version, commit and
runtime metadata, per-model timing, and the newly introduced `covered_faces` and `face_coverage`
fields, its canonical JSON is exactly equal to the preceding
[`905ddef` report](effectiveness-mfcadpp-500-paired-terminal-905ddef.json). Thus 500/500 model
results, physical records, mapped records, defining precision and recall, reconciliation,
diagnostics, observations, mismatches, selection and source hashes are unchanged.

Across supported and partial classes, accepted defining evidence covers 7,212/11,244 labelled
faces (64.14%). Across all taxonomy statuses, including unsupported and incomparable labels, it
covers 7,791/15,170 (51.36%). These aggregates describe reach only; unsupported and incomparable
classes do not become recognition targets, and neither aggregate is an accuracy score.

The supported/partial per-class comparison is:

| Class | Face coverage | Defining-face recall |
| ---: | ---: | ---: |
| 0 | 90/214 (42.06%) | 61/214 |
| 1 | 235/239 (98.33%) | 234/239 |
| 2 | 362/668 (54.19%) | 288/668 |
| 3 | 642/912 (70.39%) | 397/912 |
| 4 | 662/1,336 (49.55%) | 575/1,336 |
| 6 | 169/237 (71.31%) | 31/237 |
| 8 | 341/415 (82.17%) | 184/415 |
| 9 | 376/592 (63.51%) | 138/592 |
| 11 | 464/669 (69.36%) | 211/669 |
| 12 | 207/363 (57.02%) | 177/363 |
| 13 | 515/732 (70.36%) | 489/732 |
| 14 | 548/907 (60.42%) | 404/907 |
| 15 | 859/1,133 (75.82%) | 828/1,133 |
| 16 | 535/973 (54.98%) | 423/973 |
| 17 | 81/178 (45.51%) | 31/178 |
| 18 | 76/213 (35.68%) | 47/213 |
| 19 | 9/90 (10.00%) | 0/90 |
| 20 | 242/411 (58.88%) | 136/411 |
| 21 | 296/354 (83.62%) | 236/354 |
| 22 | 503/607 (82.87%) | 449/607 |
| 23 | 0/1 (0.00%) | 0/1 |

The gap between coverage and mapped defining recall is a triage signal. It includes legitimate
cross-family evidence and structural evidence boundaries, so it must not be converted directly
into family ownership. Publishing constituent evidence is the separate architectural decision in
[#368](https://github.com/pzfreo/b123d-recognisers/issues/368).

## Contract checks

Focused tests prove structural-only accepted claims contribute to coverage, unclaimed labelled
faces do not, and zero denominators remain `null`. The fail-closed validator requires exactly the
25 taxonomy classes and the closed version-2 row shape, rejects booleans, negative counts and
unexpected fields, and enforces `matched <= covered <= labelled`, `matched <= mapped`, and
`recalled <= truth` even when summary arithmetic is internally self-consistent.

ADRs 0003 and 0004 were reviewed. The scorer consumes the completed accepted inventory once and
does not call recognisers, alter candidate ownership, or use corpus labels as recognition policy.
No production package code changed. MFInstSeg was not run for this scorer-only increment, and no
individual transfer model was inspected.
