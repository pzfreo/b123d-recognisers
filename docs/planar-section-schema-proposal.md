# Planar section schema proposal (version 1)

**Status:** private implementation proposal; not a public package capability
**Owner:** epic #177, F4a / issue #179
**Publication gate:** F7, after the first emitting F4b feature record and ADR 0005 review

## Purpose and authority

Axis-and-span records cannot truthfully express an oblique prismatic feature. This proposal
defines the geometry values a future feature record can use without approximating curves as
polygons. F4a implements the values privately and proves exact compatibility adapters for
`Passage` and `PrismaticPocket`; it does not export these names, change `RecognitionResult`, add a
manifest record, or make a recogniser emit a new value.

Draftwright owns any future read adapter. Its review of this proposal is required before a
production pin moves, but this repository does not write consumer code as part of F4a.

## Proposed JSON values

```json
{
  "frame": {
    "origin": [0.0, 0.0, 0.0],
    "run": [0.0, 0.0, 1.0],
    "u": [1.0, 0.0, 0.0],
    "v": [0.0, 1.0, 0.0]
  },
  "run_interval": [-5.0, 5.0],
  "section": {
    "boundary": [
      {"point": [-2.0, -1.0], "bulge": 0.0},
      {"point": [2.0, -1.0], "bulge": 0.0},
      {"point": [2.0, 1.0], "bulge": 0.0},
      {"point": [-2.0, 1.0], "bulge": 0.0}
    ]
  },
  "ends": {"low_capped": false, "high_capped": false}
}
```

`PlanarSection` itself is only the intrinsic boundary. The enclosing occurrence supplies its
placement, run extent, end topology, and run-local body occurrence. No public persistent body ID
is proposed: repeated entries retain occurrence identity through their containing feature list.

Each boundary vertex starts the edge ending at the next vertex. `bulge == 0` is a line. A finite
nonzero bulge is a circular arc with signed sweep `4 * atan(bulge)`; this permits minor arcs,
semicircles, major arcs, and full circles made from at least two arcs. Boundary winding is positive
in `(u,v)` and its start is the lexicographically least complete serialized cyclic sequence.

Positions and spans use three decimal places, directions six, and dimensionless bulges twelve.
Canonicalisation occurs before serialization at full precision. Projection refuses non-finite or
self-intersecting boundaries, collapsed vertices, a nonzero bulge rounded to zero, or reconstruction
movement beyond the named bounds: `0.0008` for the intrinsic 2-D boundary and `0.002` for the whole
placed occurrence. The latter is the conservative envelope of three-decimal 3-D placement plus the
intrinsic bound, not a recognition tolerance. Direction rounding is multiplied by the actual
section/run extent, so sufficiently long geometry refuses rather than amplifying a tiny angular
serialization error without limit.

## End topology

| Geometry | `low_capped` | `high_capped` |
| --- | --- | --- |
| Passage | false | false |
| Pocket open at high run end | true | false |
| Pocket open at low run end | false | true |

Both capped is deliberately unsupported by the current recess contract: it describes an enclosed
cavity rather than a tool-reachable feature.

## Canonical geometry

The frame is right handed: `run × u = v`. Run sign uses the positive dominant component with the
existing Z→Y→X tie priority. The in-plane seed follows the package's existing `plane_axes` basis.
The frame origin is the closest point to world origin on the run-parallel line through the exact
signed-area centroid. Area and Green-theorem first moments include the circular segments, so an
equivalent split of an arc cannot move the centroid or origin.

These world-coordinate values are equivariant geometry, not rotation-invariant tuples: after a
rigid transform, reconstructing the section and applying the inverse transform must recover the
same boundary. Mirrors, reversed traversal, cyclic shifts, STEP round-trips, and equivalent arc
subdivision must satisfy that rule.

## Migration matrix

| Existing record | F4a conversion | Limitation | Public transition owner |
| --- | --- | --- | --- |
| `Passage` | exact private round-trip | line-only polygon in current record | first emitting F4b family |
| `PrismaticPocket` | exact private round-trip | line-only polygon; preserves opening end | first emitting F4b family |
| `Slot` | none | record cannot distinguish rectangular and obround source | source-aware F4b adapter |
| `Pocket` | none | record cannot distinguish rectangular and obround source | source-aware F4b adapter |
| `Channel` | none | axis-span record omits complete source boundary | source-aware F4b adapter |

Legacy records remain authoritative and byte-identical in F4a. There is no package deserializer,
so there is no generic dual-read API to add. A later public feature record is additive under ADR
0005 and requires a primary owning family, aggregate membership, manifest schema, golden evidence,
compatibility window, and reviewed consumer declaration. F7 separately decides whether neutral
frame/section primitives themselves become public records.

## Rejection and compatibility rules

- Hand-built legacy values with an invalid axis, side count, span, opening sign, or a rounded `at`
  inconsistent with the section's analytic centroid fail conversion.
- Run-local body references are issuer-created and validated on every conversion. Coincident solids
  receive distinct references; copied, foreign, or mutated references fail.
- Reverse projection derives `sides` from a line-only loop. Any arc refuses projection into the two
  current polygonal records.
- The reverse adapter intentionally omits run-local body identity; it preserves exact legacy class,
  ordering, equality, and `to_dict()` instead.
