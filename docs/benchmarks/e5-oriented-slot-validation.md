# E5 free-axis rectangular Slot validation

Issue #310 adds an explicitly compatible `OrientedSlot` successor for enclosed rectangular
through-cuts whose width/long axes are oblique in an otherwise principal-axis stock frame. The
recogniser projects only an exact four-line, non-square `SectionPassage` occurrence and reissues
its original defining walls. Principal-axis occurrences remain legacy `Slot`.

## Authored boundary

`tests/test_oriented_slots.py` covers non-special internal angles; unchanged x/y/z principal-axis
controls; raw and framed whole-part presentation; mirrors; translation; scale; STEP and reversed
face traversal; exact direct/aggregate evidence parity; real linear and grid patterns; and
same-body versus compound ownership. Negative fixtures cover square, curved, tapered, blind,
edge-open, material-obstructed, and competing-orientation geometry. Pattern grouping fails closed
across orientation, depth plane, width, length, or ambiguous body ownership. Aggregate
reconciliation rejects the generic source Passage only when the successor has the exact same
non-empty defining wall set.

`tests/golden/oriented_slots` is package-originated semantic evidence rather than a misleading
reuse of the principal-axis Draftwright golden. It pins the physical records and their source
passages, aggregate array membership, exact reconciliation dispositions, and census count.

## MFCAD++-500 development transfer

The fixed lexical 500-model selection was run in raw coordinates at package commit `72541af`
using `effectiveness-taxonomy-v10.json`. The canonical report is
`effectiveness-mfcadpp-500-oriented-slot-72541af.json`.

Taxonomy v10 makes an explicit vocabulary translation: MFCAD++ calls an enclosed rectangular
through-cut a *rectangular passage* (class 3), while its published feature diagram uses
*rectangular through slot* (class 6) for an edge-open/full-span cut. The package and Draftwright
use Slot for the former consumer semantic. This translation affects scoring only and never enters
recognition.

Compared with `effectiveness-mfcadpp-500-paired-ramp-bd6bcc7.json`:

- six generic Passage occurrences become explicit `oriented-slots`, with six exact Passage
  precedence dispositions;
- class-3 defining precision remains `397/1272` and defining recall remains `397/912`;
- class-3 face coverage rises from `658/912` to `660/912`;
- every class-6 defining metric is unchanged, while face coverage rises from `199/237` to
  `200/237`;
- taxonomy-mismatched defining faces fall from `3195` to `3194`; and
- selection, loading and validity remain exactly `500/500`, with no invalid models.

The result is therefore a downstream semantic gain with no defining-score regression. MFInstSeg
was not inspected or run for this development increment; it remains the separate pseudo-blind
transfer baseline.
