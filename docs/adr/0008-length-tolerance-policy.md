# ADR 0008 — Length tolerance policy

- **Status:** Accepted
- **Date:** 2026-08-16
- **Package review:** [epic 0001](../epics/0001-review-remediation.md), finding 2

## Context

Recognition gates are written in fixed millimetres: `_MERGE_TOL = 0.5`, `_HOLE_DIA_TOL = 0.2`,
`_CHORD_MIN = 0.05`, `STEP_LADDER_BOUNDARY_MARGIN = 0.6`. A 2 mm micro-part and a 2 m weldment are
judged by the same absolute band, and a model authored in inches is judged by a band 25× tighter
than intended. The review that opened epic 0001 counted roughly 39 such constants and proposed one
uniform pass over all of them.

Two measurements taken before writing any code contradicted that plan.

**A single reference scale does not exist.** The golden fixtures' largest extents span 30 mm to
180 mm — a factor of six. No one calibration reproduces today's behaviour across the corpus, so
"scale everything, and the goldens stay byte-identical at reference scale" is not achievable.

**Rebuilding the corpus at other scales moves very little, and not monotonically.** Across
0.05×–100×, only three of 68 census cells change. `chamfers_fillets_and_flats` gains a spurious
plate at 0.2×, 5× and 10× but not at 1× or 100×. `turned.py` is invariant at every factor tested —
and its gate is already written in the form this ADR adopts:

```python
_CHAMFER_ALLOWANCE_ABS = 0.5
_CHAMFER_ALLOWANCE_FRAC = 0.12
...
if outer >= od - (_CHAMFER_ALLOWANCE_ABS + _CHAMFER_ALLOWANCE_FRAC * od):
```

Its comment already states the reason: *"Constant + proportional terms cover both a fixed
edge-break and a chamfer that scales with the feature."* An edge-break is a real manufacturing
constant. It does not get bigger because the shaft does. A uniform pass would have scaled it and
introduced a defect where none existed.

Classifying the ~39 sites individually found that **18 of them are not lengths at all** — they are
ratios, unit-vector dot products, angles, counts and float epsilons. Scaling any of those would be
a defect. The review's count was an overcount, and the remaining work is per-site judgement rather
than a mechanical substitution.

## Decision

### One tolerance form

```python
def length_tol(nominal, *, rel, floor):
    return rel * nominal + floor
```

`rel` carries the part of the allowance that grows with the thing being measured; `floor` carries
the part that does not — the noise band below which two coordinates are the same coordinate.

The terms **add** rather than taking a maximum. A maximum discards one term below `floor / rel`:
every feature smaller than that gets exactly the floor and its own size stops mattering, which is
the scale-blindness this ADR exists to remove, merely moved to the small end. Adding keeps both
contributions at every size.

A negative `nominal` would tighten a gate below its floor, which no caller can mean, and raises. A
NaN `nominal` does not: it means the geometry that produced it is malformed, and the package fails
closed on malformed evidence rather than raising. The NaN propagates, every comparison against it
is false, and the candidate is refused.

`part_scale(bbox)` returns a solid's largest bounding-box extent, the reference length for gates
that compare two coordinates with no smaller feature to measure against.

Both live in `_geometry`, which every recogniser may import.

### What scales, and against what

Every length gate takes its `nominal` from the **smallest geometry that determines the
comparison**, not from the part:

- a diameter/radius match scales with that diameter,
- an axial gap between two coaxial bands scales with their diameter,
- a coordinate-merge or plane-coincidence gate, having no local feature, scales with
  `part_scale`.

Preferring the local nominal matters: a 0.5 mm merge tolerance is right for a 3 mm hole in a 500 mm
plate, and scaling it to the plate would merge the hole into its neighbour.

### What never scales

Dimensionless quantities: ratios and fractions; dot products of unit vectors; angles; counts;
float-comparison epsilons. These are already scale-free and scaling them is a defect.

### What stays absolute on purpose

A constant that models a physical process rather than a measurement stays absolute. `turned`'s two
edge-break constants are the current instances: a deburr is the same size on a 5 mm shaft and a
500 mm one, so scaling it is the defect.

An absolute constant is legitimate only when a comment says which physical constant it encodes,
**and** it is bounded so it cannot swamp a small feature. Two bounds work:

- pair it with a proportional term, as `_CHAMFER_ALLOWANCE_ABS + _CHAMFER_ALLOWANCE_FRAC * od`
  does, when the quantity has both a fixed and a size-dependent part; or
- cap it against the feature it is applied to, as `min(_OD_SPAN_PAD, band_width / 2)` does, when
  the risk is that the constant bridges or swallows the feature.

An unbounded absolute constant is a defect whether or not its physical justification is sound.

### Record rounding is out of scope

`round(x, 3)` / `round(x, 4)` in record projections and the `FLOAT_DIGITS` canonicalisation are the
public record contract under ADR 0002 and the capability schema under ADR 0005. They are not
tolerances and do not scale.

## Site classification

Every numeric gate in the package, classified. `no change` means the site is already correct.

### Not lengths — never scale (18)

| Site | Value | Quantity |
| --- | --- | --- |
| `_hole_patterns._BC_SPACING_TOL` | 0.04 | fraction — applied as `* even` |
| `_pattern_geometry._PATTERN_REL_TOL` | 0.02 | relative coefficient |
| `_hole_features._SPOTFACE_MAX_RATIO` | 0.2 | ratio |
| `countersinks._MIN_MAJOR_RATIO` | 1.5 | ratio |
| `countersinks._MAX_INCLUDED_ANGLE` | 160.0 | angle |
| `_recess_core._FLOOR_COVER_FRAC` | 0.5 | area fraction |
| `_recess_core._VOID_VOL_FRAC` | 0.01 | volume fraction |
| `_recess_core._LENGTH_TIE_FRAC` | 0.05 | fraction |
| `_recess_core._SLOT_MAX_SPAN_FRAC` | 0.9 | fraction |
| `_recess_core._OBROUND_RATIO_TOL` | 0.1 | extent-to-radius ratio |
| `_recess_core._AXIS_ALIGNED_TOL` | 1e-3 | unit-normal component |
| `levels._STEP_MIN_AREA_FRAC` | 0.01 | area fraction |
| `flats._RADIAL_TOL` | 0.05 | unit dot product |
| `flats._ANTIPARALLEL_TOL` | 0.05 | unit dot product |
| `turned._AXIS_NORMAL_TOL` | 0.05 | unit-normal component |
| `turned._SQUARENESS_TOL` | 0.15 | fraction — applied as `* cross` |
| `turned._OD_FILL_MIN` | 0.6 | fraction |
| `_geometry._DOMINANT_TIE_TOL` | 1e-12 | float epsilon |

The `*_frac` keyword arguments on the public recognisers (`min_area_frac`, `max_thick_frac`,
`max_leg_frac`, `max_radius_frac`), `polygonal_bosses.angle_tol`, `repeating_profiles`' two counts
and `_geometry._axis_direction_is_aligned(tol=1e-3)` are in the same class.

Several of these read as absolute because they are named `*_TOL`. Renaming them is
[#42](https://github.com/pzfreo/b123d-recognisers/issues/42), epic finding 5.

### Lengths already scaled — no change (5)

| Site | Form | Reference |
| --- | --- | --- |
| `_pattern_geometry._pattern_tol` | `rel * n + floor` | feature |
| `profiled_bores._recognise_double_d_bores_one` | `max(tol, scale * 1e-5)` | part |
| `profiled_bores.read_double_d_tool` | `max(tol, scale * 1e-5)` | part |
| `profiled_bores.double_d_profile` | `max(8 * tol, profile_scale * 1e-3)` | feature |
| `repeating_profiles._recognise_solid` | `max(tol, scale * 1e-5)` | part |

The four `max(...)` sites keep that form. Rewriting them additively would change behaviour for no
benefit; the policy above governs new and converted sites.

### Deliberately absolute (3)

| Site | Value | Physical constant |
| --- | --- | --- |
| `turned._CHAMFER_ALLOWANCE_ABS` | 0.5 | a fixed edge-break, paired with `_CHAMFER_ALLOWANCE_FRAC` |
| `turned._OD_SPAN_PAD` | 0.7 | the same edge-break, spanning a chamfer-shortened band edge |
| `levels.STEP_LADDER_BOUNDARY_MARGIN` | 0.6 | an end treatment just inside a turned end face |

`_OD_SPAN_PAD` was classified feature-relative when this ADR was written, and **measurement moved
it**. Converted to 8.75% of the band diameter it reaches 2.6 mm on a 30 mm band, bridges the 5 mm
groove in the turned-step golden, and reports that groove's step at its neighbour's OD. It spans
an edge break — the same physical constant as its sibling two lines below it in the source — and a
deburr does not grow with the shaft.

It is now capped at half the band's own width, so it cannot bridge the band it pads however small
the part is modelled. That cap, not a proportional term, is what makes a legitimately absolute
gate safe at small scale, and is the pattern to reach for when the next one appears.

`STEP_LADDER_BOUNDARY_MARGIN` moved the same way, and for the same reason. Deriving it from the
span broke the ADR 0006 regression, which pins a 0.6 mm end step on a 10 mm part as something the
inset must exclude — that step is a chamfer or edge break, and a deburr is the same size on a 20 mm
dowel and a 2 m shaft. It stays absolute, capped at a quarter of the span by
`levels.bounded_end_margin`, shared by the prismatic capture and the turned projection as ADR 0006
requires.

**Three of the sites this ADR listed for conversion turned out to belong here instead**, each
found by a test rather than by re-reading the code. That ratio is the argument for classifying
per site: a uniform pass would have scaled all three.

### Feature-relative lengths to convert (17)

Each has a diameter, radius or width in hand at the comparison.

| Site | Value | Nominal |
| --- | --- | --- |
| `_cylinder_substrate._STACK_GAP_TOL` | 0.1 | band diameter |
| `countersinks._TOL` | 0.05 | minor radius |
| `countersinks._COAXIAL_TOL` | 0.1 | drill diameter |
| `countersinks._HOLE_DIA_TOL` | 0.2 | hole diameter |
| `countersinks._HOLE_AXIS_TOL` | 0.2 | hole diameter |
| `countersinks._HOLE_MOUTH_TOL` | 0.5 | hole diameter |
| `flats._CHORD_MIN` | 0.05 | stock radius |
| `flats._CHORD_MARGIN` | 0.05 | stock radius |
| `flats._MIN_FLAT_DEPTH` | 0.5 | stock radius |
| `flats._OD_REACH_TOL` | 0.1 | stock radius |
| `flats._AXIS_LINE_TOL` | 0.1 | stock radius |
| `grooves._ADJ_TOL` | 0.1 | band diameter |
| `grooves._DIA_MARGIN` | 0.2 | band diameter |
| `grooves._WALL_DIA_TOL` | 0.5 | band diameter |
| `grooves._WIDTH_MARGIN` | 0.05 | wider neighbouring wall width |
| `_recess_core._END_RADIUS_TOL` | 0.15 | cap radius |
| `_recess_core._CAP_CLUSTER_TOL` | 0.3 | cap radius |

`_hole_features`' stack margin (`max(_STACK_GAP_TOL, min(0.45 * length, 0.5 * diameter))`) and
`_recess_core._VOID_INSET` (`min(_VOID_INSET, (hi - lo) / 4)`) are already capped by a feature
dimension; only their absolute term is converted.

### Part-relative lengths to convert (13)

No local feature determines the comparison, so the reference is `part_scale`.

| Site | Value | Public |
| --- | --- | --- |
| `levels.recognise_face_levels(tol=)` | 0.5 | yes |
| `levels.recognise_risers(tol=)` | 0.5 | yes |
| `levels.RiserEvidence.tol` | 0.5 | **record field** |
| `levels.STEP_LADDER_BOUNDARY_MARGIN` | 0.6 | yes |
| `chamfers.recognise_chamfers(tol=)` | 0.5 | yes |
| `plates.recognise_plates(tol=)` | 0.5 | yes |
| `pads.recognise_rectangular_pads(tol=)` | 0.2 | yes |
| `polygonal_bosses.recognise_polygonal_bosses(tol=)` | 0.2 | yes |
| `polygonal_bosses.recognise_polygonal_stock(tol=)` | 0.2 | yes |
| `fillets.recognise_fillets(min_radius=)` | 0.6 | yes |
| `_recess_core._MERGE_TOL` | 0.5 | no |
| `_recess_core._FLOOR_TOL` | 0.3 | no |
| `_recess_core._recognise_corner_notches(tol=)` | 0.5 | no — parameter removed, no caller ever supplied one |

`_pattern_geometry._PATTERN_ABS_TOL` also appears in three standalone degeneracy guards
(`span < _PATTERN_ABS_TOL`) that ask "is this length essentially zero"; those are part-relative and
convert with this group.

`RiserEvidence.tol` is a **public record field** whose value appears in the pinned goldens. A
derived tolerance changes that value for every fixture containing a riser. This is a visible record
change, not only a classification change, and the release note must say so.

## Consequences

**Recognition behaviour changes**, on a minor version. Parts far from the fixture corpus's scale
are classified differently, which is the point. Parts within it mostly are not, but the goldens are
not byte-identical and each moved cell is reviewed on its own evidence, as ADR 0002 requires.

The public `tol=` keywords gain `None` as their default, resolving to the derived value; passing a
float keeps today's meaning, so a caller who has calibrated for their own parts is not broken.

The ADR 0005 manifest records record *schemas*, not function signatures, so those defaults do not
appear in it — an earlier draft of this ADR claimed they did. **No record schema changes**: no
record gains, loses or alters a field, so the only difference from 0.2.2 is the package version
the manifest embeds, exactly as on any release. The one thing a consumer can observe is
recognition output away from reference scale, which is the point.

Conversion landed as five changes rather than the three planned, each split off when the
previous one's evidence showed it was a different defect: the policy and helpers; the
feature-relative group; distance-based coplanar grouping; the area-gate tie break; then the
part-relative group with the public surface, and `_recess_core` behind it.

The outcome is that every golden fixture now recognises identically from 0.05x to 100x, in every
family. `tests/test_scale_invariance.py` holds it, with an exclusion list that is empty and a
test asserting it stays empty.

Absolute constants remain **legal but justified**. A new one needs a comment naming the physical
constant it encodes and a proportional term beside it. Anything else is a defect this ADR exists to
catch in review.
