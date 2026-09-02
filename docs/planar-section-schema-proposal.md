# Planar section schema proposal (version 1)

**Status:** schema v1 accepted and published by F4b; planar-end schema v2 accepted by ADR 0015
**Owner:** epic #177, F4a/F4b / issues #179 and #184
**Publication gate:** satisfied by Draftwright issue #1337 and package issue #184

## Purpose and authority

Axis-and-span records cannot truthfully express an oblique prismatic feature. This proposal
defines geometry values without approximating curves as polygons. F4a implemented the neutral
values privately and proved exact compatibility adapters. F4b publishes feature-prefixed immutable
records owned by the existing `passages` family: `PassageFrame`, `PassageSectionVertex`,
`PassageSection`, `PassageEnds`, and the enclosing `SectionPassage`. The neutral F7 substrate names
remain private.

Draftwright owns its read adapter. Its explicit issue #1337 approval preceded the F4b production
change; consumer implementation and stable-pin choreography remain consumer-owned work.

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
  "ends": {
    "low_capped": false,
    "high_capped": false,
    "low_gradient": [0.0, 0.0],
    "high_gradient": [0.0, 0.0]
  }
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

### Normative decoding and validation

The future enclosing feature record supplies the model's length-unit contract. Under the current
package capability contract, `frame.origin`, `run_interval`, and section-point coordinates are in
millimetres; `run`, `u`, and `v` are dimensionless direction vectors, and `bulge` is dimensionless.
A point on the placed boundary is reconstructed from serialized values exactly as

```text
world(t, x, y) = origin + t * run + x * u + y * v
```

For perpendicular ends, `t` lies in the closed increasing `run_interval`. Schema v2 interprets
those two values as the termination intersections on the section-centroid run line. At an
intrinsic point `(x, y)`, the exact physical limits are `low + low_gradient[0]*x +
low_gradient[1]*y` and `high + high_gradient[0]*x + high_gradient[1]*y`. Both gradients are
dimensionless and use six decimal places; the v1 geometry is exactly the all-zero case. The low
limit must remain strictly below the high limit over the complete section. A positive bulge and positive sweep are
counter-clockwise in the right-handed `(u, v)` plane when viewed along positive `run`.

A reader uses the rounded basis exactly as serialized. It must not re-orthonormalize or otherwise
repair the frame: the producer's `0.002` whole-occurrence bound is measured against this exact
rounded reconstruction, while an unspecified repair would establish different geometry. Because
six-decimal component rounding does not preserve exact orthonormality, a reader validates the
serialized frame with these closed tolerances:

- each of `run`, `u`, and `v` has Euclidean norm within `1e-6` of one;
- every pairwise absolute dot product is at most `2e-6`; and
- `norm(cross(run, u) - v)` is at most `3e-6`.

For canonical-basis validation only, the reader normalizes the serialized `run`, chooses its
largest absolute **serialized** component (ties Z, then Y, then X), and requires that component to
be positive. It projects the corresponding package seed (X→Y, Y→Z, Z→X), normalizes it as the
expected `u`, and takes `cross(run, u)` as the expected `v`; each serialized in-plane vector must
be within Euclidean distance `3e-6` of that expected vector. The producer makes the same dominant
choice from the six-decimal run before constructing its full-precision basis, so two runs that
serialize identically cannot select different in-plane gauges.

These are serialization-validation bounds, not recognition tolerances. Every vector and point is
an exact-length JSON array (three and two elements respectively). Every numeric member must be a
finite JSON number and not a boolean. `run_interval` contains exactly two numbers with
`low < high`; each end gradient contains exactly two finite six-decimal numbers, and its two
planes must not cross over the boundary. End flags are actual JSON booleans. A nonzero gradient
currently requires a line-only boundary. The boundary contains at least two vertices,
has distinct adjacent points, is simple, has positive signed line-and-arc area, and follows the
canonical winding/start rules. Its analytic serialized centroid must be within `0.0008 mm` of
`(0, 0)`. The rounded placement must satisfy
`abs(dot(origin, run)) <= 0.000868 mm + 1e-6 * norm(origin)`; this is the conservative envelope of
three-decimal origin and six-decimal direction projection from an exactly perpendicular private
frame. Keys shown in the proposed value are required, and unknown keys are rejected until an
enclosing record schema explicitly adds them.

## End topology

| Geometry | `low_capped` | `high_capped` |
| --- | --- | --- |
| Passage | false | false |
| Pocket open at high run end | true | false |
| Pocket open at low run end | false | true |

Both capped is deliberately unsupported by the current recess contract: it describes an enclosed
cavity rather than a tool-reachable feature.

## Canonical geometry

The frame is right handed: `run × u = v`. Run sign and the in-plane seed use the positive dominant
component of the six-decimal serialized run with the existing Z→Y→X tie priority; analytic vectors
remain full precision after that discrete choice. The seed follows the package's existing
`plane_axes` basis.
The frame origin is the closest point to world origin on the run-parallel line through the exact
signed-area centroid. Area and Green-theorem first moments include the circular segments, so an
equivalent split of an arc cannot move the centroid or origin.

These world-coordinate values are equivariant geometry, not rotation-invariant tuples: after a
rigid transform, reconstructing the section and applying the inverse transform must recover the
same boundary. Mirrors, reversed traversal, cyclic shifts, STEP round-trips, and equivalent arc
subdivision must satisfy that rule.

The placed encoding is unique within the private construction tolerance (`1e-9` model units): the
analytic intrinsic-section centroid is `(0, 0)`, and `dot(frame.origin, frame.run) == 0`. A producer
must reject rather than serialize an offset section compensated by the inverse frame-origin
translation, or a run-parallel frame-origin shift compensated by the inverse interval shift.

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

“Planar-section schema version 1” is inherited normatively from the future enclosing feature
record's capability-manifest `schema_version`; the nested geometry value has no independent
version discriminator. The enclosing record schema must identify this version when it first
publishes the value. Any incompatible change to the nested geometry increments that enclosing
record's schema version and follows ADR 0005. This keeps version negotiation at Draftwright's
existing family-record boundary rather than creating a second nested protocol.

## Rejection and compatibility rules

- Hand-built legacy values with an invalid axis, side count, span, opening sign, or a rounded `at`
  inconsistent with the section's analytic centroid fail conversion.
- Run-local body references are issuer-created and validated on every conversion. Coincident solids
  receive distinct references; copied, foreign, or mutated references fail.
- Reverse projection derives `sides` from a line-only loop. Any arc refuses projection into the two
  current polygonal records.
- The reverse adapter intentionally omits run-local body identity; it preserves exact legacy class,
  ordering, equality, and `to_dict()` instead.
