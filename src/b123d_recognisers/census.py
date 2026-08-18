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
    recognise_passages,
    recognise_plates,
    recognise_pockets,
    recognise_slots,
    recognise_turned_steps,
)
from b123d_recognisers._adjacency import FaceEdges
from b123d_recognisers._record import Record
from b123d_recognisers._typing import Part


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
    holes = recognise_holes(part, cyls=cyls, face_edges=face_edges)
    records: dict[str, Sequence[Record]] = {
        "hole": holes,
        "hole_pattern": recognise_hole_patterns(holes),
        "boss": recognise_bosses(part, cyls=cyls, face_edges=face_edges),
        "step": recognise_turned_steps(part, cyls=cyls),
        "groove": recognise_grooves(part, cyls=cyls),
        "flat": recognise_flats(part, cyls=cyls, face_edges=face_edges),
        "slot": (slots := recognise_slots(part, face_edges=face_edges)),
        "channel": recognise_channels(part, face_edges=face_edges),
        "pocket": recognise_pockets(part, face_edges=face_edges),
        "passage": recognise_passages(part, slots=slots, face_edges=face_edges),
        "chamfer": recognise_chamfers(part, face_edges=face_edges),
        "angled_step": recognise_angled_steps(part, face_edges=face_edges),
        "fillet": recognise_fillets(part, face_edges=face_edges),
        "countersink": recognise_countersinks(part),
        "plate": recognise_plates(part),
    }
    return {kind: len(recs) for kind, recs in records.items()}
