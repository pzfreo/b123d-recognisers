# E2 frame representative audit

Issue [#318](https://github.com/pzfreo/b123d-recognisers/issues/318) tested whether assigning the
strongest geometry-established direction to local Z would remove the raw/framed effectiveness gap
found while preparing [#317](https://github.com/pzfreo/b123d-recognisers/issues/317). It does not.
The production convention is therefore unchanged.

## Corpus-independent hypothesis

The released representative assigns the highest-ranked established line to local X, the second to
local Y and derives local Z. The experimental convention assigned the strongest line to local Z,
the second to local X and derived a right-handed Y. AXIAL likewise put its sole established line on
Z. The experiment changed no direction evidence, sign proof, gauge, origin, normalization,
topology, recogniser predicate, record or reconciliation rule.

Authored ORTHOGONAL and AXIAL fixtures proved the experimental convention exactly, including rigid
motion, right-handedness and the existing complete golden invariance suite. Those tests were
removed with the experiment because they describe a convention that is not shipping.

## Matched A/B result

Both arms use the same first 100 lexical MFCAD++ test-split models and the same four-way comparison:
raw baseline, raw X30-plus-translation, independently framed baseline, and independently framed
presentation. Every model inferred a `FULL` frame and neither arm refused.

| Result | Released X-primary representative | Experimental Z-primary representative |
| --- | ---: | ---: |
| Framed baseline occurrences | 597 | 598 |
| Framed rigid-motion same-family | 597 / 597 | 598 / 598 |
| Framed rigid-motion absent / reclassified | 0 / 0 | 0 / 0 |
| Known introduced Slot fragment | 1 | 1 |
| Raw→framed same-family | 590 / 605 | 593 / 605 |
| Raw→framed absent | 14 | 12 |
| Raw→framed introduced | 6 | 5 |
| Raw→framed reclassified | 1 | 0 |

Machine reports:

- [`released representative`](x-primary-frame-mfcadpp-100-0685ac1.json)
- [`experimental representative`](z-primary-frame-mfcadpp-100-2df2411.json)

The Z-primary convention modestly moves three occurrences into same-family compatibility, but it
still leaves 17 baseline transitions. Twelve are Pocket absences/introductions across the two arms.
It preserves presentation invariance because either deterministic representative follows rigid
motion; it does not make an axis-restricted recogniser independent of which principal line receives
local Z.

## Decision

Close #318 with no production frame change. Biasing frame inference toward the axis preferred by
current recognisers would encode downstream limitations in an otherwise neutral gauge convention.
The system defect belongs at the recogniser/frame boundary: an ordinary framed route requires the
affected feature grammar to be principal-axis-covariant, or to state an explicit unsupported
outcome, rather than letting an arbitrary representative decide whether the feature exists.

The versioned corpus harness improvements remain useful and are the only implementation to retain:
frame reports now record commit, package/environment versions and can write immutable artifacts;
the canonical effectiveness runner can score either raw or framed recognition. The framed-default
migration remains paused while the largest affected physical family is isolated and generalized in
a separately evidenced child.

MFInstSeg was not available or inspected. This is open MFCAD++ development evidence, not transfer
evidence.
