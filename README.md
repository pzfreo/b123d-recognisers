# b123d-recognisers

Deterministic, geometry-only feature recognition for build123d solids and imported STEP models.

This project is the standalone recognition layer extracted from
[Draftwright](https://github.com/pzfreo/draftwright). It reports geometric facts—features,
measurements, evidence and diagnostics—and deliberately does not decide how a consumer should
dimension, edit, manufacture or present them.

The project is being established before recognisers are migrated. The initial public contract is
recorded in [`docs/adr/`](docs/adr/README.md); the package currently exposes only its version.

## Intended API

```python
from b123d_recognisers import recognise

result = recognise(part)

for hole in result.holes:
    print(hole.diameter, hole.depth, hole.through)

for diagnostic in result.diagnostics:
    print(diagnostic.code, diagnostic.evidence)
```

Individual recognisers will remain available for focused consumers:

```python
holes = recognise_holes(part, cylinders=inventory.cylinders)
patterns = recognise_hole_patterns(holes)
```

## Project boundary

```text
build123d / OCCT shape
          ↓
geometry inventory
          ↓
feature candidates and evidence claims
          ↓
reconciliation
          ↓
immutable records + measurables + diagnostics
```

Drawing requirements, callout formatting, annotation placement, lint severity and editing policy
belong to consumers such as Draftwright and are outside this package.

## Licence

Apache License 2.0. See [`LICENSE`](LICENSE), [`NOTICE`](NOTICE), and
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

