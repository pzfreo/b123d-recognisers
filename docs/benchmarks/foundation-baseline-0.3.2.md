# Geometry-foundation baseline at 0.3.2.dev0

This is the pre-semantic-change baseline for epic 0004 / issue #178. The recognition source is
commit `44e74df`; the exact F0 branch base is docs-only merge `e70b166`. F0 adds audit tooling,
tests, and documentation only. It changes no file under `src/` and no public result.

## Existing equivalence and adversary contract

The baseline already pins the representations F0 must preserve:

- `tests/test_step_round_trip.py` proves every golden survives STEP round-trip, proves analytic
  plane/cylinder typing survives, and contrasts it with the current package-wide empty result for
  an equivalent NURBS-only solid;
- `tests/test_arcs.py` and `tests/test_passages.py` pin smooth blend-chain and fragmented-boundary
  behavior;
- `tests/test_shared_reductions.py` hands oblique planes to families while pinning their current
  explicit refusal, and `tests/test_angled_steps.py` pins the supported bounded oblique family;
- `tests/test_golden_parity.py` and `tests/test_reconcile_identity.py` pin traversal and identity
  permutations;
- mirror behavior is pinned in `tests/test_recognition.py` and family adversaries;
- `tests/test_scale_invariance.py`, `tests/test_large_part_small_features.py`, and family-specific
  scale tests pin scale behavior and the tolerance/minimum-evidence distinction.

These are baseline outcomes, not promises that F1–F4b must leave unsupported geometry unsupported.
A later semantic child may change one only through its own development evidence, two independent
reviews, and—when applicable—the sealed holdout gate.

The exact focused freeze on the F0 branch is:

| Evidence surface | Command selection | Result |
| --- | --- | --- |
| semantic goldens, traversal and STEP/native-vs-NURBS boundary | `test_golden_*` plus `test_step_round_trip.py` | 56 passed |
| blend, oblique, traversal, mirror, identity and scale adversaries | eight named baseline modules listed above | 291 passed |
| NIST CTC real-part corpus | `test_nist_ctc_corpus.py` | 10 passed |
| MFCAD++ development and already-revealed holdout | `test_mfcadpp_corpus.py test_mfcadpp_holdout.py` | 16 passed |
| vendored turned real parts and turned chamfers | `test_turned_real_part.py test_turned_chamfers.py` | 25 passed |
| public recogniser, capability-manifest and built-wheel contract | `test_recogniser_contract.py test_capability_manifest.py test_package.py` | 71 passed |

The selections overlap the full suite by design. They are listed separately so a later child can
name the exact evidence surface it changed; their counts must not be summed into a second suite
total. MFCAD++ is synthetic. NIST and the three turned parts are real-part evidence.

The focused results above were produced by these exact commands:

```bash
uv run pytest -q --no-cov tests/test_golden_data.py tests/test_golden_fixtures.py \
  tests/test_golden_parity.py tests/test_golden_support.py tests/test_step_round_trip.py
uv run pytest -q --no-cov tests/test_arcs.py tests/test_passages.py \
  tests/test_shared_reductions.py tests/test_angled_steps.py tests/test_golden_parity.py \
  tests/test_reconcile_identity.py tests/test_recognition.py tests/test_scale_invariance.py \
  tests/test_large_part_small_features.py
uv run pytest -q --no-cov tests/test_nist_ctc_corpus.py
uv run pytest -q --no-cov tests/test_mfcadpp_corpus.py tests/test_mfcadpp_holdout.py
uv run pytest -q --no-cov tests/test_turned_real_part.py tests/test_turned_chamfers.py
uv run pytest -q --no-cov tests/test_recogniser_contract.py \
  tests/test_capability_manifest.py tests/test_package.py
```

## Exact commands and convention

Run from the exact revision under test:

```bash
uv sync --frozen
uv run pytest -q
uv run ruff check src tests tools
uv run mypy src
uv run python tools/generate_capability_manifest.py --check
uv run python tools/benchmark_recognition.py \
  --implementation package --workload composite --iterations 5
uv run python tools/benchmark_recognition.py \
  --implementation package --workload census --iterations 3
```

The performance contract is the checked-in
[`recognition-budget.json`](recognition-budget.json): minimum of samples on the shared epic
development host, with both elapsed time and peak RSS reported. The existing ceilings are not
rebased to make F0 or a later child pass. Synthetic corpus, real-part, package-contract, static,
golden and performance evidence must remain separate in issue/PR reporting.

## Exact pre-change result

On commit `e70b166`, with the repository's frozen dependencies:

- Python 3.10.21 full suite: **877 passed**, **96.39%** coverage, 875.66 seconds;
- Ruff: clean; mypy: clean; capability-manifest regeneration: deterministic;
- composite, Python 3.10.21: minimum **2.506 s**, median 2.648 s, peak 455,672 KiB;
- census, Python 3.10.21: minimum **134.165 s**, median 136.360 s, peak 498,540 KiB.

The composite result is below its 2.698-second ceiling. The census run is above the 109.651-second
ceiling even though this revision is the unmodified baseline. A clean Python 3.12.14 rerun also
failed at **134.278 s** minimum, 138.523 s median and 531,332 KiB peak. That is recorded as an
observed baseline gate failure rather than hidden or used to enlarge the budget. F0 changes no
recognition or benchmark source, and the budget remains untouched; a later performance decision
must compare the same workload on a controlled host rather than bless a larger number here.
