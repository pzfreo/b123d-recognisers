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

## Scope

**Only the ~39 scale-dependent length tolerances.** Of the ~189 non-trivial numeric literals in
the package, the rest are dimensionless ratios, unit-vector direction gates, angles, counts, tuple
indices, machine epsilons and record rounding. Naming those is
[issue #42](https://github.com/pzfreo/b123d-recognisers/issues/42); **scaling** any of them would
be a defect, not a fix. This epic touches a literal only where it is a length that should track
part size.

The epic still has to *identify* which constants are lengths — that classification lives in
ADR 0008 (PR 2) and is the only overlap with #42.

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

- [ ] `docs/adr/0008-tolerance-scaling-policy.md`: the relative-plus-floor form, the
      reference-scale calibration rule, and the boundary against #42 — why unit-vector gates,
      angles, counts and record rounding are never scaled
- [ ] The one inventory this epic needs: which module-level constants are **lengths** (confirm the
      ~39 count). Everything else is classified in #42
- [ ] `tests/test_architecture.py`: assert every constant the ADR lists as a length is consumed
      through the scaling primitive once PR 4 exists, so a new raw millimetre constant cannot
      reappear unnoticed

### PR 3 — Name the inline length tolerances
`branch: agent/name-inline-tolerances` · behaviour-neutral · goldens byte-identical

Narrow prerequisite for PRs 6–8: a tolerance cannot be scaled while it is an inline literal. Only
literals that are **lengths** are touched here; the direction gates on adjacent lines are #42.

- [ ] `_hole_features`: three inline `0.01` diameter comparisons → `_DIA_MATCH_TOL`
- [ ] `_recess_core._recognise_corner_notches(tol=0.5)` → module constant
- [ ] `pads`: the `0.005 * dx * dy` area term → named constant (it is an area, not a length —
      record in ADR 0008 how it scales)

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

- Naming the non-length literals — direction gates, ratios, angles, counts, epsilons.
  That is [#42](https://github.com/pzfreo/b123d-recognisers/issues/42)
- Changing `round(x, 4)` record precision or any serialisation rounding
- Scaling direction gates, ratios, angles or repeat counts — these are unitless by construction
- Unit inference from the STEP file — the package receives build123d objects and has no unit
  metadata; the reference scale comes from the part envelope
- Adding new recogniser families

## Related, not included

These came out of the same review and are **not** part of this epic:

- **STEP round-trip goldens.** No test imports a STEP file; all 17 fixtures are build123d CSG
  solids. Separate issue — but note the overlap: PR 1's harness rebuilds every fixture under a
  transform, and a STEP round-trip harness rebuilds every fixture through an export/import. Build
  the fixture-transform plumbing in PR 1 so the round-trip work can reuse it.
- Prose and `__annotations__` assertions in `test_published_prose.py` / `test_architecture.py`
- Coverage concentration: `_geometry.py` 73%, `grooves.py` 84%, `polygonal_bosses.py` 85%
- Function length: `polygonal_bosses._recognise_one` at 227 lines and 21 others over 60
- `census.py` line 10: a sentence starting "Progress" runs into the next line
