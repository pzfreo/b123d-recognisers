# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Immutable aggregate of one complete recognition pass.

This is the orchestration boundary above the package ADR 0002 recognisers. It owns every public
recognition family and the shared evidence consumers reuse. It deliberately stops at
geometry-only evidence and package-owned geometric reconciliation. Requirement identity,
drawing policy, and consumer diagnostics remain outside this layer.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from enum import Enum

from b123d_recognisers._features import (
    BoltCircle,
    BossRecord,
    HoleRecord,
    LinearArray,
    RectGrid,
    recognise_bosses,
    recognise_hole_patterns,
    recognise_holes,
)
from b123d_recognisers._reconcile import (
    chamfers_that_are_not_angled_steps,
    reconcile_recesses,
)
from b123d_recognisers._run import RecognitionRun, start
from b123d_recognisers._typing import Bounds, CylinderInventory, FrozenCylinderInventory, Part
from b123d_recognisers.angled_steps import AngledStep, recognise_angled_steps
from b123d_recognisers.chamfers import Chamfer, recognise_chamfers
from b123d_recognisers.countersinks import CounterSink, recognise_countersinks
from b123d_recognisers.fillets import Fillet, recognise_fillets
from b123d_recognisers.flats import Flat, recognise_flats
from b123d_recognisers.grooves import Groove, recognise_grooves
from b123d_recognisers.levels import (
    FaceLevel,
    RiserEvidence,
    bounded_end_margin,
    recognise_risers,
    step_level_records,
)
from b123d_recognisers.pads import RaisedPad, recognise_rectangular_pads
from b123d_recognisers.passages import Passage, recognise_passages
from b123d_recognisers.plates import Plate, recognise_plates
from b123d_recognisers.polygonal_bosses import (
    PolygonalBoss,
    PolygonalStock,
    recognise_polygonal_bosses,
    recognise_polygonal_stock,
)
from b123d_recognisers.prismatic_pockets import (
    PrismaticPocket,
    recognise_prismatic_pockets,
)
from b123d_recognisers.profiled_bores import DoubleDBore, recognise_double_d_bores
from b123d_recognisers.repeating_profiles import (
    RepeatingRadialProfile,
    recognise_repeating_radial_profiles,
)
from b123d_recognisers.slots import (
    Channel,
    Pocket,
    PocketArray,
    PocketGrid,
    Slot,
    SlotArray,
    SlotGrid,
    recognise_channels,
    recognise_pocket_patterns,
    recognise_pockets,
    recognise_slot_patterns,
    recognise_slots,
)
from b123d_recognisers.through_steps import ThroughStep, recognise_through_steps
from b123d_recognisers.turned import TurnedProfile, TurnedStep, recognise_turned_steps

#: The families this aggregate runs, exactly once, per orchestration.
MIGRATED: frozenset[str] = frozenset(
    {
        "recognise_angled_steps",
        "recognise_passages",
        "recognise_prismatic_pockets",
        "recognise_bosses",
        "recognise_chamfers",
        "recognise_channels",
        "recognise_countersinks",
        "recognise_double_d_bores",
        "recognise_fillets",
        "recognise_flats",
        "recognise_grooves",
        # Reached through `step_level_records`, the area-filtered gate over it. The aggregate
        # retains those records because consumers need their support spans;
        # `step_ladder_for_z_span()` gives sizing and critique their shared float projection.
        # Previously deferred for lack of an independent consumer, it now supplies the geometry
        # ladder to completeness checks without requiring a second scan.
        "recognise_face_levels",
        "recognise_hole_patterns",
        "recognise_holes",
        "recognise_pocket_patterns",
        "recognise_plates",
        "recognise_pockets",
        "recognise_polygonal_bosses",
        "recognise_polygonal_stock",
        "recognise_rectangular_pads",
        "recognise_repeating_radial_profiles",
        "recognise_risers",
        "recognise_slot_patterns",
        "recognise_slots",
        "recognise_turned_steps",
        "recognise_through_steps",
    }
)


class Deferral(Enum):
    """Why a family is not in :data:`MIGRATED` — a code, not a paragraph.

    Deferrals are explicit compatibility states, not backlog markers. A family may remain
    outside the aggregate only while one of these concrete constraints is true.

    ``CLASSIFICATION_GATED`` — an automatic-model consumer runs it only for one part class, so
    hoisting it unconditionally scans the other class for a result that is discarded.  Note
    this constraint is about applicability, not ownership. It ends when the orchestration
    carries the classification and can make the decision once.

    ``BUILD_MODEL_ONLY`` — only an automatic-model consumer needs the result. Hoisting it
    unconditionally would remove no scan from that path and add one for callers that already
    supply declared geometry.

    ``CALLER_SPECIFIC_INPUT`` — an input other than the part decides the answer and the
    callers pass different ones, so there is no single per-build value for a frozen
    aggregate to hold. Experience showed the reason is usually a
    *shape* problem rather than a fact about the feature: the scan did not depend on the
    caller's input, only the filter did, so separating the two gave the aggregate something
    single-valued to own.  Prefer that split before reaching for this member again.

    ``NO_INDEPENDENT_CONSUMER`` — reached only through one shared helper, so there is
    nothing to cache for.  Unlike the others, not scheduled to change.
    """

    CLASSIFICATION_GATED = "classification-gated"
    BUILD_MODEL_ONLY = "build-part-model-only"
    CALLER_SPECIFIC_INPUT = "caller-specific-input"
    NO_INDEPENDENT_CONSUMER = "no-independent-consumer"


@dataclass(frozen=True)
class Deferred:
    """A family the aggregate does not own, and the constraint that stops it.

    ``blocker`` is the issue that removes the constraint, or ``None`` when the deferral is
    not scheduled to end.  A deferral without either is "not got to it yet", which is not a
    reason.
    """

    reason: Deferral
    blocker: int | None = None


#: The families the aggregate does NOT own, each with its constraint.
#:
#: ``BUILD_MODEL_ONLY`` is gone as a live reason: its three families cost the
#: declared path nothing because that path does not run automatic recognition, so aggregate
#: completeness was reason enough on its own.  The enum member survives because a future
#: family can be deferred for that reason again; what does not survive is a *deferral*
#: justified by a cost that no longer exists.
#:
#: ``CALLER_SPECIFIC_INPUT`` is gone too: ``recognise_step_shoulders`` split into a
#: level-free scan the aggregate owns (``recognise_risers``) and a pure
#: ``project_step_shoulders`` each consumer applies with its own level set.
#:
#: ``CLASSIFICATION_GATED`` is gone last. Its three families are gated INSIDE the
#: orchestration now — one place decides, once, from the classification the result carries —
#: rather than each call site deciding for itself. Migration and applicability turned out to
#: be different questions: the aggregate can own a family it does not always run.
#:
#: The map is empty: every public
#: ``recognise_*`` family is owned by the one orchestration. The mechanism stays — a new
#: family still has to be classified — and every enum member survives for a future one.
DEFERRED: dict[str, Deferred] = {}


@dataclass(frozen=True)
class RecognitionResult:
    """The immutable feature inventory produced by one recognition orchestration run.

    Every public ``recognise_*`` family is owned here, although classification gates mean an
    inapplicable family need not run. This is a recognition inventory, not drafting state and
    not a promise that the evidence-gated correspondence extensions have landed.
    """

    cylinders: FrozenCylinderInventory
    countersinks: tuple[CounterSink, ...]
    holes: tuple[HoleRecord, ...]
    double_d_bores: tuple[DoubleDBore, ...]
    hole_patterns: tuple[BoltCircle | LinearArray | RectGrid, ...]
    bosses: tuple[BossRecord, ...]
    polygonal_bosses: tuple[PolygonalBoss, ...]
    polygonal_stock: tuple[PolygonalStock, ...]
    channels: tuple[Channel, ...]
    slots: tuple[Slot, ...]
    slot_patterns: tuple[SlotArray | SlotGrid, ...]
    grooves: tuple[Groove, ...]
    flats: tuple[Flat, ...]
    pockets: tuple[Pocket, ...]
    prismatic_pockets: tuple[PrismaticPocket, ...]
    pocket_patterns: tuple[PocketArray | PocketGrid, ...]
    pads: tuple[RaisedPad, ...]
    #: Complete outer-wire cyclic correspondence.  Geometry-only: consumers may compare a
    #: declared axis/count, but this inventory never manufactures gear semantics.
    repeating_radial_profiles: tuple[RepeatingRadialProfile, ...]
    turned_steps: tuple[TurnedStep, ...]
    #: Area-filtered interior prismatic levels. The support spans remain on each record so IR
    #: assembly can preserve level-to-face correspondence; sizing and critique project the Z
    #: values through :meth:`step_ladder_for_z_span`.
    step_levels: tuple[FaceLevel, ...]
    #: Whether the part classified as ROTATIONAL, carried so consumers can tell a gated-away
    #: inventory from an empty one. ``plates`` are ``()`` on a rotational part because they
    #: were not run, not because the part has none — the same
    #: empty-vs-not-run distinction consumers must preserve for declared inputs.
    rotational: bool
    #: Candidate step risers, scanned once and projected per consumer. NOT shoulders:
    #: which risers count depends on the level set the asker holds, and that is the whole
    #: reason this family could not be hoisted until the scan and the filter were separated.
    risers: tuple[RiserEvidence, ...]
    #: Chamfers and fillets are recognised on every part: planar/cylindrical on a prismatic
    #: part and conical/toroidal on a turned part. Plates additionally require no turned
    #: profile. The gate lives HERE, in the one orchestration, rather than at each call site —
    #: which is the distinction that let these migrate at all: owning a family and always
    #: running it are different things.
    chamfers: tuple[Chamfer, ...]
    #: Prismatic-only: an angled blind step is the same planar oblique-bevel read as a
    #: chamfer, while the conical bevel on a rotational part cannot establish one.
    angled_steps: tuple[AngledStep, ...]
    #: Open right-angle cuts spanning a source solid; currently the rectangular subset.
    through_steps: tuple[ThroughStep, ...]
    #: Prismatic voids running through the material, one record per closed ring.
    passages: tuple[Passage, ...]
    fillets: tuple[Fillet, ...]
    plates: tuple[Plate, ...]

    def step_ladder_for_z_span(
        self,
        z_min: float,
        z_max: float,
        *,
        boundary_margin: float | None = None,
    ) -> list[float]:
        """Return the effective step ladder within an explicit Z envelope.

        ``z_min``, ``z_max``, and an explicit ``boundary_margin`` use model length units
        (millimetres in conventional build123d/STEP workflows). For a Z-turned profile, only
        shoulders strictly inside ``z_min + boundary_margin`` and ``z_max - boundary_margin`` are
        rungs; equality is excluded. A span narrower than twice the margin therefore has no
        turned rungs.

        ``boundary_margin=None`` uses :data:`STEP_LADDER_BOUNDARY_MARGIN`, capped so it can
        never exceed a quarter of the span. The inset excludes an *end treatment* — a chamfer or
        edge break just inside the face — which is a manufacturing constant that does not grow
        with the shaft, so ADR 0008 keeps it absolute and bounds it instead. It stays the same
        rule ``step_level_records`` applies, which ADR 0006 requires the two to share.

        Prismatic levels are already envelope-filtered by :func:`step_level_records` during the
        recognition pass, so this projection returns them unchanged. The span is still validated
        on every path so invalid geometry input cannot be hidden by part classification.

        One rule serves every consumer. Model construction and completeness checks need the
        same set, but deriving it separately could silently project over different ladders.

        Geometry-only, so it is a legitimate source for critique under the independent-evidence
        rule: it reads the aggregate's own recognition, never the model.
        """
        if not math.isfinite(z_min) or not math.isfinite(z_max):
            raise ValueError("z_min and z_max must be finite")
        if z_min > z_max:
            raise ValueError("z_min must not exceed z_max")
        if boundary_margin is None:
            boundary_margin = bounded_end_margin(z_max - z_min)
        if not math.isfinite(boundary_margin) or boundary_margin < 0.0:
            raise ValueError("boundary_margin must be finite and non-negative")
        prof = TurnedProfile.from_steps(list(self.turned_steps))
        if prof is not None and prof.axis == "z":
            return [
                float(z)
                for z in prof.shoulders
                if z_min + boundary_margin < z < z_max - boundary_margin
            ]
        return [level.z for level in self.step_levels]

    def step_ladder(self, bb: Bounds) -> list[float]:
        """Compatibility shim for a build123d bounding box.

        Deprecated since 0.2.1. Use :meth:`step_ladder_for_z_span` with the two scalar Z limits.
        This shim remains for the 0.2.x compatibility line and is removed no earlier than 1.0.0.
        """
        warnings.warn(
            "RecognitionResult.step_ladder(BoundBox) is deprecated since 0.2.1; use "
            "step_ladder_for_z_span(z_min, z_max). It will be removed no earlier than 1.0.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.step_ladder_for_z_span(float(bb.min.Z), float(bb.max.Z))


def build_recognition_result(
    part: Part,
    *,
    cylinders: CylinderInventory | None = None,
    rotational: bool = False,
) -> RecognitionResult:
    """Run the shared recognition inventory exactly once for *part*.

    Dependencies are computed by this orchestration layer and injected downstream: holes
    reuse both the cylinder substrate and countersinks, while patterns reuse their accepted
    member records.  No recogniser rediscovers one of those dependencies internally.

    *rotational* is the caller's geometric classification.
    It gates the three families that only one part class consumes, so migrating them did not
    mean scanning every turned build for a discarded result.

    It is a scoping constraint, not an architectural one.
    The classification itself is geometry-only: it can be derived from bounding-box
    proportions, the largest external cylinder, and concentricity. It remains caller-supplied
    for compatibility; consumers may also use the same fact for view or drawing policy without
    transferring ownership of that policy into this package.

    The default is ``False`` — prismatic, so nothing is gated away.  A caller who has no
    classification (the lazy critique aggregate on a declared build) gets the COMPLETE
    inventory, which is the right default for a completeness check: over-recognising costs
    time, under-recognising reports a real feature as absent.
    """

    return _take_inventory(part, cylinders=cylinders, rotational=rotational)[1]


def _take_inventory(
    part: Part,
    *,
    cylinders: CylinderInventory | None = None,
    rotational: bool = False,
) -> tuple[RecognitionRun, RecognitionResult]:
    """The one inventory, and the run it was taken over. Internal to this package.

    `build_recognition_result` is this without the run, and `feature_census` is this counted.
    They were two hand-maintained sequences of the same recogniser calls before, differing in
    ways nobody had decided: the census injected a face-edge memo and the aggregate did not,
    the aggregate injected countersinks into the hole recogniser and the census did not, and
    the two gated plates on different halves of the same condition -- which is how one turned
    screw came to be a plate to one entry point and not to the other. Every such difference is
    a divergence waiting to be a wrong number, and none of them was written down as a choice.

    So there is one sequence, and the census counts what it returns. The run comes back with
    the result because the census needs the ledger: `steps_that_are_not_grooves` is a
    *counting* rule under ADR 0003, applied by the census alone, and it asks the ledger which
    faces a step and a groove were each built from.

    The census now pays for the families it does not count -- pads, polygonal stock, step
    levels and the rest. Two measurements, because one of them alone misleads:

    - `feature_census` on its own, over nine NIST and real-world STEP parts: 39.5 s to 53.4 s,
      about **35% more**. Spread across seven families with no hot spot to fix -- step levels
      are the largest single contributor at about a third of the added time.
    - The pinned parity benchmark, the composite release workload (two results and one census
      over four fixtures): **about 4% more**, 1.849 s to 1.931 s, best of five over three
      interleaved blocks.

    The composite figure is the one that bears on release, and the census-only figure is the
    one that bears on corpus sweeps. Both are the price of the two entry points being unable to
    disagree, and it is the right way round -- a measurement tool that is fast and quietly wrong
    is worth less than one that is slower and says what the library says.

    Recoverable without reopening the divergence, if a consumer ever needs both: this function
    returns the run, so one inventory can serve a result and a count. Left private until
    something asks, rather than published on the chance that it will. Both figures are held to a
    budget, tracked as a named follow-up rather than left as a number in a docstring.
    """

    # One run, one set of shared facts, derived once here rather than by whichever family asks
    # first -- see `RecognitionRun`.
    run = start(part, cylinders)
    z_cyls, cross_cyls = run.cylinders
    cyls = run.cylinders
    face_edges = run.face_edges
    countersinks = recognise_countersinks(part)
    holes = recognise_holes(part, cyls=cyls, csinks=countersinks, face_edges=face_edges)
    double_d_bores = recognise_double_d_bores(part)
    # The two families that describe a void by the faces bounding it both write into one
    # ledger, so the reconciliation below is a question about faces rather than about
    # coordinates each of them derived its own way.
    ledger = run.ledger
    slots = recognise_slots(part, ledger=ledger, face_edges=face_edges)
    channels = recognise_channels(part, ledger=ledger, face_edges=face_edges)
    # Into the same ledger. No rule reads pocket claims today, and that is the reason to write
    # them rather than to wait: a partial ledger is the trap this whole mechanism exists to
    # close, since a future rule reading one would find no pocket claim and conclude there is
    # no overlap -- silently, which is the failure `require_node` and `claims_of` both refuse
    # to allow anywhere else.
    pockets = recognise_pockets(part, ledger=ledger, face_edges=face_edges)
    ring_pockets = recognise_prismatic_pockets(part, ledger=ledger, face_edges=face_edges)
    passages = recognise_passages(part, ledger=ledger)
    recesses = reconcile_recesses(
        slots, pockets, ring_pockets, passages, ledger
    )
    accepted_slots = recesses.slots
    accepted_pockets = recesses.pockets
    accepted_ring_pockets = recesses.prismatic_pockets
    accepted_passages = recesses.passages
    # Into the ledger for the same reason, though the rule that reads these two runs in the
    # census rather than here: a groove is a rung of the step ladder, and both records survive
    # into the result because a consumer dimensioning the shaft needs the feature and the
    # profile. Only a count of *distinct machined features* has to choose.
    turned_steps = recognise_turned_steps(part, cyls=cyls, ledger=ledger)
    # ONE place decides, from the classification the result then carries. Per-family
    # conditionals at each call site are what the aggregate single-scan design removes; this
    # decides once for every consumer rather than each consumer deciding again.
    prismatic = not rotational
    # Both bevel families write into the same ledger, and both run before the result is built:
    # the rule below needs the step claims, and the field order of `RecognitionResult` puts
    # `chamfers` first. Only angled steps are prismatic; chamfers also cover the external cones
    # that a lathe makes at a turned shoulder or free end.
    chamfers = recognise_chamfers(
        part,
        cyls=cyls,
        ledger=ledger,
        face_edges=face_edges,
        include_planar=prismatic,
    )
    angled_steps = (
        recognise_angled_steps(part, ledger=ledger, face_edges=face_edges) if prismatic else []
    )
    through_steps = recognise_through_steps(part, ledger=ledger) if prismatic else []
    prof = TurnedProfile.from_steps(list(turned_steps))
    return run, RecognitionResult(
        cylinders=(tuple(z_cyls), tuple(cross_cyls)),
        countersinks=tuple(countersinks),
        holes=tuple(holes),
        double_d_bores=tuple(double_d_bores),
        hole_patterns=tuple(recognise_hole_patterns(holes)),
        bosses=tuple(recognise_bosses(part, cyls=cyls, face_edges=face_edges)),
        polygonal_bosses=tuple(recognise_polygonal_bosses(part, graph=run.graph)),
        polygonal_stock=tuple(recognise_polygonal_stock(part, graph=run.graph)),
        channels=tuple(channels),
        slots=accepted_slots,
        # Derived from the accepted members, like the other two pattern families — the
        # recogniser must not rediscover the slots it groups.
        slot_patterns=tuple(recognise_slot_patterns(accepted_slots)),
        # Also into the ledger, and the census's step count depends on it: the rule it applies
        # after this returns asks which faces a groove was built from, and an unclaimed groove
        # would subtract nothing and be counted twice, silently.
        grooves=tuple(
            recognise_grooves(part, cyls=cyls, ledger=ledger, face_edges=face_edges)
        ),
        flats=tuple(recognise_flats(part, cyls=cyls, face_edges=face_edges)),
        pockets=accepted_pockets,
        prismatic_pockets=accepted_ring_pockets,
        pocket_patterns=tuple(recognise_pocket_patterns(accepted_pockets)),
        pads=tuple(recognise_rectangular_pads(part)),
        repeating_radial_profiles=tuple(recognise_repeating_radial_profiles(part)),
        turned_steps=tuple(turned_steps),
        rotational=rotational,
        step_levels=tuple(step_level_records(part)),
        risers=tuple(recognise_risers(part)),
        chamfers=tuple(chamfers_that_are_not_angled_steps(chamfers, ledger)),
        angled_steps=tuple(angled_steps),
        through_steps=tuple(through_steps),
        passages=accepted_passages if prismatic else (),
        fillets=tuple(
            recognise_fillets(
                part,
                cyls=cyls,
                face_edges=face_edges,
                include_cylindrical=prismatic,
            )
        ),
        plates=tuple(recognise_plates(part)) if prismatic and prof is None else (),
    )
