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

### A tolerance is not a threshold

Added in 0.2.4 after this ADR's first application shipped a regression. The original rule —
"lengths scale with the geometry they judge" — conflates two kinds of constant:

**A tolerance** asks *are these two things the same?* — `abs(a - b) <= tol`, a coordinate merge, a
plane coincidence. It scales with what it compares, because measurement and modelling error do.

**A minimum-evidence threshold** asks *is this big enough to be a feature?* — `leg >= min`,
`radius >= min`, `thickness > tol`, `depth >= min`. It **must not scale with the part**. Doing so
makes a feature's existence depend on what surrounds it, so the same 1 mm chamfer is recognised on
an 80 mm plate and absent on a 200 mm one. Nor can it usefully scale with the feature, because the
gate *is* on the feature's own size.

The deeper objection is ADR 0001. Whether a 1 mm fillet on a 200 mm part is worth dimensioning is
consumer policy, and this package reports geometric facts rather than deciding significance.
Scaling a threshold answers that question inside recognition, silently, on the consumer's behalf.

0.2.3 scaled six thresholds to the part — `chamfers` minimum leg, `fillets.min_radius`, `plates`
slab thickness, `pads` footprint, `polygonal_bosses` height, `flats` minimum depth — and scaled the
recess merge band to the whole solid, which merged pockets a smaller plate kept distinct. Every
one of nineteen observed deltas on real parts was a lost record and none was a gain, which is the
signature of a one-directional change rather than of removing false positives.

Thresholds are therefore absolute, and belong with the deliberately-absolute class below.

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

### Proportional tolerances (12)

Each asks *are these two measurements of one feature the same?*, and each has that feature's own
diameter, radius or width in hand at the comparison. These are what the policy is for.

| Site | Nominal |
| --- | --- |
| `_cylinder_substrate._STACK_GAP_FRAC` | band diameter |
| `countersinks._MINOR_MATCH_FRAC` | minor radius |
| `countersinks._COAXIAL_FRAC` | drill diameter |
| `countersinks._HOLE_DIA_FRAC` | hole diameter |
| `countersinks._HOLE_AXIS_FRAC` | hole diameter |
| `countersinks._HOLE_MOUTH_FRAC` | hole diameter |
| `flats._OD_REACH_FRAC` | stock radius |
| `flats._AXIS_LINE_FRAC` | stock radius |
| `grooves._ADJ_FRAC` | band diameter |
| `grooves._WALL_DIA_FRAC` | wider wall diameter |
| `_recess_core._END_RADIUS_FRAC` | cap radius |
| `_recess_core._CAP_CLUSTER_FRAC` | cap radius |

### Minimum-evidence thresholds — absolute (13)

Each asks *is this big enough to be a feature?* All thirteen were converted in 0.2.3 and reverted
in 0.2.4; see the section above on why a threshold is not a tolerance. The values are the ones
0.2.2 used.

| Site | Value | What it gates |
| --- | --- | --- |
| `chamfers._MIN_LEG` | 0.5 | minimum chamfer leg |
| `fillets._MIN_RADIUS` | 0.6 | minimum blend radius |
| `plates._TOL` | 0.5 | minimum slab thickness |
| `pads._TOL` | 0.2 | minimum pad footprint |
| `polygonal_bosses._TOL` | 0.2 | minimum boss height and support span |
| `levels._TOL` | 0.5 | level grouping and minimum riser height |
| `flats._MIN_FLAT_DEPTH` | 0.5 | minimum material removed |
| `flats._CHORD_MIN` | 0.05 | minimum offset from the axis |
| `flats._CHORD_MARGIN` | 0.05 | minimum inset from the OD |
| `grooves._DIA_MARGIN` | 0.2 | minimum step down into the band |
| `grooves._WIDTH_MARGIN` | 0.05 | minimum narrowness against the wider wall |
| `_recess_core._MERGE_TOL` | 0.5 | coordinate merge and minimum slot-end separation |
| `_recess_core._FLOOR_TOL` | 0.3 | floor-plane coincidence |

Three of the thirteen were found only after the first fix shipped — the `flats` chord gates by
running real parts, the `grooves` margins by reading every remaining gate and asking which
question it asks. Grep does not distinguish a threshold from a tolerance; only the comparison does.


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

That conversion overreached, and 0.2.4 pulled thirteen of the sites back — see the threshold
section above. The families that remain scale-invariant across 0.05x-100x are those gated only by
proportional tolerances; `tests/test_scale_invariance.py` holds them, and names the rest in an
exclusion list that is a statement of design rather than of debt. A family gated by an absolute
minimum is *correctly* not scale-invariant: a 1 mm chamfer shrunk to 0.05 mm is a deburr.

Absolute constants remain **legal but justified**. A new one needs a comment naming the physical
constant it encodes and a proportional term beside it. Anything else is a defect this ADR exists to
catch in review.
