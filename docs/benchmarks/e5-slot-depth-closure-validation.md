# E5 Slot curved-depth closure validation

Issue [#353](https://github.com/pzfreo/b123d-recognisers/issues/353) addresses one concrete source
of accepted false `Slot` occurrences: a deep obround blind pocket whose machining depth is longer
than its footprint. The paired-wall length heuristic can transpose length and depth, look for the
planar floor on the wrong axis, and publish the pocket's tangent curved footprint ends as an
allegedly open through direction.

## Geometric authority

A through Slot must remain open at both ends of its selected depth axis. The existing immutable AAG
now refuses a proposal when a connected non-planar region joins both proposed walls smoothly and
closes either selected depth boundary. Smooth regions are expanded across tangent STEP patches;
connected non-planar components are then considered separately so two curved ends do not merge only
because both join the same planar walls. Correctly oriented obround Slot caps remain on the long-axis
ends, and nonsmooth added-material interruptions retain their previous behavior.

This is a topology statement independent of corpus labels. It changes no record, evidence,
reconciliation or tolerance contract. `COORD_FLOOR` is used only to compare coordinates belonging to
the same topological boundary. ADR 0003 records the authority.

## Authored evidence

The regression constructs a deep obround blind pocket and proves that it produces one `Pocket` and
no direct or aggregate `Slot`, both natively and after a principal-axis rigid placement and STEP
round trip. A forced `wall—curved patch—curved patch—wall` graph proves split-cap handling in both
neighbour orders. Existing straight and obround through Slots, curved-end provenance, coaxial-post,
H/U/rib, compound and reconciliation controls remain in the focused suite.

## Exact MFCAD++ comparison

The paired runs use the published MFCAD++ test split, lexical first 500 unique IDs, raw recognition,
Python 3.12.14, build123d 0.11.1, OCP 7.9.3.1, taxonomy v2 SHA-256
`67f092a2aa8d08be94e9be409c1fb338350626c7f4d1398c2f78be3123977f3b`, and selection SHA-256
`323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`.

| Measure | Parent `83d5204` | Enabled `1ced915` |
| --- | ---: | ---: |
| Models evaluated / invalid / empty | 500 / 0 / 0 | 500 / 0 / 0 |
| Accepted Slots | 157 | 45 |
| Class-6 matched / claimed defining faces | 31 / 315 | 31 / 88 |
| Class-6 defining-face precision | 0.0984 | 0.3523 |
| Class-6 matched / labelled defining faces | 31 / 237 | 31 / 237 |
| Class-6 defining-face recall | 0.1308 | 0.1308 |
| Class-7 matched / claimed defining faces | 0 / 315 | 0 / 88 |
| Class-7 defining-face recall | 0 / 78 | 0 / 78 |
| All-corpus taxonomy-mismatch face occurrences | 3,471 | 3,243 |
| Total runtime | 265.152 s | 263.495 s |
| Runtime ratio | — | 0.9938 |

Every non-Slot physical-family count is exactly equal. All 31 correctly labelled rectangular Slot
faces are retained; 227 nonmatching Slot claims disappear. Circular through-slot recall remains
zero, so this increment improves precision without claiming that the Slot family is complete.
The canonical reports are the
[parent](effectiveness-mfcadpp-500-slot-depth-closure-parent-83d5204.json) and
[enabled](effectiveness-mfcadpp-500-slot-depth-closure-1ced915.json) JSON files.

The externally supplied MFInstSeg milestone summary is not rerun here because its authenticated
corpus and canonical JSON are not mounted in this workspace. No MFInstSeg model was inspected.

## Reproduction

Run the command below at each named commit, changing only the output filename:

```bash
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version published-test-split \
  --limit 500 \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v2.json \
  --output docs/benchmarks/effectiveness-mfcadpp-500-slot-depth-closure-COMMIT.json
```
