# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

import inspect
import types
import typing
from dataclasses import fields, replace
from inspect import signature

import pytest
from build123d import Box, Pos

import b123d_recognisers as public
import b123d_recognisers.result as result_module
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._record import Record
from b123d_recognisers._registry import (
    DERIVED_DEFINITIONS,
    PHYSICAL_DEFINITIONS,
    AcceptedInputs,
    CompletedInputs,
    Counted,
    DerivedId,
    FullyAttributed,
    IncompleteAttribution,
    NotCounted,
    always,
    prismatic,
    validate_census_contract,
    validate_definitions,
    validate_output,
    validate_result_fields,
)
from b123d_recognisers.census import CENSUS_BINDINGS, CENSUS_KEYS
from b123d_recognisers.result import MIGRATED, PHYSICAL_FAMILIES, RecognitionResult, _take_inventory


def test_registry_is_the_closed_ordered_internal_roster() -> None:
    assert len(PHYSICAL_DEFINITIONS) == 22
    assert len(DERIVED_DEFINITIONS) == 3
    assert tuple(item.family for item in PHYSICAL_DEFINITIONS) == PHYSICAL_FAMILIES
    assert set(PHYSICAL_FAMILIES) == set(FamilyId) - {FamilyId.LEGACY}
    assert tuple(item.identifier for item in DERIVED_DEFINITIONS) == tuple(DerivedId)
    assert all(isinstance(item.census, Counted | NotCounted) for item in PHYSICAL_DEFINITIONS)
    assert all(isinstance(item.census, Counted | NotCounted) for item in DERIVED_DEFINITIONS)
    assert {
        item.family
        for item in PHYSICAL_DEFINITIONS
        if isinstance(item.attribution, FullyAttributed)
    } == {
        FamilyId.PRISMATIC_POCKETS,
        FamilyId.PASSAGES,
        FamilyId.GROOVES,
        FamilyId.TURNED_STEPS,
        FamilyId.CHAMFERS,
        FamilyId.ANGLED_STEPS,
    }
    assert all(
        isinstance(item.attribution, FullyAttributed | IncompleteAttribution)
        for item in PHYSICAL_DEFINITIONS
    )
    assert PHYSICAL_FAMILIES == (
        FamilyId.COUNTERSINKS,
        FamilyId.HOLES,
        FamilyId.DOUBLE_D_BORES,
        FamilyId.BOSSES,
        FamilyId.POLYGONAL_BOSSES,
        FamilyId.POLYGONAL_STOCK,
        FamilyId.CHANNELS,
        FamilyId.SLOTS,
        FamilyId.GROOVES,
        FamilyId.FLATS,
        FamilyId.POCKETS,
        FamilyId.PRISMATIC_POCKETS,
        FamilyId.PADS,
        FamilyId.REPEATING_RADIAL_PROFILES,
        FamilyId.TURNED_STEPS,
        FamilyId.STEP_LEVELS,
        FamilyId.RISERS,
        FamilyId.CHAMFERS,
        FamilyId.ANGLED_STEPS,
        FamilyId.PASSAGES,
        FamilyId.FILLETS,
        FamilyId.PLATES,
    )


@pytest.mark.parametrize(
    "attribution",
    [
        FullyAttributed(""),
        FullyAttributed("   "),
        IncompleteAttribution("", "follow-up"),
        IncompleteAttribution("   ", "follow-up"),
        IncompleteAttribution("reason", ""),
        IncompleteAttribution("reason", "   "),
    ],
)
def test_registry_rejects_empty_attribution_contracts(attribution) -> None:
    changed = (replace(PHYSICAL_DEFINITIONS[0], attribution=attribution), *PHYSICAL_DEFINITIONS[1:])
    with pytest.raises(ValueError, match="attribut"):
        validate_definitions(changed, DERIVED_DEFINITIONS)


def test_terminal_validator_enforces_fully_attributed_all_occurrence_promise(
    monkeypatch,
) -> None:
    product = _take_inventory(Box(30, 30, 5) + Pos(10, 10, 5) * Box(10, 10, 5))
    assert product.physical.candidate_set(FamilyId.PADS).candidates
    definitions = tuple(
        replace(
            item,
            attribution=FullyAttributed("adversarially false completeness declaration"),
        )
        if item.family is FamilyId.PADS
        else item
        for item in PHYSICAL_DEFINITIONS
    )
    monkeypatch.setattr(result_module, "PHYSICAL_DEFINITIONS", definitions)
    with pytest.raises(ValueError, match="pads promises complete"):
        result_module._validate_attribution(product.context, product.physical, product.evidence)


def test_terminal_validator_rechecks_partial_family_body_provenance(monkeypatch) -> None:
    product = _take_inventory(Box(30, 30, 10) - Box(12, 5, 20))
    slot = product.physical.candidate_set(FamilyId.SLOTS).candidates[0]
    assert product.evidence.defining_of(slot)
    monkeypatch.setattr(product.context.graph, "common_valid_solid", lambda nodes: None)

    with pytest.raises(ValueError, match="lost its common valid solid"):
        result_module._validate_attribution(product.context, product.physical, product.evidence)


def test_terminal_validator_reads_issuer_snapshots_not_mutated_candidate_state() -> None:
    product = _take_inventory(Box(30, 30, 10) - Box(12, 5, 20))
    slot = product.physical.candidate_set(FamilyId.SLOTS).candidates[0]
    object.__setattr__(slot.evidence, "defining", frozenset())

    with pytest.raises(ValueError, match="no longer matches its issued state"):
        result_module._validate_attribution(product.context, product.physical, product.evidence)


def test_registry_dependencies_are_explicit_and_restricted() -> None:
    dependencies = {
        item.family: item.dependencies for item in PHYSICAL_DEFINITIONS if item.dependencies
    }
    assert dependencies == {
        FamilyId.HOLES: (FamilyId.COUNTERSINKS,),
        FamilyId.PLATES: (FamilyId.TURNED_STEPS,),
    }
    sources = {item.identifier: item.sources for item in DERIVED_DEFINITIONS}
    assert sources == {
        DerivedId.HOLE_PATTERNS: (FamilyId.HOLES,),
        DerivedId.SLOT_PATTERNS: (FamilyId.SLOTS,),
        DerivedId.POCKET_PATTERNS: (FamilyId.POCKETS,),
    }
    completed = CompletedInputs.restricted((FamilyId.HOLES,), {FamilyId.HOLES: ()})
    accepted = AcceptedInputs.restricted((FamilyId.SLOTS,), {FamilyId.SLOTS: ()})
    with pytest.raises(ValueError, match="not a declared"):
        completed.records(FamilyId.SLOTS, object)
    with pytest.raises(ValueError, match="not a declared"):
        accepted.records(FamilyId.HOLES, object)


def test_registry_rejects_wrong_typed_dependency_values() -> None:
    completed = CompletedInputs.restricted((FamilyId.HOLES,), {FamilyId.HOLES: (object(),)})
    with pytest.raises(TypeError, match="wrong record type"):
        completed.records(FamilyId.HOLES, public.HoleRecord)

    accepted = AcceptedInputs.restricted((FamilyId.HOLES,), {FamilyId.HOLES: (object(),)})
    with pytest.raises(TypeError, match="wrong record type"):
        accepted.records(FamilyId.HOLES, public.HoleRecord)


def test_registry_distinguishes_an_empty_dependency_from_one_not_run() -> None:
    completed = CompletedInputs.restricted((FamilyId.HOLES,), {FamilyId.HOLES: ()})
    assert completed.records(FamilyId.HOLES, public.HoleRecord) == ()

    with pytest.raises(ValueError, match="has not completed"):
        CompletedInputs.restricted((FamilyId.HOLES,), {})


def test_inapplicable_family_is_not_published_as_a_completed_dependency(monkeypatch) -> None:
    turned = next(item for item in PHYSICAL_DEFINITIONS if item.family is FamilyId.TURNED_STEPS)
    definitions = tuple(
        replace(item, applicable=prismatic) if item is turned else item
        for item in PHYSICAL_DEFINITIONS
    )
    monkeypatch.setattr(result_module, "PHYSICAL_DEFINITIONS", definitions)

    with pytest.raises(ValueError, match="turned_steps"):
        result_module.build_recognition_result(Box(20, 20, 10), rotational=True)


def test_registry_fields_and_public_entrypoints_have_independent_coverage() -> None:
    result_fields = {item.name for item in fields(RecognitionResult)}
    orchestration_context = {"cylinders", "rotational"}
    validate_result_fields(frozenset(result_fields - orchestration_context))
    assert {
        item.public_entrypoint for item in (*PHYSICAL_DEFINITIONS, *DERIVED_DEFINITIONS)
    } == MIGRATED
    assert all(hasattr(public, item.public_entrypoint) for item in PHYSICAL_DEFINITIONS)
    assert all(hasattr(public, item.public_entrypoint) for item in DERIVED_DEFINITIONS)
    manifest_entrypoints = {
        recogniser["entry_point"].removeprefix("b123d_recognisers.")
        for family in public.capability_manifest()["families"]
        for recogniser in family["recognisers"]
    }
    assert manifest_entrypoints == MIGRATED


def _record_types(annotation: object) -> set[type[Record]]:
    if inspect.isclass(annotation) and issubclass(typing.cast(type, annotation), Record):
        return {typing.cast(type[Record], annotation)}
    origin = typing.get_origin(annotation)
    if origin in {tuple, list, typing.Union, types.UnionType}:
        return set().union(*(_record_types(item) for item in typing.get_args(annotation)), set())
    return set()


def test_registry_record_types_match_public_entrypoints_and_result_fields() -> None:
    result_hints = typing.get_type_hints(RecognitionResult)
    for definition in (*PHYSICAL_DEFINITIONS, *DERIVED_DEFINITIONS):
        declared = set(definition.record_types)
        public_return = typing.get_type_hints(getattr(public, definition.public_entrypoint))[
            "return"
        ]
        assert declared == _record_types(public_return), definition.public_entrypoint
        assert declared == _record_types(result_hints[definition.result_field]), (
            definition.result_field
        )


def test_registry_rejects_runtime_output_outside_the_record_contract() -> None:
    holes = next(item for item in PHYSICAL_DEFINITIONS if item.family is FamilyId.HOLES)
    with pytest.raises(TypeError, match="undeclared record type"):
        validate_output(holes, [object()])


def test_registry_census_dispositions_cover_the_existing_manual_keys() -> None:
    counted = {
        definition.result_field: definition.census.key
        for definition in (*PHYSICAL_DEFINITIONS, *DERIVED_DEFINITIONS)
        if isinstance(definition.census, Counted)
    }
    assert counted == {source: key for key, source in CENSUS_BINDINGS}
    assert tuple(key for key, _source in CENSUS_BINDINGS) == CENSUS_KEYS

    swapped = tuple(
        replace(definition, census=Counted("boss"))
        if definition.family is FamilyId.HOLES
        else replace(definition, census=Counted("hole"))
        if definition.family is FamilyId.BOSSES
        else definition
        for definition in PHYSICAL_DEFINITIONS
    )
    with pytest.raises(ValueError, match="census bindings"):
        validate_census_contract(
            {source: key for key, source in CENSUS_BINDINGS}, swapped, DERIVED_DEFINITIONS
        )


def test_registry_applicability_is_context_only() -> None:
    for definition in PHYSICAL_DEFINITIONS:
        assert tuple(signature(definition.applicable).parameters) == ("context",)
        assert tuple(signature(definition.projected).parameters) == ("context",)
    assert {
        definition.family: definition.projected
        for definition in PHYSICAL_DEFINITIONS
        if definition.projected is not always
    } == {FamilyId.PASSAGES: prismatic}


def test_registry_validation_rejects_duplicate_missing_and_late_dependencies() -> None:
    with pytest.raises(ValueError, match="cover every non-legacy family"):
        validate_definitions(PHYSICAL_DEFINITIONS[:-1], DERIVED_DEFINITIONS)
    duplicate = (*PHYSICAL_DEFINITIONS[:-1], PHYSICAL_DEFINITIONS[0])
    with pytest.raises(ValueError, match="cover every non-legacy family"):
        validate_definitions(duplicate, DERIVED_DEFINITIONS)
    holes = next(item for item in PHYSICAL_DEFINITIONS if item.family is FamilyId.HOLES)
    invalid = tuple(
        replace(item, dependencies=(FamilyId.PLATES,)) if item is holes else item
        for item in PHYSICAL_DEFINITIONS
    )
    with pytest.raises(ValueError, match="dependencies must exist before"):
        validate_definitions(invalid, DERIVED_DEFINITIONS)
    duplicate_census = tuple(
        replace(item, census=Counted("hole")) if item.family is FamilyId.DOUBLE_D_BORES else item
        for item in PHYSICAL_DEFINITIONS
    )
    with pytest.raises(ValueError, match="census keys must be non-empty and unique"):
        validate_definitions(duplicate_census, DERIVED_DEFINITIONS)
    unreviewed_applicability = tuple(
        replace(item, applicable=lambda context: True) if item.family is FamilyId.BOSSES else item
        for item in PHYSICAL_DEFINITIONS
    )
    with pytest.raises(ValueError, match="reviewed neutral predicate"):
        validate_definitions(unreviewed_applicability, DERIVED_DEFINITIONS)
    unreviewed_projection = tuple(
        replace(item, projected=lambda context: True) if item.family is FamilyId.BOSSES else item
        for item in PHYSICAL_DEFINITIONS
    )
    with pytest.raises(ValueError, match="projection must use a reviewed neutral predicate"):
        validate_definitions(unreviewed_projection, DERIVED_DEFINITIONS)


def test_registry_validation_rejects_incomplete_physical_contract_metadata() -> None:
    first = PHYSICAL_DEFINITIONS[0]
    second = PHYSICAL_DEFINITIONS[1]

    duplicate_field = tuple(
        replace(item, result_field=first.result_field) if item is second else item
        for item in PHYSICAL_DEFINITIONS
    )
    with pytest.raises(ValueError, match="physical result fields must be unique"):
        validate_definitions(duplicate_field, DERIVED_DEFINITIONS)

    missing_record_contract = tuple(
        replace(item, record_types=()) if item is first else item for item in PHYSICAL_DEFINITIONS
    )
    with pytest.raises(ValueError, match="record and public contracts"):
        validate_definitions(missing_record_contract, DERIVED_DEFINITIONS)

    missing_census = tuple(
        replace(item, census=None) if item is first else item  # type: ignore[arg-type]
        for item in PHYSICAL_DEFINITIONS
    )
    with pytest.raises(ValueError, match="explicit census disposition"):
        validate_definitions(missing_census, DERIVED_DEFINITIONS)

    empty_reason = tuple(
        replace(item, census=NotCounted("")) if item is first else item
        for item in PHYSICAL_DEFINITIONS
    )
    with pytest.raises(ValueError, match="reasons must be non-empty"):
        validate_definitions(empty_reason, DERIVED_DEFINITIONS)


def test_registry_validation_rejects_incomplete_derived_contract_metadata() -> None:
    first = DERIVED_DEFINITIONS[0]

    with pytest.raises(ValueError, match="cover every derived id"):
        validate_definitions(PHYSICAL_DEFINITIONS, DERIVED_DEFINITIONS[:-1])

    overlapping_field = (
        replace(first, result_field=PHYSICAL_DEFINITIONS[0].result_field),
        *DERIVED_DEFINITIONS[1:],
    )
    with pytest.raises(ValueError, match="registry result fields must be unique"):
        validate_definitions(PHYSICAL_DEFINITIONS, overlapping_field)

    missing_record_contract = (
        replace(first, public_entrypoint=""),
        *DERIVED_DEFINITIONS[1:],
    )
    with pytest.raises(ValueError, match="record and public contracts"):
        validate_definitions(PHYSICAL_DEFINITIONS, missing_record_contract)

    missing_census = (
        replace(first, census=None),  # type: ignore[arg-type]
        *DERIVED_DEFINITIONS[1:],
    )
    with pytest.raises(ValueError, match="explicit census disposition"):
        validate_definitions(PHYSICAL_DEFINITIONS, missing_census)

    empty_reason = (
        replace(first, census=NotCounted("")),
        *DERIVED_DEFINITIONS[1:],
    )
    with pytest.raises(ValueError, match="reasons must be non-empty"):
        validate_definitions(PHYSICAL_DEFINITIONS, empty_reason)

    invalid_source = (
        replace(first, sources=(FamilyId.LEGACY,)),
        *DERIVED_DEFINITIONS[1:],
    )
    with pytest.raises(ValueError, match="sources must be registered"):
        validate_definitions(PHYSICAL_DEFINITIONS, invalid_source)


def test_registry_result_field_validation_rejects_stale_contract() -> None:
    fields_without_one = frozenset(
        item.result_field for item in (*PHYSICAL_DEFINITIONS, *DERIVED_DEFINITIONS)
    ) - {"holes"}
    with pytest.raises(ValueError, match="do not exactly cover"):
        validate_result_fields(fields_without_one)
