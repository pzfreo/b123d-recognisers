# E1 bounded-explanation validation

This projection-only validation covers issue
[#295](https://github.com/pzfreo/b123d-recognisers/issues/295) at implementation commit
`29d287b33f188a16a1b60165b389ecff4b22f397`. It compares against the immutable E0
[`MFCAD++ baseline`](effectiveness-mfcadpp-500-0.5.0.md) without replacing that historical report.

## Corpus comparison

The exact E0 command was rerun with a new output path:

```bash
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version \
  'MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823' \
  --limit 500 \
  --output /tmp/b123d-e1-igyBJO/effectiveness.json
```

Provenance:

- E0 report SHA-256: `e648d1887ba0dab513adc2048e3fc54c3c3376a3675a238958e3af12c7ee0971`
- E1 rerun SHA-256: `52facefbed57941e88780ab2e7be34dc1de9403be5d30a36e50ed27e1ec1287c`
- deterministic selection SHA-256:
  `323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`
- 500 selected, loaded and evaluated; zero invalid models.

The comparison asserted exact equality for dataset, selection and taxonomy metadata, the complete
summary/score vector, and every per-model field except measured seconds. This includes physical
records, mapped classes, defining-face counts, taxonomy mismatches, reconciliation drops,
predicate observations, residual diagnostics, source hashes and status. All fields matched.

The rerun's descriptive recognition runtime was 203.753 s total, 0.377 s median and 0.707 s p95
per model. Runtime is host-load evidence rather than a semantic equality field.

The full E1 report is not checked in because it duplicates the existing 3.2 MB per-model artifact
apart from commit and timing. The command, commits, hashes and comparison scope above allow another
agent to reproduce the proof; E0 remains the immutable baseline.

## Explanation projection cost

Projection was measured over one already-completed reconciliation-heavy U-passage product. Five
rounds each built 10,000 reports from the same frozen product. The per-round times were 4.487,
4.794, 4.242, 4.704 and 6.304 seconds: minimum 424 microseconds and median 470 microseconds per
report. Each projected report retained the exact existing `RecognitionResult` object.

This isolates the additive projection cost from recognition. `build_recognition_report()` still
runs recognition once; callers of `build_recognition_result()` pay no new projection work.
