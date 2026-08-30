"""Evidence contracts for the issue #320 corpus transition classifier."""

from b123d_recognisers._recess_records import Pocket, Slot
from tools.audit_rectangular_recess_frame_transitions import _containing_blind_pocket


def _pocket(*, body_key=(1.0,), w_center=0.0, width=2.0) -> Pocket:
    return Pocket("x", "z", width, 8.0, 12.0, w_center, -4.0, 4.0, -6.0, 6.0, 1, False, body_key)


def _slot(*, body_key=(1.0,), w_center=0.0) -> Slot:
    # The orthogonal projection occupies a centred subset of the blind Pocket volume.
    return Slot("x", "y", 2.0, 12.0, w_center, -6.0, 6.0, -2.0, 2.0, body_key)


def test_alternate_slot_projection_requires_one_same_body_containing_blind_pocket() -> None:
    pocket = _pocket()
    assert _containing_blind_pocket(_slot(), (pocket,)) is pocket


def test_center_coincidence_alone_does_not_classify_an_alternate_projection() -> None:
    assert _containing_blind_pocket(_slot(body_key=(2.0,)), (_pocket(),)) is None
    assert _containing_blind_pocket(_slot(body_key=None), (_pocket(body_key=None),)) is None
    assert _containing_blind_pocket(_slot(), (_pocket(w_center=5.0),)) is None
    assert _containing_blind_pocket(_slot(), (_pocket(width=1.0),)) is None
    assert _containing_blind_pocket(_slot(), (_pocket(), _pocket())) is None
