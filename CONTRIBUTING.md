# Contributing

Contributions are welcome. By intentionally submitting a contribution for inclusion in this
project, you agree that it is provided under the Apache License 2.0, as described by section 5 of
that licence, unless you explicitly state otherwise in writing.

Changes to a recogniser or public record follow the tests-first
[`docs/delivery-protocol.md`](docs/delivery-protocol.md). Start with the recogniser issue template,
declare every downstream capability state, and run its two-checkout compatibility command before
either repository merges.

Every package pull request also runs the single-job **Draftwright downstream canary**. It resolves
Draftwright `main` to an exact commit, builds the candidate wheel, runs the same bounded contract
harness, and records both commits, the manifest digest, and wall time in the job summary. A weekly
run catches later consumer drift. This complements the package platform matrix; it does not copy or
rerun Draftwright's full matrix.

## Architectural rules

- Recognition is geometry-only: no drawing, editing-session, CAM-operation or UI policy.
- Public results are immutable, typed and serialisable without leaking build123d/OCP objects.
- A base recogniser accepts `part` first and keyword-only tuning or injected dependencies.
- A derived recogniser is a pure function over already-recognised records.
- Recognisers do not rerun sibling recognisers; orchestration computes shared evidence once.
- Empty means confidently absent within supported topology. Ambiguous and unsupported cases are
  explicit diagnostics.
- Changes to a load-bearing contract require an ADR update.

## Local checks

Mypy 1.x on Python 3.12 is the supported type checker. Python 3.10 compatibility is enforced by
the runtime CI matrix and Ruff's `py310` syntax target. `uv run mypy` checks every typed implementation body
with incomplete private definitions admitted as the incremental baseline. That allowance does
not extend to the published boundary: `tests/test_public_typing.py` independently rejects any
missing, bare-container, or direct `Any` annotation on an exported function, class method,
property, or dataclass field,
and `tests/typing/public_consumer.py` is checked in strict mode against the built wheel. Keep all
three layers green when changing public types.

```bash
uv sync --dev
uv run ruff check .
uv run mypy
uv run pytest
```

`uv run pytest` is also the coverage measurement used by CI. It records line and branch coverage,
prints missing branches, writes `coverage.xml`, and fails below the evidence-based 91.4% combined
floor. The floor was set from a clean Python 3.10 run at 91.47% combined coverage (93.44% lines and
85.48% branches) before the focused profiled-bore tests were added. Raise the floor when coverage
improves durably; do not weaken it or replace behavior assertions with execution-only tests.
