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
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType
from typing import TypeVar, cast

from b123d_recognisers._candidates import CandidateSet, EvidenceIndex, FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._correspondence import _CorrespondenceSnapshotAuthority
from b123d_recognisers._diagnostics import ResidualDiagnostic, diagnose_residuals
from b123d_recognisers._dispositions import (
    ReasonCode,
)
from b123d_recognisers._dispositions import (
    ReconciliationResult as CandidateReconciliation,
)
from b123d_recognisers._features import (
    BoltCircle,
    BossRecord,
    HoleRecord,
    LinearArray,
    RectGrid,
)
from b123d_recognisers._reconcile import (
    reconcile_bevel_candidates,
    reconcile_recess_candidates,
    reconcile_step_groove_candidates,
)
from b123d_recognisers._registry import (
    DERIVED_DEFINITIONS,
    PHYSICAL_DEFINITIONS,
    AcceptedInputs,
    AcceptedProjectionInputs,
    DerivedId,
    DiscoveryServices,
    FullyAttributed,
    ProjectionDiscoverer,
    ProjectionInputs,
    _issue_projection_inputs,
    validate_output,
    validate_result_fields,
)
from b123d_recognisers._run import RecognitionContext, start
from b123d_recognisers._typing import Bounds, CylinderInventory, FrozenCylinderInventory, Part
from b123d_recognisers.angled_steps import AngledStep
from b123d_recognisers.chamfers import Chamfer
from b123d_recognisers.countersinks import CounterSink
from b123d_recognisers.fillets import Fillet
from b123d_recognisers.flats import Flat
from b123d_recognisers.grooves import Groove
from b123d_recognisers.levels import (
    FaceLevel,
    RiserEvidence,
    bounded_end_margin,
)
from b123d_recognisers.pads import RaisedPad
from b123d_recognisers.passages import Passage, SectionPassage
from b123d_recognisers.plates import Plate
from b123d_recognisers.polygonal_bosses import (
    PolygonalBoss,
    PolygonalStock,
)
from b123d_recognisers.prismatic_pockets import PrismaticPocket
from b123d_recognisers.profiled_bores import DoubleDBore
from b123d_recognisers.repeating_profiles import RepeatingRadialProfile
from b123d_recognisers.slots import (
    Channel,
    Pocket,
    PocketArray,
    PocketGrid,
    Slot,
    SlotArray,
    SlotGrid,
)
from b123d_recognisers.turned import TurnedProfile, TurnedStep

#: The families this aggregate runs, exactly once, per orchestration.
MIGRATED: frozenset[str] = frozenset(
    definition.public_entrypoint for definition in PHYSICAL_DEFINITIONS
) | frozenset(
    definition.public_entrypoint
    for definition in DERIVED_DEFINITIONS
    if definition.public_entrypoint is not None
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


# Internal execution order is derived from the explicit closed registry, never filesystem order.
PHYSICAL_FAMILIES: tuple[FamilyId, ...] = tuple(
    definition.family for definition in PHYSICAL_DEFINITIONS
)


@dataclass(frozen=True, slots=True)
class CandidateInventory:
    """One source-ordered candidate set for every physical family."""

    _sets: Mapping[FamilyId, CandidateSet[object]]

    @classmethod
    def complete(cls, sets: Iterable[CandidateSet[object]]) -> CandidateInventory:
        by_family = {candidate_set.family: candidate_set for candidate_set in sets}
        if tuple(by_family) != PHYSICAL_FAMILIES or len(by_family) != len(PHYSICAL_FAMILIES):
            raise ValueError("physical candidate inventory is incomplete or out of order")
        return cls(MappingProxyType(by_family))

    def candidate_set(self, family: FamilyId) -> CandidateSet[object]:
        return self._sets[family]

    def records(self, family: FamilyId) -> tuple[object, ...]:
        return tuple(candidate.record for candidate in self.candidate_set(family).candidates)

    def replacing(self, replacements: Iterable[CandidateSet[object]]) -> CandidateInventory:
        changed = dict(self._sets)
        for candidate_set in replacements:
            changed[candidate_set.family] = candidate_set
        return CandidateInventory.complete(changed[family] for family in PHYSICAL_FAMILIES)


@dataclass(frozen=True, slots=True)
class DerivedInventory:
    """Post-reconciliation projections; these are not physical candidates."""

    hole_patterns: tuple[BoltCircle | LinearArray | RectGrid, ...]
    slot_patterns: tuple[SlotArray | SlotGrid, ...]
    pocket_patterns: tuple[PocketArray | PocketGrid, ...]
    passages: tuple[Passage, ...]


@dataclass(frozen=True, slots=True)
class InventoryProduct:
    """The one internal inventory consumed by result, census and attribution views."""

    context: RecognitionContext
    evidence: EvidenceIndex
    physical: CandidateInventory
    reconciliation: CandidateReconciliation
    diagnostics: tuple[ResidualDiagnostic, ...]
    derived: DerivedInventory
    result: RecognitionResult
    _correspondence_authority: object | None = field(default=None, repr=False, compare=False)

    @property
    def accepted(self) -> CandidateInventory:
        return CandidateInventory.complete(
            self.reconciliation.accepted_set(self.physical.candidate_set(family))
            for family in PHYSICAL_FAMILIES
        )

    @property
    def distinct_steps(self) -> CandidateSet[object]:
        source = self.physical.candidate_set(FamilyId.TURNED_STEPS)
        related = {
            id(item.candidate)
            for item in self.reconciliation.for_family(FamilyId.TURNED_STEPS)
            if item.reason is ReasonCode.TURNED_STEP_GROOVE_COMPATIBLE
        }
        accepted = self.reconciliation.accepted_set(source)
        result = object.__new__(CandidateSet)
        object.__setattr__(result, "family", FamilyId.TURNED_STEPS)
        object.__setattr__(
            result,
            "candidates",
            tuple(candidate for candidate in accepted.candidates if id(candidate) not in related),
        )
        object.__setattr__(result, "_issuer", source._issuer)
        return result


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
    #: Prismatic voids running through the material, one record per closed ring. Discovery still
    #: runs on a rotational-classified part so Passage evidence can reconcile overlapping recess
    #: proposals, but this public tuple is then projected as ``()``.
    section_passages: tuple[SectionPassage, ...]
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


validate_result_fields(
    frozenset(RecognitionResult.__dataclass_fields__) - {"cylinders", "rotational"}
)


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

    return _take_inventory(part, cylinders=cylinders, rotational=rotational).result


def _take_inventory(
    part: Part,
    *,
    cylinders: CylinderInventory | None = None,
    rotational: bool = False,
) -> InventoryProduct:
    """Run the explicit physical, reconciliation, derived and projection phases once."""

    context = start(part, cylinders, rotational=rotational)
    ledger = ClaimLedger(context.graph, definitions=PHYSICAL_DEFINITIONS)
    physical = CandidateInventory.complete(_discover_all(context, ledger))
    evidence = ledger.freeze_index()
    evidence.validate_complete_inventory(
        tuple(physical.candidate_set(family) for family in PHYSICAL_FAMILIES)
    )
    _validate_attribution(context, physical, evidence)
    reconciliation = _reconcile_existing(physical, evidence)
    diagnostics = diagnose_residuals(reconciliation, evidence)
    accepted = CandidateInventory.complete(
        reconciliation.accepted_set(physical.candidate_set(family)) for family in PHYSICAL_FAMILIES
    )
    derived = _derive_patterns(accepted)
    passage_definition = next(
        item for item in PHYSICAL_DEFINITIONS if item.family is FamilyId.PASSAGES
    )
    passage_projection = _issue_projection_inputs(
        accepted.candidate_set(FamilyId.PASSAGES),
        evidence,
    )
    derived = replace(
        derived,
        passages=_derive_passage_compat(
            passage_projection,
            ProjectionInputs(passage_definition.projected(context)),
        ),
    )
    result = _project_result(context, accepted, derived)
    correspondence = _CorrespondenceSnapshotAuthority()
    product = InventoryProduct(
        context=context,
        evidence=evidence,
        physical=physical,
        reconciliation=reconciliation,
        diagnostics=diagnostics,
        derived=derived,
        result=result,
        _correspondence_authority=correspondence,
    )
    correspondence.bind(product)
    return product


def _discover_all(
    context: RecognitionContext, ledger: ClaimLedger
) -> tuple[CandidateSet[object], ...]:
    """Discover and atomically complete each physical family in registry order."""

    services = DiscoveryServices(
        context=context,
        writer=ledger.writer,
        cylinders=(list(context.cylinders[0]), list(context.cylinders[1])),
    )
    completed: list[CandidateSet[object]] = []
    for definition in PHYSICAL_DEFINITIONS:
        inputs = ledger.restricted_inputs(definition)
        applicable = definition.applicable(context)
        records = definition.discover(services, inputs) if applicable else []
        validate_output(definition, records)
        completed.append(ledger.candidate_set_for(definition.family, records))
    return tuple(completed)


def _validate_attribution(
    context: RecognitionContext, physical: CandidateInventory, evidence: EvidenceIndex
) -> None:
    """Revalidate registry completeness and common-solid provenance on terminal evidence."""

    for definition in PHYSICAL_DEFINITIONS:
        candidates = physical.candidate_set(definition.family).candidates
        for candidate in candidates:
            defining = evidence.defining_of(candidate)
            if isinstance(definition.attribution, FullyAttributed) and not defining:
                raise ValueError(
                    f"{definition.family.value} promises complete defining attribution"
                )
            if defining and context.graph.common_valid_solid(defining) is None:
                raise ValueError("physical defining evidence lost its common valid solid")


RecordT = TypeVar("RecordT")


def _records(
    inventory: CandidateInventory,
    family: FamilyId,
    record_type: type[RecordT],
) -> list[RecordT]:
    records = list(inventory.records(family))
    if not all(isinstance(record, record_type) for record in records):
        raise TypeError(f"{family.value} inventory has the wrong record type")
    return cast(list[RecordT], records)


def _reconcile_existing(
    physical: CandidateInventory, evidence: EvidenceIndex
) -> CandidateReconciliation:
    """Apply existing policies to completed candidates and terminal evidence only."""

    decisions = reconcile_recess_candidates(
        physical.candidate_set(FamilyId.SLOTS),
        physical.candidate_set(FamilyId.POCKETS),
        physical.candidate_set(FamilyId.PRISMATIC_POCKETS),
        physical.candidate_set(FamilyId.PASSAGES),
        evidence,
    )
    decisions += reconcile_bevel_candidates(
        physical.candidate_set(FamilyId.CHAMFERS),
        physical.candidate_set(FamilyId.ANGLED_STEPS),
        evidence,
    )
    decisions += reconcile_step_groove_candidates(
        physical.candidate_set(FamilyId.TURNED_STEPS),
        physical.candidate_set(FamilyId.GROOVES),
        evidence,
    )
    return CandidateReconciliation.complete(
        tuple(physical.candidate_set(family) for family in PHYSICAL_FAMILIES),
        decisions,
        evidence,
    )


def _derive_patterns(accepted: CandidateInventory) -> DerivedInventory:
    """Derive pattern projections only from accepted member records."""

    accepted_records = {family: tuple(accepted.records(family)) for family in PHYSICAL_FAMILIES}
    derived: dict[DerivedId, tuple[object, ...]] = {}
    for definition in DERIVED_DEFINITIONS:
        if definition.role == "projection":
            continue
        inputs = AcceptedInputs.restricted(definition.sources, accepted_records)
        standard_derive = cast(Callable[[AcceptedInputs], list[object]], definition.derive)
        records = standard_derive(inputs)
        validate_output(definition, records)
        derived[definition.identifier] = tuple(records)
    return DerivedInventory(
        hole_patterns=cast(
            tuple[BoltCircle | LinearArray | RectGrid, ...],
            derived[DerivedId.HOLE_PATTERNS],
        ),
        slot_patterns=cast(tuple[SlotArray | SlotGrid, ...], derived[DerivedId.SLOT_PATTERNS]),
        pocket_patterns=cast(
            tuple[PocketArray | PocketGrid, ...], derived[DerivedId.POCKET_PATTERNS]
        ),
        passages=(),
    )


def _derive_passage_compat(
    inputs: AcceptedProjectionInputs, projection: ProjectionInputs
) -> tuple[Passage, ...]:
    definition = next(
        item for item in DERIVED_DEFINITIONS if item.identifier is DerivedId.PASSAGES_COMPAT
    )
    derive = cast(ProjectionDiscoverer, definition.derive)
    records = derive(inputs, projection)
    validate_output(definition, records)
    return cast(tuple[Passage, ...], tuple(records))


def _project_result(
    context: RecognitionContext,
    accepted: CandidateInventory,
    derived: DerivedInventory,
) -> RecognitionResult:
    """Project accepted and derived inventories without discovery or reconciliation."""

    z_cyls, cross_cyls = context.cylinders
    passage_definition = next(
        definition for definition in PHYSICAL_DEFINITIONS if definition.family is FamilyId.PASSAGES
    )
    return RecognitionResult(
        cylinders=(tuple(z_cyls), tuple(cross_cyls)),
        countersinks=tuple(_records(accepted, FamilyId.COUNTERSINKS, CounterSink)),
        holes=tuple(_records(accepted, FamilyId.HOLES, HoleRecord)),
        double_d_bores=tuple(_records(accepted, FamilyId.DOUBLE_D_BORES, DoubleDBore)),
        hole_patterns=derived.hole_patterns,
        bosses=tuple(_records(accepted, FamilyId.BOSSES, BossRecord)),
        polygonal_bosses=tuple(_records(accepted, FamilyId.POLYGONAL_BOSSES, PolygonalBoss)),
        polygonal_stock=tuple(_records(accepted, FamilyId.POLYGONAL_STOCK, PolygonalStock)),
        channels=tuple(_records(accepted, FamilyId.CHANNELS, Channel)),
        slots=tuple(_records(accepted, FamilyId.SLOTS, Slot)),
        slot_patterns=derived.slot_patterns,
        grooves=tuple(_records(accepted, FamilyId.GROOVES, Groove)),
        flats=tuple(_records(accepted, FamilyId.FLATS, Flat)),
        pockets=tuple(_records(accepted, FamilyId.POCKETS, Pocket)),
        prismatic_pockets=tuple(_records(accepted, FamilyId.PRISMATIC_POCKETS, PrismaticPocket)),
        pocket_patterns=derived.pocket_patterns,
        pads=tuple(_records(accepted, FamilyId.PADS, RaisedPad)),
        repeating_radial_profiles=tuple(
            _records(
                accepted,
                FamilyId.REPEATING_RADIAL_PROFILES,
                RepeatingRadialProfile,
            )
        ),
        turned_steps=tuple(_records(accepted, FamilyId.TURNED_STEPS, TurnedStep)),
        rotational=context.rotational,
        step_levels=tuple(_records(accepted, FamilyId.STEP_LEVELS, FaceLevel)),
        risers=tuple(_records(accepted, FamilyId.RISERS, RiserEvidence)),
        chamfers=tuple(_records(accepted, FamilyId.CHAMFERS, Chamfer)),
        angled_steps=tuple(_records(accepted, FamilyId.ANGLED_STEPS, AngledStep)),
        section_passages=(
            tuple(_records(accepted, FamilyId.PASSAGES, SectionPassage))
            if passage_definition.projected(context)
            else ()
        ),
        passages=derived.passages if passage_definition.projected(context) else (),
        fillets=tuple(_records(accepted, FamilyId.FILLETS, Fillet)),
        plates=tuple(_records(accepted, FamilyId.PLATES, Plate)),
    )
