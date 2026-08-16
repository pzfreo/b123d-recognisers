# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""Recognition counts on the NIST MBE PMI complex test cases.

These are real mechanical parts, 550–1170 mm across, carrying features down to a millimetre. That
combination — a large part with small features — is what the synthetic golden corpus does not
contain, and it is what issue #72 found: 0.2.3 scaled minimum-evidence gates to the part and lost
records in nineteen places across six parts, gaining in none.

The counts below are 0.2.2 behaviour as reported from downstream, and they are the reason the
gates in ADR 0008 are split into tolerances (which scale) and thresholds (which do not).

**Opt-in.** ``migration/PARITY.md`` commits the project to comparing semantic record projections
rather than file bytes, so these STEP files are not vendored. Point ``B123D_NIST_STEP_DIR`` at a
directory holding the AP203 geometry-only files to run them:

    curl -L -o nist.zip https://www.nist.gov/document/nist-pmi-step-files
    unzip -j nist.zip '*AP203 geometry only*' -d nist-step
    B123D_NIST_STEP_DIR=$PWD/nist-step uv run pytest tests/test_nist_ctc_corpus.py

NIST states the models "can be used without any restrictions"; they are not redistributed here
only because of the byte-comparison convention, not licensing.
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
}

_DIR = os.environ.get("B123D_NIST_STEP_DIR")

pytestmark = pytest.mark.skipif(
    not _DIR, reason="set B123D_NIST_STEP_DIR to the NIST AP203 geometry-only STEP directory"
)


def _step_for(stem: str) -> Path:
    matches = sorted(Path(_DIR or ".").glob(f"{stem}_*.stp"))
    if not matches:
        pytest.skip(f"no STEP file matching {stem}_*.stp in {_DIR}")
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
