# E5 round-bottom blind-slot validation

Issue [#382](https://github.com/pzfreo/b123d-recognisers/issues/382) adds one conservative physical
family for the edge-open blind-slot geometry labelled MFCAD++ class 19. It does not broaden the
rectangular `Pocket` record or recover the separate historical semicircular-bottom proposal, for
which the feasibility audit found no accepted occurrence.

## Geometric authority

`RoundBottomBlindSlot` describes one principal-axis, edge-open recess on one valid solid. Its
constant section is a flat floor tangent to two equal quarter-cylinder regions; the run has one
exact planar blind cap and one body-envelope mouth. Recognition requires the complete U-section,
the cap and mouth AAG context, an empty swept void, same-span sides and original-face ownership.

Through and doubly capped sections, rectangular and obround recesses, non-principal raw geometry,
perforated or interrupted profiles, material-filled sweeps and cross-solid composites are refused.
The only numerical equality gate uses a local length authority at relative `1e-7`, with authored
tests on both sides; it is not derived from the corpus.

The public record reports run axis/sign, oriented section axes, length, radius, flat width and
centre. Defining and constituent evidence are the same complete original-face set. Face and feature
references remain opaque, occurrence-preserving and valid only within the recognition run.

## Authored and integration evidence

Tests cover truthful dimensions and exact evidence; X/Y/Z directions and both signs; translation,
mirror, arbitrary rigid presentation through the framed aggregate, scales `0.001` and `1000`, and
STEP round trip. Cap, side and mouth subdivisions preserve one logical occurrence. Cap/floor holes,
boundary notches, through/doubly capped sections, rectangular/obround alternatives and material
interruptions refuse. Two equal compound occurrences and two slots on one body remain distinct,
and the aggregate introduces no overlapping `Slot`, `Pocket` or `Channel`.

The complete local suite at implementation commit `38f4359` passed 2,842 tests in 2,246.87 seconds.
The changed/new paths also pass Ruff, mypy, capability-manifest regeneration, golden inventory,
NURBS conversion and rigid-motion sweep checks.

## Exact MFCAD++-500 result

The canonical report is
[`effectiveness-mfcadpp-500-round-bottom-38f4359.json`](effectiveness-mfcadpp-500-round-bottom-38f4359.json),
SHA-256 `9876e1f8d6484b3cce31df06437eee1ff5e658cb7f635979e715d5535e86df4c`.
It uses implementation commit `38f4359`, the published MFCAD++ test split, lexical first 500 unique
IDs, raw recognition, taxonomy v5 SHA-256
`809c69e0725515c1ae9b3d429c9bd7eb3e15c9d1205bc598129139b00b1975d5` and selection SHA-256
`323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`.

| Measure | Pre-change `5bc9242`, taxonomy v4 | Enabled `38f4359`, taxonomy v5 |
| --- | ---: | ---: |
| Models evaluated / invalid / empty | 500 / 0 / 0 | 500 / 0 / 0 |
| Round-bottom blind-slot records | 0 | 18 |
| Class-19 mapped records | 0 | 18 |
| Class-19 matched / claimed defining faces | 0 / 1,363 | 72 / 72 |
| Class-19 defining precision | 0% | 100% |
| Class-19 matched / labelled defining faces | 0 / 90 | 72 / 90 |
| Class-19 defining recall | 0% | 80% |
| Class-19 covered / labelled faces | 9 / 90 | 75 / 90 |
| Class-19 exact face coverage | 10% | 83.33% |
| Supported/partial exact face coverage | 7,957 / 11,244 (70.77%) | 8,023 / 11,244 (71.35%) |
| All-status exact face coverage | 8,713 / 15,170 (57.44%) | 8,779 / 15,170 (57.87%) |

After removing the new family, class-19 mapping and per-model timing fields, all 500 model rows are
identical. Every pre-existing physical-family count, non-class-19 class row, reconciliation drop,
diagnostic, predicate observation, invalid/empty result and taxonomy-mismatch count is unchanged.
The 18 records occur across 17 of the 20 affected models; the bounded missed variants remain
explicit follow-up evidence rather than weakened acceptance rules.

The report took 316.311 seconds versus 296.327 seconds for the historical pre-change report, but
that ratio is descriptive because the runs used different Python environments and were not paired.

## Paired real-part performance and false positives

The commit-pinned paired report is
[`round-bottom-slot-performance-census-38f4359.json`](round-bottom-slot-performance-census-38f4359.json),
SHA-256 `c6c1f84d603ca75aaaca0a705fee405cfb7bf36bf5e64676f8b498c17923d979`.
It alternates enabled/disabled order over 13 NIST and Gramel STEP parts on one host:

- every pre-existing aggregate result is exactly equal;
- neither raw nor accepted round-bottom slot candidates occur, so the census adds no false positive;
- disabled total runtime is 216.456 seconds and enabled runtime is 230.299 seconds;
- enabled/disabled ratio is 1.064 and paired median delta is 0.236 seconds, within the 1.10 gate.

## Architecture and transfer

ADRs 0003, 0004, 0005, 0008 and 0010 were reviewed before implementation and against the final
diff. The increment uses the single candidate/evidence lifecycle, preserves same-solid and
occurrence identity, publishes one closed capability-manifest family, and introduces no graph
internals, persistent face name, correspondence promise or reconciliation precedence.

MFInstSeg is not rerun per predicate edit. Its authenticated corpus and canonical format-3 artifact
remain unavailable in this workspace; no individual MFInstSeg model was inspected. The full
transfer baseline remains a milestone requirement for the end of #369 and Epic #290.

## Reproduction

```bash
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version published-test-split \
  --limit 500 \
  --recognition-frame raw \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v5.json \
  --output docs/benchmarks/effectiveness-mfcadpp-500-round-bottom-COMMIT.json

uv run python tools/benchmark_round_bottom_slots.py census \
  --output docs/benchmarks/round-bottom-slot-performance-census-COMMIT.json
```
