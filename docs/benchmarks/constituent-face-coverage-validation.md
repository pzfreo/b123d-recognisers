# Constituent face-coverage validation

Issue [#368](https://github.com/pzfreo/b123d-recognisers/issues/368) changes face coverage from
accepted defining evidence to exact accepted constituent evidence. Defining evidence keeps its
existing semantics and remains the sole input to recognition claims, reconciliation and the
defining-face metrics. This report therefore measures downstream evidence visibility, not a
recognition or accuracy improvement.

## Exact MFCAD++-500 result

The immutable taxonomy-v4 report is
[`effectiveness-mfcadpp-500-constituent-5bc9242.json`](effectiveness-mfcadpp-500-constituent-5bc9242.json),
SHA-256 `4177dccbcbfec5bee999eb0cfab96a7d7bf2275599fd6a532e22d9e0082e5c13`, generated at
scorer commit `5bc9242` using:

```bash
PYTHONPATH=src .venv/bin/python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version published-test-split \
  --limit 500 \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v4.json \
  --output docs/benchmarks/effectiveness-mfcadpp-500-constituent-5bc9242.json
```

All 500 selected models loaded and evaluated; none was invalid or returned no physical records.
Across supported and partial classes, exact accepted constituent evidence covers 7,957/11,244
labelled faces (70.77%), compared with 7,212/11,244 (64.14%) under the format-2 defining-evidence
metric: **745 additional faces, or 6.63 percentage points**. Across every taxonomy status it covers
8,713/15,170 (57.44%), compared with 7,791/15,170 (51.36%): **922 additional faces, or 6.08
percentage points**.

The supported/partial comparison is:

| Class | Constituent coverage | Previous defining coverage | Defining-face recall |
| ---: | ---: | ---: | ---: |
| 0 | 91/214 | 90/214 | 61/214 |
| 1 | 236/239 | 235/239 | 234/239 |
| 2 | 363/668 | 362/668 | 288/668 |
| 3 | 658/912 | 642/912 | 397/912 |
| 4 | 662/1,336 | 662/1,336 | 575/1,336 |
| 6 | 199/237 | 169/237 | 31/237 |
| 8 | 346/415 | 341/415 | 184/415 |
| 9 | 376/592 | 376/592 | 138/592 |
| 11 | 643/669 | 464/669 | 211/669 |
| 12 | 352/363 | 207/363 | 177/363 |
| 13 | 515/732 | 515/732 | 489/732 |
| 14 | 659/907 | 548/907 | 404/907 |
| 15 | 860/1,133 | 859/1,133 | 828/1,133 |
| 16 | 664/973 | 535/973 | 423/973 |
| 17 | 89/178 | 81/178 | 31/178 |
| 18 | 95/213 | 76/213 | 47/213 |
| 19 | 9/90 | 9/90 | 0/90 |
| 20 | 332/411 | 242/411 | 136/411 |
| 21 | 298/354 | 296/354 | 236/354 |
| 22 | 510/607 | 503/607 | 449/607 |
| 23 | 0/1 | 0/1 | 0/1 |

After removing format version, commit and runtime metadata, per-model timing, and coverage fields,
the canonical format-3 report is exactly equal to the preceding
[`f4881f8` format-2 report](effectiveness-mfcadpp-500-face-coverage-f4881f8.json). Thus all 500 model
rows, physical and mapped records, defining precision and recall, reconciliation drops,
diagnostics, observations, taxonomy mismatches, source hashes and selection provenance are
unchanged. The defining aggregates remain 5,339 matched faces and 18,705 mapped defining faces.

## Architecture and performance

ADR 0010 was reviewed before implementation and against the final production diffs. Constituent
membership retains identities already selected by each accepted geometry proof, defining is a
subset, omission defaults exactly to defining, and reconciliation never reads the wider set. No
coordinate matching, adjacency expansion, corpus-label inference or second recognition pass was
introduced.

The complete constituent stack measured 216.649 seconds minimum and 226.471 seconds median over
three census iterations. An unchanged-main calibration on the same host measured 221.370 seconds
for one iteration. Both exceed the historical 109.651-second absolute ceiling because this host is
currently about twice as slow; the side-by-side result shows no attributable constituent-evidence
regression, but is not represented as an absolute-budget pass.

MFInstSeg was not available at the documented workspace paths when this report was generated. The
required transfer milestone remains open and must use the same format-3 scorer without inspecting
individual MFInstSeg models or feeding model-specific feedback into implementation.
