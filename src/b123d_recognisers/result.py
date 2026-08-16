# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Immutable aggregate of one complete recognition pass.

This is the orchestration boundary above the package ADR 0002 recognisers. It owns every public
recognition family and the shared evidence consumers reuse. It deliberately stops at
geometry-only evidence: reconciliation, requirement identity, drawing policy, and diagnostics
belong to consumers and require their own independent evidence.
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
    analyse_cylinders,
    recognise_bosses,
    recognise_hole_patterns,
    recognise_holes,
)
from b123d_recognisers._typing import Bounds, CylinderInventory, FrozenCylinderInventory, Part
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
from b123d_recognisers.plates import Plate, recognise_plates
from b123d_recognisers.polygonal_bosses import (
    PolygonalBoss,
    PolygonalStock,
    recognise_polygonal_bosses,
    recognise_polygonal_stock,
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
from b123d_recognisers.turned import TurnedProfile, TurnedStep, recognise_turned_steps

#: The families this aggregate runs, exactly once, per orchestration.
MIGRATED: frozenset[str] = frozenset(
    {
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
    #: inventory from an empty one. ``chamfers``/``fillets``/``plates`` are ``()`` on a
    #: rotational part because they were not run, not because the part has none — the same
    #: empty-vs-not-run distinction consumers must preserve for declared inputs.
    rotational: bool
    #: Candidate step risers, scanned once and projected per consumer. NOT shoulders:
    #: which risers count depends on the level set the asker holds, and that is the whole
    #: reason this family could not be hoisted until the scan and the filter were separated.
    risers: tuple[RiserEvidence, ...]
    #: Classification-gated inventories. Recognised only for the class that consumes
    #: them: chamfers and fillets on a non-rotational part (a turned part's chamfers are
    #: conical, so the recogniser finds none anyway), plates additionally only when there is no
    #: turned profile. The gate lives HERE, in the one orchestration, rather than at each call
    #: site — which is the distinction that let these migrate at all: owning a family and
    #: always running it are different things.
    chamfers: tuple[Chamfer, ...]
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

    z_cyls, cross_cyls = cylinders if cylinders is not None else analyse_cylinders(part)
    cyls = (z_cyls, cross_cyls)
    countersinks = recognise_countersinks(part)
    holes = recognise_holes(part, cyls=cyls, csinks=countersinks)
    double_d_bores = recognise_double_d_bores(part)
    channels = recognise_channels(part)
    pockets = recognise_pockets(part)
    slots = recognise_slots(part)
    turned_steps = recognise_turned_steps(part, cyls=cyls)
    # ONE place decides, from the classification the result then carries. Per-family
    # conditionals at each call site are what the aggregate single-scan design removes; this
    # decides once for every consumer rather than each consumer deciding again.
    prismatic = not rotational
    prof = TurnedProfile.from_steps(list(turned_steps))
    return RecognitionResult(
        cylinders=(tuple(z_cyls), tuple(cross_cyls)),
        countersinks=tuple(countersinks),
        holes=tuple(holes),
        double_d_bores=tuple(double_d_bores),
        hole_patterns=tuple(recognise_hole_patterns(holes)),
        bosses=tuple(recognise_bosses(part, cyls=cyls)),
        polygonal_bosses=tuple(recognise_polygonal_bosses(part)),
        polygonal_stock=tuple(recognise_polygonal_stock(part)),
        channels=tuple(channels),
        slots=tuple(slots),
        # Derived from the accepted members, like the other two pattern families — the
        # recogniser must not rediscover the slots it groups.
        slot_patterns=tuple(recognise_slot_patterns(slots)),
        grooves=tuple(recognise_grooves(part, cyls=cyls)),
        flats=tuple(recognise_flats(part, cyls=cyls)),
        pockets=tuple(pockets),
        pocket_patterns=tuple(recognise_pocket_patterns(pockets)),
        pads=tuple(recognise_rectangular_pads(part)),
        repeating_radial_profiles=tuple(recognise_repeating_radial_profiles(part)),
        turned_steps=tuple(turned_steps),
        rotational=rotational,
        step_levels=tuple(step_level_records(part)),
        risers=tuple(recognise_risers(part)),
        chamfers=tuple(recognise_chamfers(part)) if prismatic else (),
        fillets=tuple(recognise_fillets(part)) if prismatic else (),
        plates=tuple(recognise_plates(part)) if prismatic and prof is None else (),
    )
