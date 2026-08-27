# Part-relative frame-handling evaluation

This evidence supports issue #272 and spike #274. The rigid-motion sweep is instrumentation; the
architectural question is whether recognition should have an explicit part-relative frame.

## Smallest contract tested

The spike defined an immutable caller-space `PartFrame`, inverse point transforms, a framed result
pairing that frame with the unchanged `RecognitionResult`, and typed refusals.

The origin is the material centre of mass. Two independent analytic direction classes establish
axis lines and a right-handed basis. Production revision orients an observable line from the
signed distribution of analytic-face area about the material centre. A symmetric distribution is
not assigned invented meaning: `ORTHOGONAL` exposes a remaining discrete sign/interchange gauge.
A single direction returns `AXIAL`, exposing continuous roll. Representatives of both gauges are
usable coordinate frames but not semantic material directions. No analytic direction is refused.
A transient normalized shape passes through the existing recognition and reconciliation stack
once. Existing public entry points and their coordinate meaning are unchanged.

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

The production rerun retains 2,751/2,751 framed baseline occurrences, with no reclassification,
absence, refusal or error, and introduces the one Slot described below. All 500 solids establish a
`FULL` frame. Its machine report is
[frame-corpus-500-production.json](frame-corpus-500-production.json); the original spike report
remains alongside it rather than being rewritten.

`10098.step` still introduces one Slot fragment in the moved presentation. It is caused by an exact
`width > length` distinction on a nominally square floored recess whose evaluated spans differ by
1.8e-15 after placement. Applying even a small model-length tolerance globally changes two reviewed
legacy Slot claims; a bounded ULP allowance has the same effect because those legacy candidates are
also numerically square. The release therefore preserves legacy semantics and publishes this as a
known opt-in limitation rather than hiding a regression. Framed recognition is not advertised as
byte-identical under every rigid motion.

Raw X30+T retains 1,166/2,784 occurrences (41.9%), reclassifies 47, loses 1,571 and introduces
seven. Framed normalization therefore recovers every raw baseline occurrence on the same named
sample. The complete machine report is [frame-corpus-500.json](frame-corpus-500.json).

## Compatibility

The legacy route is untouched and its goldens remain byte-identical. Normalizing even an
unrotated input is not yet behavior-preserving: across all 500 models, legacy versus framed
baseline retains 2,715/2,784 occurrences, reclassifies two, loses 67 and introduces 33.
This is why the production route remains opt-in. The earlier rich-Passage failures were fixed by
requiring exact axis/sides/length/position agreement and accepting only cyclic/winding-equivalent
closed polygon sections; incompatible projections still fail closed.

## Runtime

For the final production 500-model pass, frame inference took 14.12 seconds, placement normalization
5.00 seconds, framed recognition 498.97 seconds and raw recognition 479.76 seconds. Frame work is
3.83% of framed recognition time; paired framed recognition including frame work is 8.00% slower
than the paired raw route. Import time (27.58 seconds) is excluded from both. These are development
machine measurements, not a latency guarantee.

## Recommendation

**Revise and continue.** Keep the explicit frame-plus-local-result boundary and closed ambiguity
behavior. Do not make the placement implementation default. Its value is clear:
same-family retention rises from roughly 42% raw to 100% framed on real development data, while
all golden cases become invariant. Its remaining work is equally clear: remove or tolerance-specify
axis-sign semantics are addressed. The one introduced Slot fragment is an explicitly accepted
opt-in numerical limitation because eliminating it without a frame-scoped policy changes legacy
recognition. The remaining release gate is packaging and cross-platform evidence.

The authoritative proposed contract and acceptance gate are in ADR 0011.
