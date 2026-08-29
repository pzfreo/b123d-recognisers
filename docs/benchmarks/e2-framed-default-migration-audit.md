# E2 framed-default migration audit

Issue [#317](https://github.com/pzfreo/b123d-recognisers/issues/317) records the product decision to
make framed recognition the ordinary safe aggregate route. This audit tests the released frame
representative before changing downstream defaults. MFCAD++ is open development evidence; no
MFInstSeg model was available or inspected.

## Reproduction

Commit `37b0d28` adds `--recognition-frame raw|framed` to the canonical effectiveness runner. Both
arms use taxonomy v2, the same first 500 unique lexical model IDs from the published MFCAD++ test
split, and the same OCP/build123d environment. The complete reports retain selection hashes,
package/environment versions, model rows, exact score numerators/denominators and runtime:

- [`raw compatibility score`](effectiveness-mfcadpp-500-raw-compat-37b0d28.json)
- [`framed score`](effectiveness-mfcadpp-500-framed-default-37b0d28.json)
- [`rigid-motion and compatibility transitions`](framed-default-mfcadpp-500-a83b5e5.json)

The rigid-motion sweep independently normalizes the baseline model and an X30-plus-translation
presentation, then matches accepted occurrences through defining-face evidence. It also compares
the raw and framed answers on the untransformed input.

## What framing proves

All 500 models infer a `FULL` frame; none refuses or errors. Framed rigid-motion comparison retains
2,867/2,867 baseline occurrences with zero absences or reclassifications and one already documented
introduced Slot fragment. The raw route retains only 1,166/2,901 under the same presentation,
losing 1,688 occurrences and reclassifying 47. This is decisive evidence that an explicit local
frame solves whole-part presentation bias.

## Why the current representative must not become ordinary yet

Raw-to-framed comparison on the untransformed models has 68 absent, 34 introduced and three
reclassified accepted occurrences across 75 models. Label-aware scoring confirms that the changes
are not uniformly beneficial:

| MFCAD++ class | Raw matched / labelled faces | Framed matched / labelled faces | Precision |
| --- | ---: | ---: | ---: |
| Rectangular pocket (14) | 385 / 907 | 398 / 907 | 0.1377 → 0.1455 |
| Rectangular blind slot (17) | 77 / 178 | 81 / 178 | 0.0564 → 0.0611 |
| Vertical circular blind slot (18) | 47 / 213 | 49 / 213 | 0.0344 → 0.0370 |
| Triangular pocket (13) | 489 / 732 | 474 / 732 | 0.3417 → 0.3362 |
| 6-sided pocket (15) | 828 / 1,133 | 822 / 1,133 | 0.5786 → 0.5830 |
| Circular-end pocket (16) | 423 / 973 | 419 / 973 | 0.3099 → 0.3160 |
| Triangular blind step (20) | 136 / 411 | 132 / 411 | 0.9714 → 0.9706 |
| Circular blind step (21) | 236 / 354 | 234 / 354 | 1.0000 → 1.0000 |
| Rectangular blind step (22) | 403 / 607 | 339 / 607 | 0.2952 → 0.2557 |
| Rectangular through step (8) | 184 / 415 | 182 / 415 | 1.0000 → 1.0000 |

The framed arm emits four additional Rectangular Pads but 18 fewer Pockets, six fewer Prismatic
Pockets, four fewer Angled Steps, one fewer Circular Blind Step and one fewer Through Step. It also
changes Z-specific Face Level and Riser projections substantially. Taxonomy-mismatch defining faces
rise from 1,122 to 1,131. Both arms evaluate all 500 models and return zero empty models.

The isolated totals are 229.04 seconds raw and 255.16 seconds framed, a 1.1140 ratio. The paired
four-way sweep measures 448.48 seconds of raw recognition, 481.38 seconds of framed recognition,
12.67 seconds of inference and 4.33 seconds of normalization. This is close to, but above, the
default 1.10 sentinel and must be reported rather than rounded into compliance.

## Geometric diagnosis and next gate

For a full orthogonal frame, current inference assigns the highest-ranked geometry-established
direction to local X. Several mature recognizers deliberately interpret local Z as their supported
feature axis. On canonical axis-aligned MFCAD++ parts, the strongest direction is commonly the
dominant stock/terminal direction, so assigning it to X systematically changes which physical
direction the mature Z grammar sees. This is a representative convention, not new material-axis
evidence.

The next prerequisite will evaluate a corpus-independent Z-primary representative: the strongest
established direction becomes local Z, the second establishes local X, and right-handed local Y is
derived. The corresponding AXIAL representative also places its sole established line on local Z.
The gauge remains `FULL`, `ORTHOGONAL` or `AXIAL`; no unobservable sign, roll or material meaning is
invented. It must preserve the 100% framed rigid-motion result, improve raw/framed compatibility,
remain deterministic across platforms and traversal, retain topology identity, and rerun the exact
score/runtime evidence above. The framed-default API and downstream migration do not merge until
that evidence is reviewed.

MFInstSeg remains absent at `/app/workspaces-codex/datasets/mfinstseg` and
`/app/workspaces/datasets/mfinstseg`. These MFCAD++ results are not a transfer claim.
