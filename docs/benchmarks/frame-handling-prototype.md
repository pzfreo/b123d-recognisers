# Part-relative frame-handling evaluation

This evidence supports issue #272 and spike #274. The rigid-motion sweep is instrumentation; the
architectural question is whether recognition should have an explicit part-relative frame.

## Smallest contract tested

`_experimental_frame.py` defines an immutable caller-space `PartFrame`, inverse point transforms,
a framed result pairing that frame with the unchanged `RecognitionResult`, and typed refusals. It
is deliberately absent from the package root and capability manifest.

The origin is the material centre of mass. Two independent analytic direction classes establish
axis lines and a right-handed basis. A single direction does not establish roll and is refused as
`ambiguous-direction`. The prototype still orients each otherwise-unoriented line with a
deterministic world-component sign convention. That is adequate to test the boundary on the named
motions, but is not a geometry-established semantic sign and is a production gap. A transient
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
| local baseline vs independently framed X30+T | 2,750 | **2,745 (99.82%)** | 0 | 5 | 8 |

The 13 differing occurrence events occur in 12/500 models:

- seven introduced Slot fragments: `10098`, `10226`, `10308`, `10395`, `11408`, `11974`, `12794`;
- three absent Slot fragments: `10363`, `115`, `12206`;
- one absent Fillet: `1149`; and
- one absent plus one introduced Pocket defining-evidence group: `12772`.

Ten models are recess-fragment instability, one is blend-boundary instability and one is a
same-family pocket evidence replacement. There are no family reclassifications. These are
accounted failures: OCCT copying and downstream boundary tolerances still perturb evidence at
threshold cases. They prevent default release but do not negate the boundary's value.

The preceding 499-comparable-model raw run retained 1,165/2,780 occurrences (41.9%), with 46
reclassifications and 1,569 absences. The complete post-fix raw total is regenerated before the
decision artifact is finalized rather than extrapolated here.

## Compatibility

The legacy route is untouched and its goldens remain byte-identical. Normalizing even an
unrotated input is not yet behavior-preserving: in the first 499 comparable models, legacy versus
framed baseline retained 2,711/2,780 occurrences, reclassified two, lost 67 and introduced 33.
This is why the spike is opt-in and non-exported. The earlier rich-Passage failures were fixed by
requiring exact axis/sides/length/position agreement and accepting only cyclic/winding-equivalent
closed polygon sections; incompatible projections still fail closed.

## Runtime

For the 500-model framed-only post-fix pass, frame inference took 11.52 seconds, copied-shape
normalization 5.09 seconds and framed recognition 454.58 seconds. Frame work is 3.65% of framed
recognition time. Against the preceding paired raw-recognition measurement (405.88 seconds), the
framed paired path including inference and normalization is about 16.1% slower. The difference is
larger than frame computation itself and must be treated as copied-shape/recognition overhead, not
hidden behind the smaller 3.65% number.

## Recommendation

**Revise and continue.** Keep the explicit frame-plus-local-result boundary and closed ambiguity
behavior. Do not publish or make the copied-shape implementation default yet. Its value is clear:
same-family retention rises from roughly 42% raw to 99.82% framed on real development data, while
all golden cases become invariant. Its remaining work is equally clear: remove or tolerance-specify
the 12-model instability, resolve axis-sign gauge, repeat cross-platform evidence, and
reduce/profile end-to-end overhead.

The authoritative proposed contract and acceptance gate are in ADR 0011.
