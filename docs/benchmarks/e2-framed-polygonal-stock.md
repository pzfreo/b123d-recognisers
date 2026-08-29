# E2 framed Polygonal Stock validation

Issue [#311](https://github.com/pzfreo/b123d-recognisers/issues/311) fixes a bounded framed-route
gap at implementation commit `16df9c8ce82536515f9e88aad9cb4cf69c9dcea7`. A regular hexagonal
whole-stock prism may use X, Y or Z in the supplied recognition frame. Attached Polygonal Bosses
remain Z-only.

## Geometry and downstream result

The public record schema is unchanged. `axis` now selects the coordinate used by `base` and `top`;
`center`, `flat_directions` and `flat_centres` remain three-dimensional values in the same frame.
The direct Z record and its golden serialization are unchanged. Direct X/Y cases and framed
canonical, translated, tilted and generic-axis presentations each retain one record backed by the
complete original six-side/two-cap boundary. Equivalent framed presentations produce the exact
same serialized local record.

This closes the provider failure reproduced by downstream Draftwright issue
[`#1371`](https://github.com/pzfreo/draftwright/issues/1371): the framed route previously returned
zero Polygonal Stock records even for its canonical supported prism because the valid
`ORTHOGONAL` frame placed the extrusion direction on local X. The change preserves the existing
frame instead of introducing a family-specific normalization authority.

A read-only consumer check against Draftwright commit `1b21162` passed the generic tilted prism's
exact framed working shape and record into its existing `build_part_model(...,
polygonal_stock=...)` boundary. The resulting `PolygonalStockFeature` retained axis X, length 30,
and A/F 34.641, and exposed the downstream `polygon_across_flats.length` and
`stock_length.length` dimension parameters. No Draftwright source or lock file was changed. This
proves the existing consumer adapter can use the expanded record value; adopting the framed
orchestration and immutable package release remains consumer-owned under Draftwright #1357/#1371.

## MFCAD++ development evidence

The immutable [500-model report](effectiveness-mfcadpp-500-e2-polygonal-stock-16df9c8.json) loaded
and evaluated 500/500 models with zero invalid or empty models. Its complete summary is identical
to E5f. After removing only per-model `seconds`, all 500 model rows have the same canonical SHA-256
as E5f: `e472111335901e1cec4c192ac29d51cb85cfee5a54b3e643716e9ee2d416e498`.

Polygonal Stock is stock context and MFCAD++ class 24 is explicitly incomparable, so no taxonomy
recall claim is made. Neither run emitted Polygonal Stock on this interacting-feature corpus; this
is useful false-positive and regression evidence, not evidence of the authored framed gain.

## Paired performance

`tools/benchmark_polygonal_stock_axes.py` alternates enabled/Z-only execution order per imported
model and compares the complete aggregate after replacing only the newly enabled stock field.

| Workload | Models | Legacy stock | Enabled stock | Exact other outputs | Total ratio | Paired median delta |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| [MFCAD++-500](polygonal-stock-axis-performance-mfcadpp-500-16df9c8.json) | 500 | 0 | 0 | yes | 0.9879 | -0.0027 s |
| [NIST/Gramel census](polygonal-stock-axis-performance-census-16df9c8.json) | 13 | 0 | 0 | yes | 0.9761 | +0.0118 s |

Both are below the Epic #290 `1.10` ceiling. The neutral/negative corpus stock result is reported
alongside the positive authored/downstream case rather than being promoted into a corpus gain.

## Transfer boundary

MFInstSeg was not inspected. The documented roots remain unavailable, so issue #293 stays open and
this increment makes no independent transfer claim.
