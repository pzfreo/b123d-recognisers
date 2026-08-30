# E2 ordinary framed provider contract

This validates the provider portion of Epic 0005 issue #317 at implementation commit
`a404823`. It changes public lifecycle naming and guidance, not recognition predicates or record
schemas.

## Contract result

- `build_framed_recognition_result()` is the ordinary documented aggregate route.
- `build_framed_recognition_report()` pairs the same inferred frame and exact local working shape
  with one bounded report produced by one aggregate run.
- prepared result and report calls reuse the one local cylinder substrate after caller-owned
  classification.
- `build_raw_recognition_result()` and `build_raw_recognition_report()` explicitly retain
  caller/world coordinates. Their historical ambiguous names remain raw aliases through 0.4.x and
  are removed in 0.5.0 rather than silently changing type.
- `NO_MATERIAL`, `NO_ANALYTIC_DIRECTION`, and `NONFINITE_GEOMETRY` remain typed refusals. No framed
  route falls back to raw recognition.

ADRs 0011 and 0012 record the authority, compatibility window, and paired-report decision. ADRs
0001, 0002, 0003, 0004, 0005, 0007, and 0008 were checked before implementation and against the
final provider diff. No record schema, topology-evidence ownership, frame inference, tolerance,
family predicate, registry, or reconciliation rule changed.

## MFCAD++ evidence

The checked-in [taxonomy-v2 report](effectiveness-mfcadpp-500-e2-framed-provider-a404823.json) has
SHA-256 `eb21c3e50d00ba6a24a7566b7020d916305171b878ac7a03550fab4bd050e0dd`.
It uses the published MFCAD++ test split, lexical first 500 unique model IDs, framed recognition,
and selection hash `323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`.

- 500 selected, loaded, and evaluated; zero invalid, refused, or empty models.
- Every per-model occurrence, family count, defining-face score, taxonomy mismatch, diagnostic,
  and reconciliation disposition is identical to the prior framed report at `10fa5f6` after
  removing timing and package/environment metadata.
- Physical records remain: 1,408 Face Levels, 737 Risers, 580 Holes, 547 Pockets, 319 Prismatic
  Pockets, 282 Passages, 234 Plates, 199 Bosses, 154 Slots, and the unchanged remaining families.
- Taxonomy-mismatch defining faces remain 1,133. Plate class 21 remains precision 234/234 and
  recall 234/354.

The implementation report's total was 348.669 seconds. A fresh [parent
report](effectiveness-mfcadpp-500-e2-framed-provider-parent-87e583a.json) at `87e583a` has SHA-256
`03942296894443ae50248b5748b9e865eca4183e0f6139cb193074c1c5af60df` and total 314.541 seconds:
the sequential current/parent ratio is 1.1085. Both reports have exact non-timing parity. The API
change adds no per-model geometry work—the framed result route replaces one compatibility wrapper
call with its explicit raw equivalent—so this 10.85% sequential difference is retained as observed
environment/runtime variance, not claimed as measured implementation cost. It remains within the
range of prior E2 whole-corpus runs, but the Draftwright consumer validation must still measure its
own end-to-end drawing path.

## Validation and review

- focused frame, explanation, prose, architecture, and package suite: 66 passed on the initial
  diff; final refusal/package subset: 34 passed;
- local fast lane: 2,342 passed;
- Ruff, mypy, sdist and wheel build: clean;
- installed wheel exercises framed report success, explicit raw success, and typed empty-part
  refusal;
- one bounded independent contract/ADR review found the empty-shape dereference before the
  `NO_MATERIAL` guard; `a404823` fixed it, the review reran 49 focused tests, and the exact final
  diff is clean.

MFInstSeg was not inspected for this provider-only child. Issue #293 remains the explicit transfer
gate, and no substitute transfer claim is made here. Draftwright migration and its drawing outcome
remain the separately reviewable consumer portion of #317.

## Reproduction

```bash
uv run pytest -n 2 -m "not slow" -q
uv run pytest -q tests/test_experimental_frame.py tests/test_recognition_explanations.py \
  tests/test_published_prose.py tests/test_architecture.py tests/test_package.py
uv run mypy tests/typing/public_consumer.py
uv build
uv run python tools/run_effectiveness_baseline.py mfcadpp \
  /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version "MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823" \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v2.json \
  --limit 500 --recognition-frame framed --output REPORT.json
```
