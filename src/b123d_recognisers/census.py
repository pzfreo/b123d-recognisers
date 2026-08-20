# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Feature-recognition census.

A **measurement tool**, not a recogniser: it counts how completely the recognition suite
(:mod:`b123d_recognisers`) captures a part's machined features. It produces no consumer-domain
feature or drawing policy.

The metric is a **census**: the number of features each recogniser finds, per kind. Across a
representative corpus, changes in kinds and counts expose recognition changes directly; a single
part's census states exactly what was recognised.

*Why census-only, no completeness ratio.* A ratio needs an independent denominator, and there
isn't a good one. The obvious substrate — :func:`b123d_recognisers.feature_diameters` —
is itself built from ``recognise_holes`` / ``recognise_bosses``, so diffing recognised diameters
against it is **tautological**: both sides move together, the ratio is 1.0 for every real part,
and a genuine recogniser regression drops the denominator too (so it never signals). The only
independent substrate, the raw ``analyse_cylinders`` patch list, is **noisy** — radiused slot
ends and other non-feature partial cylinders are never features, so legitimate parts would score
below 1.0 permanently. That is why :func:`feature_diameters` avoids the raw substrate. A
census is the one honest signal, so that is all this reports.

Bottom of the DAG beside the recognisers: depends only on :mod:`b123d_recognisers` and build123d.
"""

from __future__ import annotations

from collections.abc import Sequence

from b123d_recognisers import (
    analyse_cylinders,
    recognise_angled_steps,
    recognise_bosses,
    recognise_chamfers,
    recognise_channels,
    recognise_countersinks,
    recognise_fillets,
    recognise_flats,
    recognise_grooves,
    recognise_hole_patterns,
    recognise_holes,
    recognise_plates,
    recognise_pockets,
    recognise_prismatic_pockets,
    recognise_slots,
    recognise_turned_steps,
)
from b123d_recognisers._adjacency import FaceEdges, FaceGraph
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._reconcile import (
    chamfers_that_are_not_angled_steps,
    passages_that_are_not_slots,
    prismatic_pockets_that_are_not_pockets,
    steps_that_are_not_grooves,
)
from b123d_recognisers._record import Record
from b123d_recognisers._typing import Part
from b123d_recognisers.turned import TurnedProfile


def feature_census(part: Part) -> dict[str, int]:
    """The count of recognised features per kind for *part* (see module docs).

    Runs every feature recogniser once — injecting hole patterns from the recognised holes and
    one shared cylinder scan into every substrate recogniser — and returns
    ``{kind: count}`` with a stable, complete set of
    keys (a kind absent from the part reports ``0``, not a missing key). The prismatic
    *substrate* recognisers (face levels and step risers) are excluded: they feed other
    recognisers rather than being distinct machined features, and their level-derivation belongs
    to the model layer, not a metric."""
    cyls = analyse_cylinders(part)
    # One face-edge memo for the whole census. `Face.edges()` is the suite's most expensive
    # derived query and the recognisers below ask it of the same faces over and over; sharing
    # it here is worth about a fifth of this function's runtime. It must not outlive the call
    # -- see `FaceEdges`.
    face_edges = FaceEdges()
    # A through slot is also a passage, so the two families would count one void twice. The
    # rule that resolves it reads the faces each claimed, so both write into one ledger --
    # and the metric agrees with `build_recognition_result` because it is the same rule.
    ledger = ClaimLedger(FaceGraph(part, face_edges=face_edges))
    holes = recognise_holes(part, cyls=cyls, face_edges=face_edges)
    # One band is both the annular channel cut into a shaft and a rung of that shaft's step
    # ladder. Both records are real -- see `_reconcile` -- but it is one machined feature, and
    # this function counts features. Both run before the mapping so that the rule below sees a
    # complete ledger whatever order the entries are written in -- an earlier version called the
    # recognisers inside the mapping, where `"step"` is written before `"groove"`, so the rule
    # read an empty ledger and subtracted nothing. Silently: there is no groove claim to be
    # missing, only a count that is quietly one too high. Hoisting them removes the ordering
    # question rather than documenting it, and the order of these two lines does not matter.
    grooves = recognise_grooves(part, cyls=cyls, ledger=ledger)
    steps = recognise_turned_steps(part, cyls=cyls, ledger=ledger)
    # One bevel face is both "the edge break here" and "the slant of the step that stops here",
    # and only the second is true when a triangular flat closes it. Hoisted above the mapping
    # for the reason the two lines above are: `"chamfer"` is written before `"angled_step"`, so
    # calling the recognisers inside the mapping would let the rule read a ledger with no step
    # claims in it yet and subtract nothing -- silently, as a count one too high.
    # Both pocket families before the mapping: the rule needs the pairing family's claims,
    # and `"pocket"` is written before `"prismatic_pocket"`.
    pockets = recognise_pockets(part, face_edges=face_edges, ledger=ledger)
    prismatic = recognise_prismatic_pockets(part, face_edges=face_edges, ledger=ledger)
    chamfers = recognise_chamfers(part, face_edges=face_edges, ledger=ledger)
    angled_steps = recognise_angled_steps(part, face_edges=face_edges, ledger=ledger)
    records: dict[str, Sequence[Record]] = {
        "hole": holes,
        "hole_pattern": recognise_hole_patterns(holes),
        "boss": recognise_bosses(part, cyls=cyls, face_edges=face_edges),
        "step": steps_that_are_not_grooves(steps, ledger),
        "groove": grooves,
        "flat": recognise_flats(part, cyls=cyls, face_edges=face_edges),
        "slot": recognise_slots(part, ledger=ledger, face_edges=face_edges),
        "channel": recognise_channels(part, face_edges=face_edges, ledger=ledger),
        "pocket": pockets,
        "prismatic_pocket": prismatic_pockets_that_are_not_pockets(prismatic, ledger),
        "passage": passages_that_are_not_slots(part, ledger),
        "chamfer": chamfers_that_are_not_angled_steps(chamfers, ledger),
        "angled_step": angled_steps,
        "fillet": recognise_fillets(part, face_edges=face_edges),
        "countersink": recognise_countersinks(part),
        # Gated on the turned profile, as `build_recognition_result` gates it: a shaft whose
        # steps form a ladder is not a plate, and counting one here while the aggregate reports
        # none is two answers about one part. Measured before fixing -- it happened on exactly
        # one of the 73 corpus parts, a real turned screw, which is what a divergence between
        # two inventories looks like before anyone notices.
        #
        # The aggregate also gates on its caller's *rotational* classification. That is an input
        # this function does not take, so this matches the half it can evaluate rather than
        # pretending to the whole.
        "plate": [] if TurnedProfile.from_steps(list(steps)) is not None
        else recognise_plates(part),
    }
    return {kind: len(recs) for kind, recs in records.items()}
