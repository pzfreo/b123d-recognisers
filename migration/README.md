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

Capture the reviewed semantic goldens only from that checkout with the manifest's explicit SHA:

```bash
uv run python tools/capture_draftwright_goldens.py \
  --draftwright ../draftwright-baseline \
  --commit 3fe20b0f71a71deced06b310943dd44cc66e355e
```

Existing `expected.json` files are never replaced unless `--overwrite` is passed explicitly.
Capture validates every fixture before writing any file, so a failed recognition or equivalence
check cannot leave a partially refreshed corpus.

Canonicalizer version 1 rounds finite floats to eight decimal places, normalises negative zero,
adds dataclass type tags, sorts mapping/set encodings, and preserves recogniser sequence order so
ordering drift remains visible. Raw CAD face handles and traversal-derived `solid_idx` values are
excluded; every other non-JSON value fails capture rather than being stringified.
