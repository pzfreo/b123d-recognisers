# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Closed internal execution registry for recognition orchestration.

The registry is deliberately not a plugin system and does not publish API or schema.  It owns
only physical discovery order, declared physical dependencies, neutral applicability, derived
pattern order, and explicit census coverage.  Public exports, capability metadata, result
projection, reconciliation policy, and census key order remain independently reviewed surfaces.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import TypeAlias, TypeVar, cast

from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import EvidenceWriter
from b123d_recognisers._features import (
    BoltCircle,
    BossRecord,
    HoleRecord,
    LinearArray,
    RectGrid,
    recognise_hole_patterns,
    recognise_holes,
)
from b123d_recognisers._hole_features import _discover_bosses
from b123d_recognisers._run import RecognitionContext
from b123d_recognisers._typing import CylinderInventory
from b123d_recognisers.angled_steps import AngledStep, recognise_angled_steps
from b123d_recognisers.chamfers import Chamfer, recognise_chamfers
from b123d_recognisers.countersinks import CounterSink, _discover_countersinks
from b123d_recognisers.fillets import Fillet, _discover_fillets
from b123d_recognisers.flats import Flat, _discover_flats
from b123d_recognisers.grooves import Groove, recognise_grooves
from b123d_recognisers.levels import FaceLevel, RiserEvidence, recognise_risers, step_level_records
from b123d_recognisers.pads import RaisedPad, recognise_rectangular_pads
from b123d_recognisers.passages import Passage, recognise_passages
from b123d_recognisers.plates import Plate, recognise_plates
from b123d_recognisers.polygonal_bosses import (
    PolygonalBoss,
    PolygonalStock,
    recognise_polygonal_bosses,
    recognise_polygonal_stock,
)
from b123d_recognisers.prismatic_pockets import PrismaticPocket, recognise_prismatic_pockets
from b123d_recognisers.profiled_bores import DoubleDBore, _discover_double_d_bores
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


@dataclass(frozen=True, slots=True)
class Counted:
    """A definition contributes to one existing stable census key."""

    key: str


@dataclass(frozen=True, slots=True)
class NotCounted:
    """A definition is deliberately absent from the feature census."""

    reason: str


CensusSpec: TypeAlias = Counted | NotCounted


@dataclass(frozen=True, slots=True)
class FullyAttributed:
    """Every aggregate output path has non-empty original-face defining evidence."""

    proof_contract: str


@dataclass(frozen=True, slots=True)
class IncompleteAttribution:
    """At least one output path lacks a reviewed complete ownership proof."""

    reason: str
    follow_up_or_exclusion: str


AttributionSpec: TypeAlias = FullyAttributed | IncompleteAttribution


class DerivedId(Enum):
    """Closed identifiers for post-reconciliation, non-physical projections."""

    HOLE_PATTERNS = "hole_patterns"
    SLOT_PATTERNS = "slot_patterns"
    POCKET_PATTERNS = "pocket_patterns"


@dataclass(frozen=True, slots=True)
class DiscoveryServices:
    """Run facts and the sole write capability available to registry adapters."""

    context: RecognitionContext
    writer: EvidenceWriter
    cylinders: CylinderInventory


RecordT = TypeVar("RecordT")


@dataclass(frozen=True, slots=True)
class CompletedInputs:
    """Read-only records for exactly one definition's declared predecessors."""

    _allowed: frozenset[FamilyId]
    _records: Mapping[FamilyId, tuple[object, ...]]

    @classmethod
    def restricted(
        cls,
        allowed: tuple[FamilyId, ...],
        completed: Mapping[FamilyId, tuple[object, ...]],
    ) -> CompletedInputs:
        missing = tuple(family for family in allowed if family not in completed)
        if missing:
            raise ValueError(
                "declared physical dependency has not completed: "
                + ", ".join(family.value for family in missing)
            )
        return cls(
            frozenset(allowed),
            MappingProxyType({family: completed[family] for family in allowed}),
        )

    def records(self, family: FamilyId, record_type: type[RecordT]) -> tuple[RecordT, ...]:
        if family not in self._allowed:
            raise ValueError(f"{family.value} is not a declared physical dependency")
        records = self._records[family]
        if not all(isinstance(record, record_type) for record in records):
            raise TypeError(f"{family.value} dependency has the wrong record type")
        return cast(tuple[RecordT, ...], records)


@dataclass(frozen=True, slots=True)
class AcceptedInputs:
    """Read-only accepted records for exactly one derived definition's sources."""

    _allowed: frozenset[FamilyId]
    _records: Mapping[FamilyId, tuple[object, ...]]

    @classmethod
    def restricted(
        cls,
        allowed: tuple[FamilyId, ...],
        accepted: Mapping[FamilyId, tuple[object, ...]],
    ) -> AcceptedInputs:
        return cls(
            frozenset(allowed),
            MappingProxyType({family: accepted[family] for family in allowed}),
        )

    def records(self, family: FamilyId, record_type: type[RecordT]) -> tuple[RecordT, ...]:
        if family not in self._allowed:
            raise ValueError(f"{family.value} is not a declared accepted source")
        records = self._records[family]
        if not all(isinstance(record, record_type) for record in records):
            raise TypeError(f"{family.value} source has the wrong record type")
        return cast(tuple[RecordT, ...], records)


PhysicalDiscoverer: TypeAlias = Callable[[DiscoveryServices, CompletedInputs], list[object]]
Applicability: TypeAlias = Callable[[RecognitionContext], bool]
DerivedDiscoverer: TypeAlias = Callable[[AcceptedInputs], list[object]]


def always(context: RecognitionContext) -> bool:
    del context
    return True


def prismatic(context: RecognitionContext) -> bool:
    return not context.rotational


@dataclass(frozen=True, slots=True)
class PhysicalDefinition:
    family: FamilyId
    record_types: tuple[type[object], ...]
    result_field: str
    public_entrypoint: str
    dependencies: tuple[FamilyId, ...]
    applicable: Applicability
    discover: PhysicalDiscoverer
    census: CensusSpec
    attribution: AttributionSpec
    projected: Applicability = always


@dataclass(frozen=True, slots=True)
class DerivedDefinition:
    identifier: DerivedId
    record_types: tuple[type[object], ...]
    result_field: str
    public_entrypoint: str
    sources: tuple[FamilyId, ...]
    derive: DerivedDiscoverer
    census: CensusSpec


def _simple(call: Callable[[DiscoveryServices], list[object]]) -> PhysicalDiscoverer:
    def discover(services: DiscoveryServices, inputs: CompletedInputs) -> list[object]:
        del inputs
        return call(services)

    return discover


def _holes(services: DiscoveryServices, inputs: CompletedInputs) -> list[object]:
    countersinks = list(inputs.records(FamilyId.COUNTERSINKS, CounterSink))
    return list(
        recognise_holes(
            services.context.part,
            cyls=services.cylinders,
            csinks=countersinks,
            face_edges=services.context.face_edges,
        )
    )


def _plates(services: DiscoveryServices, inputs: CompletedInputs) -> list[object]:
    steps = list(inputs.records(FamilyId.TURNED_STEPS, TurnedStep))
    if TurnedProfile.from_steps(steps) is not None:
        return []
    return list(recognise_plates(services.context.part))


def _hole_patterns(inputs: AcceptedInputs) -> list[object]:
    return list(recognise_hole_patterns(inputs.records(FamilyId.HOLES, HoleRecord)))


def _slot_patterns(inputs: AcceptedInputs) -> list[object]:
    return list(recognise_slot_patterns(inputs.records(FamilyId.SLOTS, Slot)))


def _pocket_patterns(inputs: AcceptedInputs) -> list[object]:
    return list(recognise_pocket_patterns(inputs.records(FamilyId.POCKETS, Pocket)))


PHYSICAL_DEFINITIONS: tuple[PhysicalDefinition, ...] = (
    PhysicalDefinition(
        FamilyId.COUNTERSINKS,
        (CounterSink,),
        "countersinks",
        "recognise_countersinks",
        (),
        always,
        _simple(lambda s: list(_discover_countersinks(s.context.part, writer=s.writer))),
        Counted("countersink"),
        FullyAttributed("every returned countersink claims its original conical seat face"),
    ),
    PhysicalDefinition(
        FamilyId.HOLES,
        (HoleRecord,),
        "holes",
        "recognise_holes",
        (FamilyId.COUNTERSINKS,),
        always,
        _holes,
        Counted("hole"),
        IncompleteAttribution(
            "no defining evidence is issued", "define bore and countersink roles"
        ),
    ),
    PhysicalDefinition(
        FamilyId.DOUBLE_D_BORES,
        (DoubleDBore,),
        "double_d_bores",
        "recognise_double_d_bores",
        (),
        always,
        _simple(
            lambda s: list(
                _discover_double_d_bores(
                    s.context.part,
                    face_edges=s.context.face_edges,
                    writer=s.writer,
                )
            )
        ),
        NotCounted("not a distinct census key"),
        FullyAttributed(
            "every returned Double-D bore claims its complete original lateral wall faces"
        ),
    ),
    PhysicalDefinition(
        FamilyId.BOSSES,
        (BossRecord,),
        "bosses",
        "recognise_bosses",
        (),
        always,
        _simple(
            lambda s: list(
                _discover_bosses(
                    s.context.part,
                    cyls=s.cylinders,
                    face_edges=s.context.face_edges,
                    writer=s.writer,
                )
            )
        ),
        Counted("boss"),
        FullyAttributed("every returned boss claims its original external segment faces"),
    ),
    PhysicalDefinition(
        FamilyId.POLYGONAL_BOSSES,
        (PolygonalBoss,),
        "polygonal_bosses",
        "recognise_polygonal_bosses",
        (),
        always,
        _simple(lambda s: list(recognise_polygonal_bosses(s.context.part, graph=s.context.graph))),
        NotCounted("not a distinct census key"),
        IncompleteAttribution("no defining evidence is issued", "migrate polygonal boss faces"),
    ),
    PhysicalDefinition(
        FamilyId.POLYGONAL_STOCK,
        (PolygonalStock,),
        "polygonal_stock",
        "recognise_polygonal_stock",
        (),
        always,
        _simple(lambda s: list(recognise_polygonal_stock(s.context.part, graph=s.context.graph))),
        NotCounted("stock context is not a machined feature"),
        IncompleteAttribution(
            "stock context is not machined-feature ownership", "reviewed structural exclusion"
        ),
    ),
    PhysicalDefinition(
        FamilyId.CHANNELS,
        (Channel,),
        "channels",
        "recognise_channels",
        (),
        always,
        _simple(
            lambda s: list(
                recognise_channels(s.context.part, ledger=s.writer, face_edges=s.context.face_edges)
            )
        ),
        Counted("channel"),
        IncompleteAttribution("writer is deliberately not used", "define channel owner faces"),
    ),
    PhysicalDefinition(
        FamilyId.SLOTS,
        (Slot,),
        "slots",
        "recognise_slots",
        (),
        always,
        _simple(
            lambda s: list(
                recognise_slots(s.context.part, ledger=s.writer, face_edges=s.context.face_edges)
            )
        ),
        Counted("slot"),
        IncompleteAttribution(
            "cap-recovered obround outputs have empty evidence", "migrate slot cap path"
        ),
    ),
    PhysicalDefinition(
        FamilyId.GROOVES,
        (Groove,),
        "grooves",
        "recognise_grooves",
        (),
        always,
        _simple(
            lambda s: list(
                recognise_grooves(
                    s.context.part,
                    cyls=s.cylinders,
                    ledger=s.writer,
                    face_edges=s.context.face_edges,
                )
            )
        ),
        Counted("groove"),
        FullyAttributed("every returned groove claims its defining groove faces"),
    ),
    PhysicalDefinition(
        FamilyId.FLATS,
        (Flat,),
        "flats",
        "recognise_flats",
        (),
        always,
        _simple(
            lambda s: list(
                _discover_flats(
                    s.context.part,
                    cyls=s.cylinders,
                    face_edges=s.context.face_edges,
                    writer=s.writer,
                )
            )
        ),
        Counted("flat"),
        FullyAttributed("every returned flat claims its defining planar truncation face"),
    ),
    PhysicalDefinition(
        FamilyId.POCKETS,
        (Pocket,),
        "pockets",
        "recognise_pockets",
        (),
        always,
        _simple(
            lambda s: list(
                recognise_pockets(s.context.part, ledger=s.writer, face_edges=s.context.face_edges)
            )
        ),
        Counted("pocket"),
        IncompleteAttribution(
            "cap-recovered obround outputs have empty evidence", "migrate pocket cap path"
        ),
    ),
    PhysicalDefinition(
        FamilyId.PRISMATIC_POCKETS,
        (PrismaticPocket,),
        "prismatic_pockets",
        "recognise_prismatic_pockets",
        (),
        always,
        _simple(
            lambda s: list(
                recognise_prismatic_pockets(
                    s.context.part, ledger=s.writer, face_edges=s.context.face_edges
                )
            )
        ),
        Counted("prismatic_pocket"),
        FullyAttributed("every returned prismatic pocket claims its defining boundary faces"),
    ),
    PhysicalDefinition(
        FamilyId.PADS,
        (RaisedPad,),
        "pads",
        "recognise_rectangular_pads",
        (),
        always,
        _simple(lambda s: list(recognise_rectangular_pads(s.context.part))),
        NotCounted("not a distinct census key"),
        IncompleteAttribution("no defining evidence is issued", "migrate raised-pad owner faces"),
    ),
    PhysicalDefinition(
        FamilyId.REPEATING_RADIAL_PROFILES,
        (RepeatingRadialProfile,),
        "repeating_radial_profiles",
        "recognise_repeating_radial_profiles",
        (),
        always,
        _simple(lambda s: list(recognise_repeating_radial_profiles(s.context.part))),
        NotCounted("correspondence evidence is not a distinct feature"),
        IncompleteAttribution(
            "correspondence records lack occurrence ownership",
            "review structural exclusion or prove source-face mapping",
        ),
    ),
    PhysicalDefinition(
        FamilyId.TURNED_STEPS,
        (TurnedStep,),
        "turned_steps",
        "recognise_turned_steps",
        (),
        always,
        _simple(
            lambda s: list(
                recognise_turned_steps(s.context.part, cyls=s.cylinders, ledger=s.writer)
            )
        ),
        Counted("step"),
        FullyAttributed("every returned turned step claims its defining profile faces"),
    ),
    PhysicalDefinition(
        FamilyId.STEP_LEVELS,
        (FaceLevel,),
        "step_levels",
        "recognise_face_levels",
        (),
        always,
        _simple(lambda s: list(step_level_records(s.context.part))),
        NotCounted("level substrate is not a distinct feature"),
        IncompleteAttribution(
            "level substrate lacks occurrence ownership", "review structural exclusion"
        ),
    ),
    PhysicalDefinition(
        FamilyId.RISERS,
        (RiserEvidence,),
        "risers",
        "recognise_risers",
        (),
        always,
        _simple(lambda s: list(recognise_risers(s.context.part))),
        NotCounted("riser evidence is not a distinct feature"),
        IncompleteAttribution(
            "riser analysis lacks occurrence ownership", "review structural exclusion"
        ),
    ),
    PhysicalDefinition(
        FamilyId.CHAMFERS,
        (Chamfer,),
        "chamfers",
        "recognise_chamfers",
        (),
        always,
        _simple(
            lambda s: list(
                recognise_chamfers(
                    s.context.part,
                    cyls=s.cylinders,
                    ledger=s.writer,
                    face_edges=s.context.face_edges,
                    include_planar=not s.context.rotational,
                )
            )
        ),
        Counted("chamfer"),
        FullyAttributed("every returned chamfer claims its defining bevel face"),
    ),
    PhysicalDefinition(
        FamilyId.ANGLED_STEPS,
        (AngledStep,),
        "angled_steps",
        "recognise_angled_steps",
        (),
        prismatic,
        _simple(
            lambda s: list(
                recognise_angled_steps(
                    s.context.part, ledger=s.writer, face_edges=s.context.face_edges
                )
            )
        ),
        Counted("angled_step"),
        FullyAttributed("every returned angled step claims its defining slant face"),
    ),
    PhysicalDefinition(
        FamilyId.PASSAGES,
        (Passage,),
        "passages",
        "recognise_passages",
        (),
        always,
        _simple(
            lambda s: list(
                recognise_passages(s.context.part, ledger=s.writer, face_edges=s.context.face_edges)
            )
        ),
        Counted("passage"),
        FullyAttributed("every returned passage claims its defining passage faces"),
        projected=prismatic,
    ),
    PhysicalDefinition(
        FamilyId.FILLETS,
        (Fillet,),
        "fillets",
        "recognise_fillets",
        (),
        always,
        _simple(
            lambda s: list(
                _discover_fillets(
                    s.context.part,
                    min_radius=None,
                    max_radius_frac=0.45,
                    cyls=s.cylinders,
                    face_edges=s.context.face_edges,
                    include_cylindrical=not s.context.rotational,
                    writer=s.writer,
                )
            )
        ),
        Counted("fillet"),
        FullyAttributed("every returned fillet claims its original curved blend face"),
    ),
    PhysicalDefinition(
        FamilyId.PLATES,
        (Plate,),
        "plates",
        "recognise_plates",
        (FamilyId.TURNED_STEPS,),
        prismatic,
        _plates,
        Counted("plate"),
        IncompleteAttribution("no defining evidence is issued", "prove plate source-face mapping"),
    ),
)


DERIVED_DEFINITIONS: tuple[DerivedDefinition, ...] = (
    DerivedDefinition(
        DerivedId.HOLE_PATTERNS,
        (BoltCircle, LinearArray, RectGrid),
        "hole_patterns",
        "recognise_hole_patterns",
        (FamilyId.HOLES,),
        _hole_patterns,
        Counted("hole_pattern"),
    ),
    DerivedDefinition(
        DerivedId.SLOT_PATTERNS,
        (SlotArray, SlotGrid),
        "slot_patterns",
        "recognise_slot_patterns",
        (FamilyId.SLOTS,),
        _slot_patterns,
        NotCounted("not a distinct census key"),
    ),
    DerivedDefinition(
        DerivedId.POCKET_PATTERNS,
        (PocketArray, PocketGrid),
        "pocket_patterns",
        "recognise_pocket_patterns",
        (FamilyId.POCKETS,),
        _pocket_patterns,
        NotCounted("not a distinct census key"),
    ),
)


def validate_definitions(
    physical: tuple[PhysicalDefinition, ...],
    derived: tuple[DerivedDefinition, ...],
) -> None:
    """Fail closed when the closed internal registry is incomplete or incoherent."""

    families = tuple(definition.family for definition in physical)
    expected = tuple(family for family in FamilyId if family is not FamilyId.LEGACY)
    if len(set(families)) != len(families) or set(families) != set(expected):
        raise ValueError("physical definitions must cover every non-legacy family exactly once")
    positions = {family: index for index, family in enumerate(families)}
    fields = [definition.result_field for definition in physical]
    if len(set(fields)) != len(fields):
        raise ValueError("physical result fields must be unique")
    counted_keys = [
        definition.census.key for definition in physical if isinstance(definition.census, Counted)
    ] + [definition.census.key for definition in derived if isinstance(definition.census, Counted)]
    if len(set(counted_keys)) != len(counted_keys) or any(not key for key in counted_keys):
        raise ValueError("counted census keys must be non-empty and unique")
    for index, definition in enumerate(physical):
        if not definition.record_types or not definition.public_entrypoint:
            raise ValueError("physical definitions require record and public contracts")
        if not isinstance(definition.census, Counted | NotCounted):
            raise ValueError("physical definitions require an explicit census disposition")
        if isinstance(definition.census, NotCounted) and not definition.census.reason:
            raise ValueError("not-counted census reasons must be non-empty")
        if not isinstance(definition.attribution, FullyAttributed | IncompleteAttribution):
            raise ValueError("physical definitions require an attribution disposition")
        if (
            isinstance(definition.attribution, FullyAttributed)
            and not definition.attribution.proof_contract.strip()
        ):
            raise ValueError("fully-attributed proof contracts must be non-empty")
        if isinstance(definition.attribution, IncompleteAttribution) and (
            not definition.attribution.reason.strip()
            or not definition.attribution.follow_up_or_exclusion.strip()
        ):
            raise ValueError("incomplete-attribution reasons and dispositions must be non-empty")
        if definition.applicable not in {always, prismatic}:
            raise ValueError("physical applicability must use a reviewed neutral predicate")
        if definition.projected not in {always, prismatic}:
            raise ValueError("physical projection must use a reviewed neutral predicate")
        if any(
            dependency not in positions or positions[dependency] >= index
            for dependency in definition.dependencies
        ):
            raise ValueError("physical dependencies must exist before their consumer")
    derived_ids = tuple(definition.identifier for definition in derived)
    if len(set(derived_ids)) != len(derived_ids) or set(derived_ids) != set(DerivedId):
        raise ValueError("derived definitions must cover every derived id exactly once")
    derived_fields = [definition.result_field for definition in derived]
    if len(set(derived_fields)) != len(derived_fields) or set(fields) & set(derived_fields):
        raise ValueError("registry result fields must be unique")
    for derived_definition in derived:
        if not derived_definition.record_types or not derived_definition.public_entrypoint:
            raise ValueError("derived definitions require record and public contracts")
        if not isinstance(derived_definition.census, Counted | NotCounted):
            raise ValueError("derived definitions require an explicit census disposition")
        if (
            isinstance(derived_definition.census, NotCounted)
            and not derived_definition.census.reason
        ):
            raise ValueError("not-counted census reasons must be non-empty")
        if any(source not in positions for source in derived_definition.sources):
            raise ValueError("derived sources must be registered physical families")


def validate_result_fields(result_fields: frozenset[str]) -> None:
    """Validate registry coverage against the independently declared public result fields."""

    registered = {definition.result_field for definition in PHYSICAL_DEFINITIONS} | {
        definition.result_field for definition in DERIVED_DEFINITIONS
    }
    if registered != result_fields:
        raise ValueError("registry fields do not exactly cover physical and derived results")


def validate_output(
    definition: PhysicalDefinition | DerivedDefinition,
    records: list[object],
) -> None:
    """Reject an adapter output that violates its declared record contract."""

    if not all(isinstance(record, definition.record_types) for record in records):
        raise TypeError(f"{definition.result_field} discovery returned an undeclared record type")


def validate_census_contract(
    expected: Mapping[str, str],
    physical: tuple[PhysicalDefinition, ...] = PHYSICAL_DEFINITIONS,
    derived: tuple[DerivedDefinition, ...] = DERIVED_DEFINITIONS,
) -> None:
    """Compare census key-to-source bindings with the independent manual census contract."""

    actual = {
        definition.result_field: definition.census.key
        for definition in physical
        if isinstance(definition.census, Counted)
    } | {
        definition.result_field: definition.census.key
        for definition in derived
        if isinstance(definition.census, Counted)
    }
    if actual != dict(expected):
        raise ValueError("registry census bindings do not match the manual census contract")


validate_definitions(PHYSICAL_DEFINITIONS, DERIVED_DEFINITIONS)
