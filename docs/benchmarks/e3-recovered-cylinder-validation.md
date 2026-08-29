# E3 recovered-cylinder substrate validation

This is development evidence for Epic #290 child #276. MFCAD++ is open development data, not a
blind holdout. The licensed Fusion 360 Gallery source archive used by the earlier external spike
was not present in this workspace, so its recorded 29-cylinder / 4-Flat / 1-Hole signal remains
prioritisation evidence and was not promoted to a correctness claim.

## Reproduction

The canonical report was produced from implementation commit `3a202ac` on Linux, Python 3.12.14,
build123d 0.11.1 and OCP/OCCT 7.9.3.1:

```bash
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --limit 500 \
  --dataset-version \
  'MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823' \
  --output docs/benchmarks/effectiveness-mfcadpp-500-e3-cylinders-3a202ac.json
```

Selection remains the first 500 unique lexical model IDs with selection hash
`323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`.

## MFCAD++ result

The complete score vector is byte-equivalent to the E5a report at `67395b6`: 500/500 models load
and evaluate, zero are invalid or empty, every physical-family count, class numerator/denominator,
taxonomy mismatch, reconciliation disposition and diagnostic count is unchanged. In particular,
the aggregate still emits 580 Holes and 199 Bosses. This is the expected neutral MFCAD++ result:
the corpus models in this selection retain native analytic cylinders, so this increment should
preserve their records while moving only the recovered-input boundary.

| runtime | E5a baseline | recovered-cylinder head | change |
| --- | ---: | ---: | ---: |
| median/model | 0.4070 s | 0.4223 s | +3.75% |
| p95/model | 0.8077 s | 0.7941 s | -1.69% |
| total/500 | 223.50 s | 220.90 s | -1.16% |
| maximum | 1.2514 s | 1.4787 s | +18.16% |

The distribution does not show a package-level regression: total and p95 improve while median and
one noisy maximum move in opposite directions. An earlier implementation accidentally sent every
native plane through effective recovery and took 414.31 seconds; it was rejected before review.
The final scan enters recovery only for B-spline/Bezier faces, and a contract test proves a supplied
effective query is untouched for native analytic input.

## Corpus-independent and converted-input evidence

- Exact OCCT-converted internal and external cylinders retain diameter, axis, span and radial role.
- A converted external cylinder reaches the existing Boss consumer with the exact native
  `BossRecord`; a converted bore reaches Hole discovery. Hole end classification remains a named
  downstream native-surface boundary and is not claimed as generally representation-transparent.
- Hole and Boss aggregate Candidates retain the exact original recovered cylindrical faces plus
  their recovery and radial material-side certificates. The issuer rejects wrong primitive kind,
  missing dependency coverage and the wrong internal/external sign.
- Curved side proof covers rigid rotations, both radial signs, open/unproved ownership, projected
  seam samples, classifier disagreement/failure and differential failure. Existing native mirror
  and traversal-order suites remain authoritative controls.
- A warmed 15-run simple-cylinder measurement on the report environment gives a 0.0235-second
  native median and 0.2315-second exact-converted median. Recovery is deliberately the slower path;
  it performs bounded fitting, projection and solid-side probes rather than weakening native input.

MFInstSeg is not a per-increment gate. Its unavailable dataset state remains tracked by #293; no
transfer-baseline claim is made here.
