# b123d-recognisers

[![CI](https://github.com/pzfreo/b123d-recognisers/actions/workflows/ci.yml/badge.svg)](https://github.com/pzfreo/b123d-recognisers/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/pzfreo/b123d-recognisers/graph/badge.svg)](https://codecov.io/gh/pzfreo/b123d-recognisers)
[![PyPI](https://img.shields.io/pypi/v/b123d-recognisers.svg)](https://pypi.org/project/b123d-recognisers/)
[![Python versions](https://img.shields.io/pypi/pyversions/b123d-recognisers.svg)](https://pypi.org/project/b123d-recognisers/)
[![License](https://img.shields.io/pypi/l/b123d-recognisers.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![mypy](https://img.shields.io/badge/mypy-checked-2A6DB2.svg)](https://mypy-lang.org/)

Recover useful engineering features from imported STEP and boundary-representation (B-Rep)
geometry.

A STEP file normally gives a CAD application faces, edges, and solids, but not the design intent
that produced them. `b123d-recognisers` analyses that topology and returns deterministic semantic
records for features such as holes and counterbores, bosses, slots, pockets, pads, fillets,
chamfers, grooves, hole and pocket patterns, and turned steps. The records contain ordinary,
JSON-serialisable geometry values rather than build123d or OCP objects.

Most recognition families classify faces by native analytic surface type, so imported geometry
should preserve its planes, cylinders and cones. STEP carries them, and every pinned fixture is
proven to survive an export and re-import unchanged. Raised Pads additionally have measured support
for exact planes re-expressed as B-splines; other B-spline families remain outside the proven
domain. Raised Pad recognition also requires exact face membership in one valid closed solid;
open shells, invalid bodies, and ambiguous or missing solid ownership return no Pad records. See
[`docs/capabilities.md`](docs/capabilities.md).

That makes the library a useful foundation for systems which inspect, classify, annotate, compare,
or modify imported CAD. For example, a STEP editor can recognise a hole, present its diameter and
axis as editable intent, and use those values to drive its own topology-editing operation. The
recognisers recover evidence; the consuming CAD system decides what that evidence means and how an
edit should be performed.

The package is Apache-2.0 licensed and independent of any drawing or editing application. It uses
build123d/OCP internally as its B-Rep kernel, but its purpose is recovering meaning from geometry
whose construction history is not available.

## Recognise an imported model

Import a STEP file with build123d, then run the shared recognition orchestration to obtain one
consistent feature inventory:

```python
from build123d import import_step
from b123d_recognisers import build_recognition_result

part = import_step("gearbox-housing.step")
result = build_recognition_result(part)

for hole in result.holes:
    print(hole.location, hole.axis, hole.diameter, hole.depth, hole.bottom)
```

`build_recognition_result()` shares intermediate geometric analysis across recognisers and is the
usual entry point for a CAD application. Its frozen result can be inspected directly or projected
to JSON-compatible dictionaries for storage, indexing, comparison, or an editing pipeline.

For bounded lifecycle explanations from the same single run, use
`build_recognition_report()`. Its immutable report distinguishes evaluated-empty families,
classification-gated families, accepted/rejected candidates and supported residual diagnostics.
It is deliberately not an exhaustive explanation of unsupported geometry; a missing diagnostic
does not prove that no unsupported feature is present.

Individual recognisers are also public when an application needs a narrower answer. Reusable
evidence can be injected explicitly so it is not rediscovered:

```python
from b123d_recognisers import analyse_cylinders, recognise_hole_patterns, recognise_holes

cylinders = analyse_cylinders(part)
holes = recognise_holes(part, cyls=cylinders)
patterns = recognise_hole_patterns(holes)
```

### Inspect geometry for declared features

CAD front ends that create a declared feature from a selected face can use the supported,
single-face inspection namespace instead of importing recogniser internals:

```python
from b123d_recognisers.inspection import AnalyticSurface, SurfaceKind, inspect_face

inspected = inspect_face(selected_face)
if isinstance(inspected.surface, AnalyticSurface):
    if inspected.surface.kind is SurfaceKind.CYLINDER:
        print(inspected.surface.parameters, inspected.anchor)
```

The manifest and [capability documentation](docs/capabilities.md#declared-feature-inspection-api)
freeze the kind-specific parameter positions and units. When an anchor is present, it is proved
in or on the selected face's actual trim, including faces with holes or concave outer boundaries.

The namespace also groups the four consumer-proven family reads: `classify_bevel` /
`BevelReject`, `cone_rims`, `read_double_d_tool`, and `floor_face_anchor`. Existing root,
family-module, and `experimental_geometry.inspect_face` imports remain exact-object compatibility
aliases. `GeometryGraph`, adjacency, blend collapse, correspondence, evidence, and reconciliation
are not part of this supported API.

`inspection_api_manifest()` returns the separately versioned, installed-wheel contract for this
roster. It does not change the recognition capability-manifest schema. See
[`docs/capabilities.md`](docs/capabilities.md#declared-feature-inspection-api).

That contract includes the closed `BevelReject.reason` values and the ordered
`read_double_d_tool()` result: `(axis, major_diameter, across_flats, origin, depth,
profile_direction)`. Diameters, origin coordinates, and depth use model-length units;
`profile_direction` is unitless and `axis` is one of `x`, `y`, or `z`.

### Recognise independently of STEP placement

Use the opt-in framed route when the same physical part must produce local coordinates independent
of its placement in the imported file:

```python
from b123d_recognisers import FramedRecognitionResult, build_framed_recognition_result

framed = build_framed_recognition_result(part)
if isinstance(framed, FramedRecognitionResult):
    print(framed.frame.gauge)
    print(framed.part.bounding_box())  # the exact local shape used for recognition
    print(framed.result.holes)  # coordinates and axis letters are local to framed.frame
```

The paired `PartFrame` converts points in either direction with `to_local()` and `to_world()`.
`framed.part` is the exact topology-preserving local working shape passed to recognition, not a
consumer reconstruction. Its evaluated coordinates agree with `framed.result`, and
`framed.frame` converts between it and the caller's input coordinates. Keep the successful
`FramedRecognitionResult` alive while using topology-bearing recognition evidence: the result owns
the identity relationship between that evidence and `framed.part`; the original input shape is a
different caller-space object.
`FULL` means geometry establishes a directed, ordered basis. `ORTHOGONAL` exposes an unobservable
discrete sign or axis interchange, and `AXIAL` exposes unobservable roll. The axes returned for a
gauged frame are deterministic representatives and must not be treated as semantic material
directions. Geometry without an analytic direction returns a typed `RefusedPartFrame`.

This route does not change `build_recognition_result()` or the caller-space meaning of its records.

Every `recognise_*` function returns a deterministic list of frozen dataclass records. Records
provide `to_dict()` projections containing only JSON-serialisable geometry values. The installed
package also exposes a versioned capability manifest so larger CAD systems can validate which
recognisers and record schemas they consume. See
[`docs/capabilities.md`](docs/capabilities.md) for the proven feature inventory and
[`docs/adr/0002-uniform-deterministic-recogniser-contract.md`](docs/adr/0002-uniform-deterministic-recogniser-contract.md)
for the complete contract.

### Project an aggregate step ladder

The aggregate owns the one geometry-only rule that chooses between Z-turned shoulders and already
filtered prismatic levels. Pass only the Z envelope it needs; no build123d object crosses this
projection boundary:

```python
z_min = part.bounding_box().min.Z
z_max = part.bounding_box().max.Z
step_zs = result.step_ladder_for_z_span(z_min, z_max)
```

The default `boundary_margin=0.6` is measured in model length units (normally millimetres) and
strictly excludes turned end faces at both ends. It can be overridden explicitly. The former
`result.step_ladder(bound_box)` call remains as a deprecated 0.2.x compatibility shim and will be
removed no earlier than 1.0.0. See
[`ADR 0006`](docs/adr/0006-explicit-step-ladder-z-span.md) for the caller inventory and boundary
decision.

## Scope

Feature recognition is deliberately separate from feature editing. This package reports geometric
facts; it does not mutate the source model, guess manufacturing intent, or prescribe a downstream
CAD representation. That boundary lets an editor, drawing engine, CAM tool, model checker, or
search/indexing service adopt the same recognition layer while retaining its own policy.

`b123d-recognisers` began as the recognition layer of
[Draftwright](https://github.com/pzfreo/draftwright), but the runtime package does not import
Draftwright and is designed for standalone use.

## Migrated behavior

The initial `0.1` release series preserves the recognition behavior of Draftwright commit
`3fe20b0f71a71deced06b310943dd44cc66e355e`. The migration includes every public recogniser,
shared cylinder/level substrates, the aggregate result, and `feature_census`. There are no feature
policy changes; one previously platform-dependent numerical axis tie is normalized to the pinned
baseline result. The checked-in semantic corpus records and continuously verifies the compatibility
boundary; see [`migration/PARITY.md`](migration/PARITY.md).

The dependency direction is:

```text
consumer → b123d-recognisers → build123d/OCP
```

The runtime package does not import Draftwright and does not return build123d or OCP objects in
public feature records.

Contributors: see [Adding a recogniser](docs/adding-a-recogniser.md) for the AAG predicate,
candidate/evidence, registry, reconciliation, and verification path.

Maintainers: see [the release guide](docs/releasing.md) for the TestPyPI-first, OIDC-only
publication process.

## Licence

Apache License 2.0. See [`LICENSE`](LICENSE), [`NOTICE`](NOTICE), and
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
