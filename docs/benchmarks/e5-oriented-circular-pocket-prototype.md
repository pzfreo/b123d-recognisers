# E5 coordinate-free circular-end Pocket prototype

Issue: [#495](https://github.com/pzfreo/b123d-recognisers/issues/495)

Prototype commit: `1094249aadb4007e5f5a11100f9eac9ef1b6b6d5`

## Result

The complete published MFCAD++ test split contains a coherent closed circular-end Pocket contract
that the axis-letter `Pocket` record cannot represent. A geometry-first prototype finds 725 exact
blind obround candidates across all 2,500 models. Labels are loaded only after each model's complete
candidate set has been built; all 725 candidates have both class-16-only defining supports and a
class-16-only floor-inclusive constituent set.

Of those candidates, 63 have a principal depth direction but free in-plane long/width directions
outside the existing `_dominant_axis` authority. They span all three principal depth directions and
angles from about 2.6 to 44.2 degrees off an in-plane principal axis. Each has exactly two
equal-radius cylindrical ends, two mutually parallel planar sides tangent to both ends, one shared
blind floor, one shared convex mouth and one valid-solid owner.

Against the merged-head aggregate evidence:

| Current state | Occurrences | Candidate faces already covered | New faces available |
| --- | ---: | ---: | ---: |
| Wholly untouched | 51 | 0 | 255 |
| Partially touched by structural evidence, two of five faces | 6 | 12 | 18 |
| Partially touched by structural evidence, one of five faces | 6 | 6 | 24 |
| **Total** | **63** | **18** | **297** |

The partial overlaps are nine `FaceLevel` and three `Riser` interpretations; none is an accepted
`Pocket`. The existing framed aggregate recovers only one of the 54 raw non-principal untouched
components as an `EdgeOpenCircularPocket`; framing the stock does not align a feature that is
internally rotated within the stock plane.

## Prototype proof

Candidate construction does not use an axis-aligned bounding box or a dataset component. Starting
from a planar floor, it requires:

- exactly two cylindrical and two planar supports meeting the floor concavely;
- equal-radius cylinder axes parallel to the floor normal;
- two opposed side planes parallel to the derived width direction;
- every cylinder tangent to both side planes;
- one observed semicircular floor edge per cylinder, proved by arc length over radius;
- inward-facing cylindrical supports, excluding the geometrically similar added boss;
- a common non-zero floor-to-mouth interval across all four supports;
- exactly one planar mouth meeting every support convexly or smoothly; and
- one valid-solid owner for the complete support and floor set.

Authored controls cover the oriented positive, X/Y/Z and arbitrary rigid presentation, a principal
closed Pocket control, through/round/rectangular negatives, an interrupted support and equal
features on two bodies, plus an added obround boss adversary. Nine focused tests pass. The
prototype issues no Candidate or public record and changes no aggregate result.

## Architectural interpretation

This is not another relaxation of `Pocket` or `EdgeOpenCircularPocket`. The geometry is a complete
closed obround, but its in-plane directions are free vectors that the current axis-letter `Pocket`
schema cannot express. The truthful production shape is therefore a narrow sibling such as
`OrientedCircularPocket`, carrying a free orthonormal section frame, the two observed cap centres,
radius, floor-to-mouth interval/opening direction and one body owner. Complete ends make overall
length derivable without fabrication.

Before production implementation, review the record against ADRs 0002, 0003, 0004, 0005, 0007,
0008, 0010, 0011 and 0018 and confirm a concrete Draftwright IR/planner/rendering path. Draftwright
currently has only axis-letter `PocketFeature`; this is not adapter-only. The prototype is strong
enough to justify that schema/consumer review, but does not pre-approve the final fields.

MFInstSeg was not read, run or inspected during this prototype. Its frozen family-level score set
the priority only.

## Reproduction

```console
uv run python tools/audit_mfcadpp_oriented_circular_pockets.py \
  /path/to/MFCAD++_dataset/step/test \
  --limit 2500 --output /tmp/oriented-circular-pocket-prototype.json
```

The final prototype report SHA-256 is
`f1fff5301bf1bedccd5bd1264ad3d4b08fc162bdc795a6e0d7f1f52598a46ea7`.
