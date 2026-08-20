# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""How the claiming families do on geometry no predicate here was shaped by.

``tests/corpus/mfcadpp`` is the *design* corpus: it found the chamfer-versus-angled-step
defect, predicates were changed until it was happy, and every figure it produces is therefore
a figure about geometry this package has already been fitted to. That is worth having and it
is not a generalisation estimate. This module reads a second corpus, drawn from a split the
design set cannot overlap and covering the twenty MFCAD++ classes the design set does not
target, and scored once — after the last predicate change, never before one.

**What the first draw found.** The same rule drew a development set first, and one model in it
carried a right-triangular pocket whose hypotenuse satisfied every gate ``recognise_angled_steps``
applied. It was reported as a step, at 87% precision against the design corpus's 100%. The gate
that now rejects it is ``material_beyond_corner``, and
``test_a_right_triangular_pocket_wall_is_not_an_angled_step`` is the isolated case. That
development set is spent and is not vendored; what is vendored is the *next* draw, which had
no part in the fix.

**The measurement, over 33 models and 1,037 labelled faces.** Angled steps: 8 records, every one
on a face MFCAD++ labels a triangular blind step. Stock: 226 faces, none claimed by anything.
Chamfers: 2 records, both on faces labelled *triangular through slot* — a V-notch across a
convex corner, which is a chamfer by this package's definition and a slot by MFCAD++'s. That
is a taxonomy difference and was deliberately not "fixed"; changing a predicate to satisfy it
would have spent this draw the way the first one was spent.

The per-label shares are recorded in ``corpus/mfcadpp_holdout/MANIFEST.json``'s sibling
tooling rather than asserted here: recall against MFCAD++'s taxonomy is bounded by which
families claim at all, so a share is a statement about the ledger as much as the recogniser.
What is asserted is what a share cannot excuse -- a claim on stock is wrong whatever the
taxonomy, and a step on a recess wall is the defect the held-out draw exists to catch.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))

from per_face_scan import LABELS, scan  # noqa: E402

CORPUS = Path(__file__).parent / "corpus" / "mfcadpp_holdout"
#: As for the design corpus: the sdist ships this module but not the STEP it reads.
pytestmark = pytest.mark.skipif(
    not (CORPUS / "MANIFEST.json").is_file(),
    reason="the vendored MFCAD++ hold-out subset is excluded from the sdist",
)
STOCK = "Stock"
TRIANGULAR_BLIND_STEP = "Triangular blind step"


@pytest.fixture(scope="module")
def scored():
    """One scan of the hold-out corpus. Slow, so module-scoped and shared."""

    return scan(CORPUS)


@pytest.fixture(scope="module")
def manifest():
    return json.loads((CORPUS / "MANIFEST.json").read_text(encoding="utf-8"))


def test_every_vendored_model_is_scored(scored, manifest):
    """No model quietly dropped, which is what a skip for a failed precondition would be.

    ``scan`` skips a model whose label count and face count disagree, because the join it
    performs would be meaningless there. A hold-out figure computed over a silently smaller
    corpus than the one on disk is the kind of number that reads as evidence and is not, so
    the precondition every vendored model was selected under is asserted rather than assumed.
    """

    assert scored["skipped"] == 0
    assert scored["models"] == len(manifest["models"])


def test_no_claiming_family_claims_a_stock_face(scored):
    """The negative control, and the one assertion no taxonomy argument can soften.

    Stock is the unmachined remainder of the billet. A record whose defining face is stock is
    a feature reported where none was cut, and it would be wrong under any naming convention.
    226 of the 1,037 labelled faces here are stock and nothing claims one.
    """

    stock = next(k for k, v in LABELS.items() if v == STOCK)
    assert scored["faces_covered"].get(stock, 0) == 0
    assert scored["faces_per_label"][stock] > 0, "a control that is empty proves nothing"


def test_every_angled_step_on_unseen_geometry_is_a_triangular_blind_step(scored):
    """Precision 8/8, and the evidence that the far-corner gate generalises.

    The development draw scored 14 of 16 before the gate and 14 of 15 after it. This draw is
    the claim that the gate was a fix rather than a fit: it was never consulted while the gate
    was designed, it carries 48 triangular-pocket faces and 22 slanted-through-step faces for
    the family to go wrong on, and it goes wrong on none of them.
    """

    claimed = scored["claimed"].get("AngledStep", {})
    assert claimed, "no angled steps at all would make the precision figure vacuous"
    off_target = {
        LABELS[int(label)]: count
        for label, count in claimed.items()
        if LABELS[int(label)] != TRIANGULAR_BLIND_STEP
    }
    assert off_target == {}
