# b123d-recognisers

Deterministic, geometry-only feature recognition for build123d solids and imported STEP models.

This is the standalone Apache-2.0 recognition layer extracted from
[Draftwright](https://github.com/pzfreo/draftwright). It reports immutable geometric records and
does not own drawing, manufacturing, editing, or consumer-cache policy.

## Usage

Run the complete shared recognition orchestration when a consumer needs one consistent inventory:

```python
from b123d_recognisers import build_recognition_result

result = build_recognition_result(part)
for hole in result.holes:
    print(hole.diameter, hole.depth, hole.through)
```

Individual recognisers remain public for focused consumers. Reusable evidence is explicitly
injected so it is not rediscovered:

```python
from b123d_recognisers import analyse_cylinders, recognise_hole_patterns, recognise_holes

cylinders = analyse_cylinders(part)
holes = recognise_holes(part, cyls=cylinders)
patterns = recognise_hole_patterns(holes)
```

Every `recognise_*` function returns a deterministic list of frozen dataclass records. Records
provide `to_dict()` projections containing only JSON-serialisable geometry values. See
[`docs/adr/0002-uniform-deterministic-recogniser-contract.md`](docs/adr/0002-uniform-deterministic-recogniser-contract.md)
for the complete contract.

## Migrated behavior

Version `0.1.0` preserves the recognition behavior of Draftwright commit
`3fe20b0f71a71deced06b310943dd44cc66e355e`. The migration includes every public recogniser,
shared cylinder/level substrates, the aggregate result, and `feature_census`. There are no
intentional recognition changes. The checked-in semantic corpus records and continuously verifies
the compatibility boundary; see [`migration/PARITY.md`](migration/PARITY.md).

The dependency direction is:

```text
consumer → b123d-recognisers → build123d/OCP
```

The runtime package does not import Draftwright and does not return build123d or OCP objects in
public feature records.

## Licence

Apache License 2.0. See [`LICENSE`](LICENSE), [`NOTICE`](NOTICE), and
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
