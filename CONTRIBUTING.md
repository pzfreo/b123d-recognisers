# Contributing

Contributions are welcome. By intentionally submitting a contribution for inclusion in this
project, you agree that it is provided under the Apache License 2.0, as described by section 5 of
that licence, unless you explicitly state otherwise in writing.

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

```bash
uv sync --dev
uv run ruff check .
uv run pytest
```

