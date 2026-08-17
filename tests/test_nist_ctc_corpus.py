# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""Recognition counts on the NIST MBE PMI complex test cases.

These are real mechanical parts, 550–1170 mm across, carrying features down to a millimetre. That
combination — a large part with small features — is what the synthetic golden corpus does not
contain, and it is what issue #72 found: 0.2.3 scaled minimum-evidence gates to the part and lost
records in nineteen places across six parts, gaining in none.

The counts below are 0.2.2 behaviour as reported from downstream, and they are the reason the
gates in ADR 0008 are split into tolerances (which scale) and thresholds (which do not).

**Vendored.** These ten AP203 geometry-only files live in ``tests/corpus/nist``, so
this module runs by default instead of skipping. It previously skipped unless
``B123D_NIST_STEP_DIR`` pointed at a local download, which meant the only tests in this project
running on real mechanical parts were off unless someone remembered to switch them on.

The reason recorded for not vendoring them does not survive reading it: ``migration/PARITY.md``
commits *the goldens* to comparing semantic record projections rather than STEP bytes, which is a
statement about what assertions may examine, not about where input geometry comes from. Nothing
here compares bytes; it compares record counts, from a file that now happens to be checked in.
NIST states the models "can be used without any restrictions", so there was never a licensing
obstacle either. ``B123D_NIST_STEP_DIR`` still overrides, for anyone testing a fuller download.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("build123d")

from build123d import import_step  # noqa: E402

from b123d_recognisers import build_recognition_result  # noqa: E402

#: Recogniser families and counts as measured on 0.2.2, per the downstream report in issue #72.
#: Only the families that moved under 0.2.3 are pinned — this is a regression guard, not a
#: capability claim, and `docs/capabilities.md` remains the place scope is stated.
EXPECTED = {
    "nist_ctc_01": {"pockets": 10, "chamfers": 3, "fillets": 8},
    "nist_ctc_02": {"pockets": 13, "fillets": 21, "step_levels": 6},
    "nist_ctc_03": {"pockets": 5, "slots": 3, "step_levels": 3, "fillets": 17},
    "nist_ctc_04": {"fillets": 24, "chamfers": 8, "pockets": 9, "slots": 6, "step_levels": 6},
    "nist_ctc_05": {"flats": 4, "pockets": 12, "fillets": 5},
    # ftc_06 is here for a different reason: it has no 0.2.2 baseline because it *crashed* on
    # 0.2.2 and 0.2.4 alike (issue #74 — ``Face.radius`` is ``None`` on a trimmed surface, and
    # a ``cast`` carried that ``None`` into the countersink bore search). These are the counts
    # from the first run that completed, pinned so the crash cannot return unnoticed.
    "nist_ftc_06": {"holes": 12, "bosses": 8, "pockets": 6, "chamfers": 5, "fillets": 3},
}

_VENDORED = Path(__file__).parent / "corpus" / "nist"
_DIR = os.environ.get("B123D_NIST_STEP_DIR") or str(_VENDORED)

#: The sdist ships these tests but not the corpus they read -- 9 MB of third-party STEP that
#: no consumer of the package needs. So absence must skip, not fail: a packager running the
#: sdist's suite is in a legitimate situation, not a broken one. Failing here was a real
#: regression from the previous behaviour, which skipped cleanly when the files were missing.
pytestmark = pytest.mark.skipif(
    not sorted(Path(_DIR).glob("*.stp")),
    reason=f"no NIST STEP files in {_DIR}; the vendored corpus is excluded from the sdist",
)


def _step_for(stem: str) -> Path:
    matches = sorted(Path(_DIR).glob(f"{stem}_*.stp"))
    if not matches:
        # A gap in the vendored corpus is this repository's bug and must fail. A gap in a
        # directory the caller pointed `B123D_NIST_STEP_DIR` at is not -- a partial download
        # is exactly what the override is for, and failing it was the same skip-versus-fail
        # mistake as shipping a corpus-less sdist that could not skip.
        if os.environ.get("B123D_NIST_STEP_DIR"):
            pytest.skip(f"no STEP file matching {stem}_*.stp in {_DIR}")
        pytest.fail(f"no STEP file matching {stem}_*.stp in the vendored corpus")
    return matches[0]


@pytest.mark.parametrize("stem", sorted(EXPECTED), ids=lambda s: s.removeprefix("nist_"))
def test_recognition_counts_match_the_reported_baseline(stem):
    """Every family that regressed under 0.2.3 is back to its 0.2.2 count.

    Counts rather than records: the downstream report is in counts, and a record-level pin would
    make this a second golden corpus without the review discipline the real one has.
    """

    result = build_recognition_result(import_step(str(_step_for(stem))))

    actual = {family: len(getattr(result, family)) for family in EXPECTED[stem]}

    assert actual == EXPECTED[stem]


#: Counts as of vendoring. **Not a correctness baseline** -- unlike ``EXPECTED``, no
#: downstream report says these are right, so they pin only what this package does today.
#: They are a change detector on real geometry, and are labelled as one so nobody later
#: mistakes them for evidence that these numbers were ever reviewed.
#:
#: The first version of this asserted only "some holes, some levels, some blend". That is
#: what it looks like when a test is written to avoid making a claim: truncating every hole
#: list to one record -- a 95% silent loss, exactly the #72 failure mode this module exists
#: for -- left all four passing.
_OBSERVED = {
    "nist_ftc_07": {"holes": 23, "step_levels": 10, "fillets": 16},
    "nist_ftc_08": {"holes": 21, "step_levels": 3, "fillets": 13},
    "nist_ftc_09": {"holes": 30, "step_levels": 15, "chamfers": 8},
    "nist_ftc_10": {"holes": 30, "step_levels": 10, "fillets": 22},
}


@pytest.mark.parametrize("stem", sorted(_OBSERVED), ids=lambda s: s.removeprefix("nist_"))
def test_recognition_on_the_remaining_vendored_parts_has_not_moved(stem):
    """A change detector, not a baseline. A moved count here needs review, not a re-pin."""

    result = build_recognition_result(import_step(str(_step_for(stem))))

    actual = {family: len(getattr(result, family)) for family in _OBSERVED[stem]}

    assert actual == _OBSERVED[stem]
