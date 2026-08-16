# Epic 0001 — Tolerance policy and named constants

**Status:** proposed
**Owner:** @pzfreo
**Target release:** 0.3.0 (minor — recognition behaviour changes off reference scale)
**Opened:** 2026-08-16

## Problem

Most length tolerances in the package are fixed millimetre constants: `_MERGE_TOL = 0.5`,
`_HOLE_DIA_TOL = 0.2`, `_CHORD_MIN = 0.05`, `boundary_margin = 0.6`. A 2 mm micro-part and a
2 m weldment are held to the same absolute gates, and a model authored in inches silently
changes classification. Nothing in the test suite exercises any scale other than the golden
fixtures' ~50 mm envelope, so the failure mode is currently invisible.

Two modules already do this correctly and are the template, not a new invention:

- `_pattern_geometry._pattern_tol(nominal) = _PATTERN_REL_TOL * nominal + _PATTERN_ABS_TOL`
  — the relative-plus-floor form this epic generalises.
- `profiled_bores` and `repeating_profiles` derive `max(tol, part_scale * 1e-5)` from the part
  envelope.

## Scope — what "remove all magic numbers" means here

The source contains ~189 non-trivial numeric literals. They are **not** one kind of thing, and
treating them as one would introduce bugs. The epic classifies them into six kinds and applies a
different rule to each:

| Kind | Example | Rule | Count |
|---|---|---|---:|
| **Length tolerance** | `_MERGE_TOL = 0.5`, `_HOLE_DIA_TOL = 0.2` | **Scale with the part.** The epic's real target. | ~39 |
| Dimensionless ratio | `_FLOOR_COVER_FRAC = 0.5`, `max_leg_frac = 0.45` | Name it; never scale it. Already correct. | ~15 |
| Direction gate | `0.99` normal component, `0.9` dot product, `_SQUARENESS_TOL = 0.15` | Name it; never scale it — these compare **unit vectors**. | ~20 |
| Angle | `_MAX_INCLUDED_ANGLE = 160.0`, `math.radians(2)` | Name it; never scale it. | ~4 |
| Count / index | `side_count != 6`, `_MIN_REPEAT_COUNT = 5`, `bb[4]` | Leave alone. Tuple indices are not magic numbers. | ~30 |
| Machine epsilon / rounding | `1e-12`, `2e-6`, `round(x, 4)` | **Do not touch.** `round(x, 4)` is the record serialisation contract — changing it moves every golden and the capability schema. | ~80 |

**Scaling a direction gate or a rounding precision would be a defect.** Only the first row moves.

`_BC_SPACING_TOL = 0.04` is a worked example of why classification comes first: it reads as an
absolute constant but is already applied relatively (`> _BC_SPACING_TOL * even`). It needs a
rename, not a scaling change.

## Constraints this epic must respect

1. **This is a recognition-behaviour change.** Every release note since 0.1.0 states that canonical
   semantic goldens are unchanged. That guarantee ends here, so per
   [`docs/delivery-protocol.md`](../delivery-protocol.md) the epic needs an approved behaviour
   issue, an ADR, a compatibility note, and a package prerelease that Draftwright validates before
   the stable release.
2. **Calibrate so 1× is unchanged.** Choose `rel` and `abs_floor` per constant so that at the
   golden fixtures' envelope the effective tolerance equals today's value. Goldens then stay
   byte-identical *by construction* and only off-reference-scale behaviour changes. Verify this per
   PR — do not assume it.
3. **Public `tol=` defaults are API surface.** `recognise_plates`, `recognise_chamfers`,
   `recognise_fillets`, `recognise_rectangular_pads`, `recognise_risers` and the `levels` helpers
   expose tolerance keywords with literal defaults, and those signatures are recorded in the
   capability manifest. Changing a default to a derived value is a signature change and lands on
   its own, ahead of any behaviour change.
4. **CI stays green at every commit.** No `xfail`, no `skip`. Known-broken scale behaviour is
   recorded in a pinned drift baseline that each PR shrinks (see PR 1).

## Pull requests

Each PR is independently landable and leaves both repositories releasable. PRs 1–5 are
behaviour-neutral; goldens must be byte-identical. PRs 6–8 change behaviour off reference scale.

### PR 1 — Scale-invariance drift baseline
`branch: agent/scale-drift-baseline` · behaviour-neutral · **blocks everything else**

Rebuild every golden fixture at 0.1×, 1×, 10× and 100× and assert each record scales
proportionally. Most families will not. Record exactly which recogniser fails at which factor in
a pinned `tests/scale/drift-baseline.json`; the test asserts current behaviour *matches that
baseline*, so CI is green and the defect is documented rather than hidden.

- [ ] `tests/scale/` harness parameterised over the 17 fixtures × 4 scale factors
- [ ] `drift-baseline.json` committed with the measured failures
- [ ] Test fails if drift *appears* or *disappears* without updating the baseline

**Done when:** the baseline file is the epic's progress bar — every later PR deletes entries.

### PR 2 — ADR 0008 and the classification
`branch: agent/adr-tolerance-policy` · behaviour-neutral

- [ ] `docs/adr/0008-tolerance-scaling-policy.md`: the six kinds, the relative-plus-floor form,
      the reference-scale calibration rule, and why direction gates and rounding are excluded
- [ ] Full literal inventory table (confirm the ~39 count)
- [ ] Naming convention: `*_TOL`/`*_MARGIN`/`*_MIN_*` = length · `*_FRAC`/`*_RATIO` = dimensionless
      · `*_ANGLE` = angle · `*_EPS` = machine
- [ ] `tests/test_architecture.py`: assert every module-level tolerance constant matches the
      convention, so the classification cannot rot

### PR 3 — Hoist inline literals to named constants
`branch: agent/name-inline-tolerances` · behaviour-neutral · goldens byte-identical

The honest "remove the magic numbers" PR, with no semantic risk.

- [ ] `_hole_features`: three inline `0.01` diameter comparisons → `_DIA_MATCH_TOL`
- [ ] `chamfers`, `fillets`, `plates`, `pads`, `levels`, `polygonal_bosses`: `0.99` / `0.05` /
      `0.02` / `0.01` direction gates → named `_AXIS_ALIGNED`, `_NORMAL_FLAT` etc.
- [ ] `chamfers`/`fillets`: the `0.05` interior-probe fraction → `_PROBE_FRAC`
- [ ] `_recess_core._recognise_corner_notches(tol=0.5)` → module constant
- [ ] Rename `_BC_SPACING_TOL` → `_BC_SPACING_FRAC` (it is already relative)

### PR 4 — Shared scaling primitive
`branch: agent/tolerance-primitive` · behaviour-neutral

- [ ] `_geometry.length_tol(nominal, *, rel, floor)` generalising `_pattern_tol`
- [ ] `_geometry.part_scale(part)` — one definition of "part envelope", currently spelled three
      different ways across `profiled_bores`, `repeating_profiles` and `levels`
- [ ] Adopt in `_pattern_geometry` only, proving equivalence: its numbers are unchanged
- [ ] ADR 0007 seam table and `test_architecture.py` updated for the new edges

### PR 5 — Public tolerance keywords accept a derived default
`branch: agent/tolerance-keyword-sentinel` · behaviour-neutral

- [ ] `tol: float | None = None` on the five public recognisers; `None` resolves to today's exact
      constant, so behaviour is unchanged
- [ ] `STEP_LADDER_BOUNDARY_MARGIN` retained as the documented explicit override
- [ ] Capability manifest regenerated; schema/signature delta reviewed
- [ ] Release note: signature widened, defaults unchanged

### PR 6 — Apply scaling: hole and cylinder family
`branch: agent/scale-hole-tolerances` · **behaviour change**

`_cylinder_substrate` · `_hole_features` · `countersinks` · `_hole_patterns`

- [ ] `_STACK_GAP_TOL`, `_DIA_MATCH_TOL`, `_TOL`, `_COAXIAL_TOL`, `_HOLE_DIA_TOL`,
      `_HOLE_AXIS_TOL`, `_HOLE_MOUTH_TOL` calibrated to relative-plus-floor
- [ ] Goldens byte-identical at 1× (verify)
- [ ] Drift-baseline entries for these families removed
- [ ] New fixture: micro (2 mm) and large (2 m) hole plate

### PR 7 — Apply scaling: recess family
`branch: agent/scale-recess-tolerances` · **behaviour change**

`_recess_core` · `_recess_patterns`

- [ ] `_MERGE_TOL`, `_FLOOR_TOL`, `_VOID_INSET`, `_END_RADIUS_TOL`, `_CAP_CLUSTER_TOL`, notch tol
- [ ] Highest-risk PR in the epic — `_recess_core` is 987 lines at 92% coverage and these
      tolerances interact (merge feeds collapse feeds obround extension). Land it alone.
- [ ] Goldens byte-identical at 1×; drift entries removed; multi-scale slot/pocket fixture

### PR 8 — Apply scaling: prismatic and turned families
`branch: agent/scale-prismatic-tolerances` · **behaviour change**

`levels` · `plates` · `pads` · `chamfers` · `fillets` · `flats` · `grooves` · `turned` ·
`polygonal_bosses`

- [ ] Per-module calibration; `flats` (6 constants) and `grooves` (4) carry the most
- [ ] `STEP_LADDER_BOUNDARY_MARGIN = 0.6` becomes scale-derived — it is public and documented in
      the README and ADR 0006; both need updating
- [ ] Goldens byte-identical at 1×; drift baseline reduced to empty

## Release gate

- [ ] `drift-baseline.json` is empty; the scale-invariance test asserts invariance directly
- [ ] ADR 0008 marked accepted
- [ ] README tolerance/units precondition documented
- [ ] `0.3.0a1` prerelease published; Draftwright validates against it via the downstream canary
- [ ] Release note states the behaviour change explicitly, with the reference-scale guarantee
- [ ] `0.3.0` promoted; Draftwright lock moved to the stable artifact

## Explicitly out of scope

- Changing `round(x, 4)` record precision or any serialisation rounding
- Scaling direction gates, ratios, angles or repeat counts
- Unit inference from the STEP file — the package receives build123d objects and has no unit
  metadata; the reference scale comes from the part envelope
- Adding new recogniser families
