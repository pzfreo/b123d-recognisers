# Part-relative frame-handling evaluation

This evidence supports issue #272 and spike #274. The rigid-motion sweep is instrumentation; the
architectural question is whether recognition should have an explicit part-relative frame.

## Smallest contract tested

`_experimental_frame.py` defines an immutable caller-space `PartFrame`, inverse point transforms,
a framed result pairing that frame with the unchanged `RecognitionResult`, and typed refusals. It
is deliberately absent from the package root and capability manifest.

The origin is the material centre of mass. Two independent analytic direction classes establish
axis lines and a right-handed basis. A single direction returns an explicit `AXIAL` gauge: roll is
unobservable and its world-seeded basis is only a deterministic representative, not a semantic
material direction. No analytic direction is refused. The prototype still orients each
otherwise-unoriented line with a deterministic world-component sign convention. That is adequate
to test the boundary on the named motions, but is not a geometry-established semantic sign and is
a production gap. A transient
normalized shape passes through the existing recognition and reconciliation stack once. Existing
public entry points and their coordinate meaning are unchanged.

This is normalization, not general free-axis recognition. Every record in a framed result is in
the accompanying local frame and must not be interpreted in caller space.

## Golden result

Every original, rotated and translated presentation inferred its frame independently. Occurrences
were matched by defining-face evidence rather than census counts.

| presentation | baseline | same family | reclassified | absent | introduced |
| --- | ---: | ---: | ---: | ---: | ---: |
| Z30 | 75 | **75** | 0 | 0 | 0 |
| X30 + translation | 75 | **75** | 0 | 0 | 0 |
| X90 | 75 | **75** | 0 | 0 | 0 |

This covers both observed failure classes: disappearing families and frame-dependent
Slot/Passage or Pocket/PrismaticPocket reconciliation.

## MFCAD++ development evaluation

Selection is the first 500 STEP filenames in lexical ascending order from
`MFCAD++_dataset/step/test` at `/app/workspaces-codex/datasets/mfcadpp`. This is named open
development evidence. No MFTRCAD sealed holdout was used. The independent presentation is X30
followed by translation `(173, -91, 42)`.

All 500 models infer a full frame after one fix to a pre-existing recess probe: model `11281.step`
created a positive but unconstructible 7.1e-15 bounding-box span. The reducer now treats spans at
or below the coordinate floor as unable to prove void and fails that candidate closed.

| framed comparison | baseline | same family | reclassified | absent | introduced |
| --- | ---: | ---: | ---: | ---: | ---: |
| local baseline vs independently framed X30+T | 2,750 | **2,750 (100%)** | 0 | 0 | 1 |

Only `10098.step` differs: its five baseline occurrences all remain and the transformed
presentation introduces one extra Slot fragment. There are no family reclassifications or absent
occurrences. This is an accounted downstream recess-boundary instability and remains a gate for a
default route, but it no longer obscures the frame result.

Raw X30+T retains 1,166/2,784 occurrences (41.9%), reclassifies 47, loses 1,571 and introduces
seven. Framed normalization therefore recovers every raw baseline occurrence on the same named
sample. The complete machine report is [frame-corpus-500.json](frame-corpus-500.json).

## Compatibility

The legacy route is untouched and its goldens remain byte-identical. Normalizing even an
unrotated input is not yet behavior-preserving: across all 500 models, legacy versus framed
baseline retains 2,715/2,784 occurrences, reclassifies two, loses 67 and introduces 33.
This is why the spike is opt-in and non-exported. The earlier rich-Passage failures were fixed by
requiring exact axis/sides/length/position agreement and accepting only cyclic/winding-equivalent
closed polygon sections; incompatible projections still fail closed.

## Runtime

For the definitive 500-model pass, frame inference took 11.96 seconds, placement normalization
4.35 seconds, framed recognition 436.12 seconds and raw recognition 417.77 seconds. Frame work is
3.74% of framed recognition time; paired framed recognition including frame work is 8.29% slower
than the paired raw route. Import time (24.98 seconds) is excluded from both.

## Recommendation

**Revise and continue.** Keep the explicit frame-plus-local-result boundary and closed ambiguity
behavior. Do not publish or make the placement implementation default yet. Its value is clear:
same-family retention rises from roughly 42% raw to 100% framed on real development data, while
all golden cases become invariant. Its remaining work is equally clear: remove or tolerance-specify
the one introduced Slot fragment, resolve axis-sign gauge, repeat cross-platform evidence, and
reduce/profile end-to-end overhead.

The authoritative proposed contract and acceptance gate are in ADR 0011.
