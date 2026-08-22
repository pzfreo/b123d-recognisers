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

Above the aggregate rather than beside it: this counts what
:func:`b123d_recognisers.build_recognition_result` returns, over the same run, so a count and a
result cannot describe one part differently. It was a parallel orchestration once, and the two
drifted -- see ADR 0003's amendment for what that cost.
"""

from __future__ import annotations

from collections.abc import Sequence

from b123d_recognisers._reconcile import steps_that_are_not_grooves
from b123d_recognisers._record import Record
from b123d_recognisers._typing import Part
from b123d_recognisers.result import _take_inventory


def feature_census(part: Part) -> dict[str, int]:
    """The count of recognised features per kind for *part* (see module docs).

    Counts the one shared inventory -- the same sequence of recogniser calls, over the same
    run-local state, that `build_recognition_result` returns. It is not a second orchestration
    that happens to agree; agreeing is not something a second one can be made to keep doing.

    Returns ``{kind: count}`` with a stable, complete set of keys: a kind absent from the part
    reports ``0``, not a missing key. Face levels and step risers are computed by the inventory
    and not counted here: they feed other recognisers rather than being distinct machined
    features, and their level derivation belongs to the model layer, not to a metric.

    Taken as prismatic, because that is the classification under which nothing is gated away
    and a census is a completeness check. `build_recognition_result` takes *rotational* from
    its caller; this has no caller to take it from, and under-counting a real feature is the
    worse error for a metric.
    """

    run, found = _take_inventory(part)
    records: dict[str, Sequence[Record]] = {
        "hole": found.holes,
        "hole_pattern": found.hole_patterns,
        "boss": found.bosses,
        # The one place the census deliberately differs from the result it counts. A groove is
        # both an annular channel and a rung of the step ladder; both records are true and both
        # survive into the inventory, but it is one machined feature and this counts features.
        # See `steps_that_are_not_grooves` for why the ladder keeps its rung.
        "step": steps_that_are_not_grooves(list(found.turned_steps), run.ledger),
        "groove": found.grooves,
        "flat": found.flats,
        "slot": found.slots,
        "channel": found.channels,
        "pocket": found.pockets,
        "prismatic_pocket": found.prismatic_pockets,
        "passage": found.passages,
        "chamfer": found.chamfers,
        "angled_step": found.angled_steps,
        "through_step": found.through_steps,
        "round_bottom_blind_slot": found.round_bottom_blind_slots,
        "semicircular_bottom_blind_slot": found.semicircular_bottom_blind_slots,
        "fillet": found.fillets,
        "countersink": found.countersinks,
        "plate": found.plates,
    }
    return {kind: len(recs) for kind, recs in records.items()}
