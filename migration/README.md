# Recognition migration audit boundary

`source-baseline.json` pins the only Draftwright source from which parity fixtures and
implementation code may be extracted. Each entry records the Git blob at the selected clean
commit, so a path with different contents is not the baseline even if a nearby checkout uses the
same filename.

The baseline deliberately includes all recognition modules and only the `feature_census()`
function from `score.py`. Draftwright's drawing, model, declaration, annotation, lint, repair,
export, and consumer-cache code is outside this package boundary.

Golden-capture tooling must verify the repository URL, commit, clean worktree, and listed blobs
before reading baseline code. Ordinary tests and CI must consume checked-in canonical goldens and
must never regenerate them from an adjacent Draftwright checkout.

Verify a deliberately checked-out baseline before capture with:

```bash
uv run python tools/verify_source_baseline.py --draftwright ../draftwright-baseline
```
