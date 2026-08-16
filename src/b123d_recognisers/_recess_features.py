# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Public slot, pocket, and channel recognisers over one shared recess core."""

from b123d_recognisers._recess_core import (
    _body_scoped_records,
    _channel_sort_key,
    _recognise_channels_one,
    _recognise_pockets_one,
    _recognise_slots_one,
    _region_center,
)
from b123d_recognisers._recess_records import Channel, Pocket, Slot
from b123d_recognisers._typing import Part


def recognise_slots(part: Part) -> list[Slot]:
    """Recognise enclosed through-slots independently within each solid in *part*.

    Returns a list of :class:`Slot`, one per physical feature, in a
    deterministic order (co-located candidate pairs within a solid are merged,
    keeping the narrower width). See the module docstring for the recognition
    predicate and its deliberately narrow scope. Obround slots too stubby for
    their flat walls to pair are recovered from their end caps.

    A compound is scanned per solid so faces from separate components cannot
    combine into a fictitious slot across the gap between them.
    """
    solids = list(part.solids())
    sources = solids if len(solids) > 1 else [part]
    slots = _body_scoped_records(sources, _recognise_slots_one)
    return sorted(slots, key=lambda slot: (slot.width, _region_center(slot)))


def recognise_pockets(part: Part) -> list[Pocket]:
    """Recognise blind rectangular recesses independently within each solid.

    The blind counterpart of :func:`recognise_slots`: the same facing-rectangular-wall
    candidate scan, but keeping the pairs a floor caps. The depth (open-face-to-floor
    extent) is read from the axis the floor is normal to -- see
    :func:`_pocket_candidate` -- not from a size heuristic, so a pocket deeper than it
    is long is dimensioned correctly. A compound is scanned per solid so separate
    components cannot supply walls or floors for one fictitious recess.
    """
    solids = list(part.solids())
    sources = solids if len(solids) > 1 else [part]
    pockets = _body_scoped_records(sources, _recognise_pockets_one)
    return sorted(pockets, key=lambda pocket: (pocket.width, _region_center(pocket)))


def recognise_channels(part: Part) -> list[Channel]:
    """Recognise full-span floored channels independently within each solid.

    This is deliberately separate from :func:`recognise_pockets`: a channel's length
    and depth participate in the surrounding envelope/plate scheme, while only its
    wall-to-wall width is an independent defining measurement. Body-local bounds prove
    that the channel reaches the ends of the same solid whose faces bound it.
    """
    solids = list(part.solids())
    sources = solids if len(solids) > 1 else [part]
    channels = [channel for solid in sources for channel in _recognise_channels_one(solid)]
    return sorted(channels, key=_channel_sort_key)
