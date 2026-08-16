# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Recognition of slots, pockets, channels, and their derived patterns.

This module is the supported compatibility facade; implementation modules remain private.
"""

from b123d_recognisers._recess_features import (
    recognise_channels,
    recognise_pockets,
    recognise_slots,
)
from b123d_recognisers._recess_patterns import (
    recognise_pocket_patterns,
    recognise_slot_patterns,
)
from b123d_recognisers._recess_records import (
    Channel,
    Pocket,
    PocketArray,
    PocketGrid,
    Slot,
    SlotArray,
    SlotGrid,
)
from b123d_recognisers._typing import Vector3 as Vector3

__all__ = [
    "Channel",
    "Pocket",
    "PocketArray",
    "PocketGrid",
    "Slot",
    "SlotArray",
    "SlotGrid",
    "recognise_channels",
    "recognise_pocket_patterns",
    "recognise_pockets",
    "recognise_slot_patterns",
    "recognise_slots",
]

for _exported_name in __all__:
    globals()[_exported_name].__module__ = __name__
