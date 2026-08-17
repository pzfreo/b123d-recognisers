# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""Recognition counts on the NIST MBE PMI complex test cases.

These are real mechanical parts, 550–1170 mm across, carrying features down to a millimetre. That
combination — a large part with small features — is what the synthetic golden corpus does not
contain, and it is what issue #72 found: 0.2.3 scaled minimum-evidence gates to the part and lost
records in nineteen places across six parts, gaining in none.

The counts below are 0.2.2 behaviour as reported from downstream, and they are the reason the
gates in ADR 0008 are split into tolerances (which scale) and thresholds (which do not).

**Vendored, since 0.2.6.** These ten AP203 geometry-only files live in ``tests/corpus/nist``, so
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


def _step_for(stem: str) -> Path:
    matches = sorted(Path(_DIR).glob(f"{stem}_*.stp"))
    if not matches:
        pytest.fail(f"no STEP file matching {stem}_*.stp in {_DIR}")
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


#: The four remaining vendored parts. They have no downstream-reported baseline, so pinning
#: counts for them would be inventing a golden out of today's behaviour and calling it
#: evidence. What can be asserted honestly is weaker and still worth having: recognition
#: completes on a real 550-1170 mm part and returns records, which is the failure mode a
#: large part with millimetre features actually produces.
_UNBASELINED = ("nist_ftc_07", "nist_ftc_08", "nist_ftc_09", "nist_ftc_10")


@pytest.mark.parametrize("stem", _UNBASELINED, ids=lambda s: s.removeprefix("nist_"))
def test_recognition_completes_on_the_remaining_vendored_parts(stem):
    """Recognition runs to completion and finds features, without a pinned expectation.

    Deliberately not count assertions. The six above are pinned because a downstream report
    gave them a value to be pinned *to*; these four would only be pinned to whatever this
    package happens to do today, which tells a future reader nothing about whether that was
    ever right. If a baseline for them appears, it belongs in ``EXPECTED`` with the others.
    """

    result = build_recognition_result(import_step(str(_step_for(stem))))

    assert result.holes, f"{stem}: a NIST test case with no holes means recognition fell over"
    assert result.step_levels
    assert result.fillets or result.chamfers
