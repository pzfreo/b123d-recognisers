# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Public slot, pocket, and channel recognisers over one shared recess core."""

from __future__ import annotations

from functools import partial

from b123d_recognisers._adjacency import FaceEdges
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._recess_core import (
    _channel_sort_key,
    _recognise_channels_one,
    _recognise_pockets_one,
    _recognise_slots_one,
)
from b123d_recognisers._recess_records import Channel, Pocket, Slot
from b123d_recognisers._recess_reduce import _body_scoped_pairs, _Claims, _region_center
from b123d_recognisers._typing import Part


def recognise_slots(
    part: Part, *, face_edges: FaceEdges | None = None, ledger: ClaimLedger | None = None
) -> list[Slot]:
    """Recognise enclosed through-slots independently within each solid in *part*.

    Returns a list of :class:`Slot`, one per physical feature, in a
    deterministic order (co-located candidate pairs within a solid are merged,
    keeping the narrower width). See the module docstring for the recognition
    predicate and its deliberately narrow scope. Obround slots too stubby for
    their flat walls to pair are recovered from their end caps.

    A compound is scanned per solid so faces from separate components cannot
    combine into a fictitious slot across the gap between them.

    *ledger* is injected the way *face_edges* is, and records which faces each returned slot was
    built from -- its two walls, plus the walls of every candidate folded into it: the same void
    seen through its other wall pair, and the arms a crossing channel split it into. It changes
    nothing about what is returned: claims are written and never read here, so no slot's
    existence can depend on another family having run. It exists so a second family can ask
    whether it is describing the same void, instead of comparing record coordinates.

    *ledger*'s graph must have been built from *part*; a face that does not resolve against it
    is refused rather than silently claiming nothing, because an empty ledger would otherwise
    read as "no overlap" to the reconciler it exists to serve.

    A slot recovered from its end caps rather than from paired flat walls claims nothing, and is
    absent from the ledger. Its evidence is two cylindrical caps, which are not walls, and no
    consumer needs it: a caller reconciling against a ring of planar faces cannot be looking at
    a slot whose ends are round.
    """
    solids = list(part.solids())
    sources = solids if len(solids) > 1 else [part]
    claims: _Claims | None = {} if ledger is not None else None
    pairs = _body_scoped_pairs(
        sources,
        partial(
            _recognise_slots_one,
            face_edges=face_edges,
            graph=None if ledger is None else ledger.graph,
            claims=claims,
        ),
        claims,
    )
    pairs.sort(key=lambda pair: (pair[0].width, _region_center(pair[0])))
    if ledger is not None:
        for slot, nodes in pairs:
            if nodes:
                ledger.add_defining(slot, nodes)
    return [slot for slot, _ in pairs]


def recognise_pockets(
    part: Part, *, face_edges: FaceEdges | None = None, ledger: ClaimLedger | None = None
) -> list[Pocket]:
    """Recognise blind rectangular recesses independently within each solid.

    The blind counterpart of :func:`recognise_slots`: the same facing-rectangular-wall
    candidate scan, but keeping the pairs a floor caps. The depth (open-face-to-floor
    extent) is read from the axis the floor is normal to -- see
    :func:`_pocket_candidate` -- not from a size heuristic, so a pocket deeper than it
    is long is dimensioned correctly. A compound is scanned per solid so separate
    components cannot supply walls or floors for one fictitious recess.

    *ledger* is injected the way it is on :func:`recognise_slots`, and changes nothing about
    what is returned: claims are written and never read here. What a pocket claims depends on
    how it was found. From opposed walls it claims the two walls, and *not* the floor, which
    only had to exist -- the same line the through-slot draws, since the depth is the walls'
    own overlap rather than the floor's position. From a corner notch it claims the floor too,
    because that path iterates floors and reads the notch's footprint off the one it finds. A
    stubby obround pocket recovered from its cylindrical end caps claims nothing and is absent
    from the ledger, as its through-slot counterpart is.

    *ledger*'s graph must have been built from *part*; a face that does not resolve is refused
    rather than silently claiming nothing.
    """
    solids = list(part.solids())
    sources = solids if len(solids) > 1 else [part]
    claims: _Claims | None = {} if ledger is not None else None
    pairs = _body_scoped_pairs(
        sources,
        partial(
            _recognise_pockets_one,
            face_edges=face_edges,
            graph=None if ledger is None else ledger.graph,
            claims=claims,
        ),
        claims,
    )
    pairs.sort(key=lambda pair: (pair[0].width, _region_center(pair[0])))
    if ledger is not None:
        for pocket, nodes in pairs:
            if nodes:
                ledger.add_defining(pocket, nodes)
    return [pocket for pocket, _ in pairs]


def recognise_channels(
    part: Part, *, face_edges: FaceEdges | None = None, ledger: ClaimLedger | None = None
) -> list[Channel]:
    """Recognise full-span floored channels independently within each solid.

    This is deliberately separate from :func:`recognise_pockets`: a channel's length
    and depth participate in the surrounding envelope/plate scheme, while only its
    wall-to-wall width is an independent defining measurement. Body-local bounds prove
    that the channel reaches the ends of the same solid whose faces bound it.

    *ledger* is accepted but **never written to**: this family claims nothing, because no rule
    needs to ask what a channel was built from. What the parameter is for is the *graph* --
    `_planar_faces` reads each face's material-side normal from it, and a family without one
    builds its own. Passing the run's keeps a census to a single graph rather than one per solid
    for this family alone.
    """
    solids = list(part.solids())
    sources = solids if len(solids) > 1 else [part]
    graph = None if ledger is None else ledger.graph
    channels = [
        channel
        for solid in sources
        for channel in _recognise_channels_one(solid, face_edges, graph)
    ]
    return sorted(channels, key=_channel_sort_key)
