# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Run-local candidate identity and defining evidence for epic 0003.

Public recognition records compare by value.  A candidate is different: it is one proposal made
during one run, and two equal records may have been established by different faces.  Candidates
therefore compare by identity and can only be issued through :class:`EvidenceSink`, which validates
every face node against the run's graph before candidate and evidence become visible together.

Only defining evidence exists in this slice.  Consulted and derived roles remain reserved until
real diagnostic consumers exist.  The sink intentionally has no lookup API; reconciliation
receives an immutable index only after aggregate discovery has issued every physical proposal and
the issuer has been terminally sealed.  Standalone compatibility paths may still take non-closing
point-in-time snapshots.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Generic, TypeVar

from b123d_recognisers._adjacency import FaceGraph, FaceNode

RecordT = TypeVar("RecordT")


class FamilyId(Enum):
    """Closed identifiers for every physical aggregate family.

    ``LEGACY`` remains only for standalone compatibility through ``ClaimLedger.add_defining``.
    It is not a physical aggregate family and aggregate completeness rejects it.
    Adding a real member is an explicit integration change rather than an arbitrary string.
    """

    LEGACY = "legacy"
    ANGLED_STEPS = "angled_steps"
    BOSSES = "bosses"
    CHAMFERS = "chamfers"
    CHANNELS = "channels"
    COUNTERSINKS = "countersinks"
    DOUBLE_D_BORES = "double_d_bores"
    FILLETS = "fillets"
    FLATS = "flats"
    GROOVES = "grooves"
    HOLES = "holes"
    PADS = "pads"
    PASSAGES = "passages"
    PLATES = "plates"
    POCKETS = "pockets"
    POLYGONAL_BOSSES = "polygonal_bosses"
    POLYGONAL_STOCK = "polygonal_stock"
    PRISMATIC_POCKETS = "prismatic_pockets"
    REPEATING_RADIAL_PROFILES = "repeating_radial_profiles"
    RISERS = "risers"
    SLOTS = "slots"
    STEP_LEVELS = "step_levels"
    TURNED_STEPS = "turned_steps"


@dataclass(frozen=True, slots=True)
class Evidence:
    """The graph nodes that establish one proposal."""

    defining: frozenset[FaceNode]


@dataclass(frozen=True, eq=False, init=False, slots=True)
class Candidate(Generic[RecordT]):
    """One sink-issued proposal, compared by run-local identity."""

    family: FamilyId
    record: RecordT
    evidence: Evidence
    _issuer: object = field(repr=False)


@dataclass(frozen=True, init=False, slots=True)
class CandidateSet(Generic[RecordT]):
    """The source-ordered candidates issued for one family."""

    family: FamilyId
    candidates: tuple[Candidate[RecordT], ...]
    _issuer: object = field(repr=False)


class EvidenceSink:
    """Write-only candidate/evidence capability handed to discovery."""

    __slots__ = ("__issuer",)

    def __init__(self, issuer: _CandidateIssuer) -> None:
        self.__issuer = issuer

    def propose(
        self,
        family: FamilyId,
        record: RecordT,
        *,
        defining: Iterable[FaceNode] = (),
    ) -> Candidate[RecordT]:
        """Atomically validate evidence and issue one identity-safe candidate."""

        return self.__issuer.propose(family, record, defining=defining)


@dataclass(frozen=True, init=False, slots=True)
class EvidenceIndex:
    """Immutable point-in-time evidence issued by one recognition run.

    This is a copy, not a live read-only facade. A standalone compatibility caller may snapshot
    an issued prefix and continue writing; those later proposals cannot appear here. Aggregate
    orchestration instead obtains the same read type from its one terminal freeze, after every
    physical proposal has been bound, then validates exact inventory coverage before any rule
    reads it. The index exposes neither creation mode nor a route back to the issuer.
    """

    _graph: FaceGraph = field(repr=False)
    _token: object = field(repr=False)
    _candidates: tuple[Candidate[object], ...] = field(repr=False)
    _issued: Mapping[int, _IssuedCandidate] = field(repr=False)
    _by_record: Mapping[int, tuple[Candidate[object], ...]] = field(repr=False)
    _by_node: Mapping[FaceNode, tuple[Candidate[object], ...]] = field(repr=False)

    def candidate_set(self, family: FamilyId) -> CandidateSet[object]:
        """Return the source-ordered candidates for *family* in this snapshot."""

        candidates = tuple(
            issued.candidate
            for candidate in self._candidates
            if (issued := self._validate(candidate)).family is family
        )
        result = object.__new__(CandidateSet)
        object.__setattr__(result, "family", family)
        object.__setattr__(result, "candidates", candidates)
        object.__setattr__(result, "_issuer", self._token)
        return result

    def candidate_set_for(
        self, family: FamilyId, records: Iterable[object]
    ) -> CandidateSet[object]:
        """Select accepted occurrences from this family's frozen candidates by identity."""

        available = list(self.candidate_set(family).candidates)
        selected: list[Candidate[object]] = []
        used: set[int] = set()
        for record in records:
            candidate = next(
                (
                    item
                    for item in available
                    if id(item) not in used and self._validate(item).record is record
                ),
                None,
            )
            if candidate is None:
                raise ValueError("accepted record has no candidate in this evidence snapshot")
            used.add(id(candidate))
            selected.append(candidate)
        result = object.__new__(CandidateSet)
        object.__setattr__(result, "family", family)
        object.__setattr__(result, "candidates", tuple(selected))
        object.__setattr__(result, "_issuer", self._token)
        return result

    def validate_complete_inventory(
        self, candidate_sets: tuple[CandidateSet[object], ...]
    ) -> None:
        """Prove one same-run, non-legacy inventory covers every frozen candidate once."""

        seen: set[int] = set()
        for candidate_set in candidate_sets:
            if candidate_set._issuer is not self._token:
                raise ValueError("candidate set belongs to another evidence issuer")
            if candidate_set.family is FamilyId.LEGACY:
                raise ValueError("legacy candidates are not aggregate physical proposals")
            for candidate in candidate_set.candidates:
                issued = self._validate(candidate)
                if issued.family is not candidate_set.family:
                    raise ValueError("candidate family does not match its candidate set")
                if id(candidate) in seen:
                    raise ValueError("candidate occurs more than once in physical inventory")
                seen.add(id(candidate))
        expected = {id(candidate) for candidate in self._candidates}
        if seen != expected:
            raise ValueError("physical inventory does not exactly cover frozen candidates")

    def defining_of(self, subject: object) -> frozenset[FaceNode]:
        """Return defining evidence by candidate identity.

        Record-object lookup is a private migration adapter for legacy filters.  It deliberately
        preserves the ledger's identity-based, last-proposal-wins behaviour and disappears once
        every physical output is a candidate.
        """

        if isinstance(subject, Candidate):
            return self._validate(subject).defining
        candidates = self._by_record.get(id(subject), ())
        return self._validate(candidates[-1]).defining if candidates else frozenset()

    def claims_of(self, node: FaceNode) -> tuple[Candidate[object], ...]:
        """Return candidates naming *node*, in proposal order."""

        if not self._graph.owns(node):
            raise ValueError(f"{node!r} is not this graph's node")
        candidates = self._by_node.get(node, ())
        for candidate in candidates:
            self._validate(candidate)
        return candidates

    def _validate(self, candidate: Candidate[object]) -> _IssuedCandidate:
        issued = self._issued.get(id(candidate))
        if issued is None or issued.candidate is not candidate:
            raise ValueError("candidate is not present in this evidence snapshot")
        if (
            candidate._issuer is not self._token
            or candidate.family is not issued.family
            or candidate.record is not issued.record
            or candidate.evidence is not issued.evidence
            or candidate.evidence.defining is not issued.defining
        ):
            raise ValueError("candidate no longer matches its issued state")
        return issued


@dataclass(frozen=True, slots=True)
class _IssuedCandidate:
    """Issuer-owned snapshot against which the outward Candidate is verified."""

    candidate: Candidate[object]
    family: FamilyId
    record: object
    evidence: Evidence
    defining: frozenset[FaceNode]


class _CandidateIssuer:
    """Mutable run store owned by the legacy ledger until its read/write views split."""

    def __init__(
        self,
        graph: FaceGraph,
        *,
        on_issued: Callable[[Candidate[object]], None] | None = None,
    ) -> None:
        self._graph = graph
        self._token = object()
        self._candidates: list[Candidate[object]] = []
        self._issued: dict[int, _IssuedCandidate] = {}
        self._by_record: dict[int, list[Candidate[object]]] = {}
        self._by_node: dict[FaceNode, list[Candidate[object]]] = {}
        self._on_issued = on_issued
        self._sealed = False
        self.sink = EvidenceSink(self)

    def propose(
        self,
        family: FamilyId,
        record: RecordT,
        *,
        defining: Iterable[FaceNode],
    ) -> Candidate[RecordT]:
        if self._sealed:
            raise RuntimeError("candidate issuance is sealed")
        nodes = frozenset(defining)
        foreign = [node for node in nodes if not self._graph.owns(node)]
        if foreign:
            raise ValueError(f"{sorted(node.index for node in foreign)} are not this graph's nodes")
        candidate = object.__new__(Candidate)
        object.__setattr__(candidate, "family", family)
        object.__setattr__(candidate, "record", record)
        object.__setattr__(candidate, "evidence", Evidence(nodes))
        object.__setattr__(candidate, "_issuer", self._token)
        self._candidates.append(candidate)
        self._issued[id(candidate)] = _IssuedCandidate(
            candidate,
            family,
            record,
            candidate.evidence,
            candidate.evidence.defining,
        )
        self._by_record.setdefault(id(record), []).append(candidate)
        for node in nodes:
            self._by_node.setdefault(node, []).append(candidate)
        if self._on_issued is not None:
            self._on_issued(candidate)
        return candidate

    @property
    def candidates(self) -> tuple[Candidate[object], ...]:
        for candidate in self._candidates:
            self._validate(candidate)
        return tuple(self._candidates)

    def candidate_set(self, family: FamilyId) -> CandidateSet[object]:
        candidates = tuple(
            issued.candidate
            for candidate in self._candidates
            if (issued := self._validate(candidate)).family is family
        )
        return self._make_candidate_set(family, candidates)

    def candidate_set_for(
        self, family: FamilyId, records: Iterable[object]
    ) -> CandidateSet[object]:
        """Map each returned record occurrence to exactly one family candidate.

        Named candidates already issued by a claim-writing recogniser are reused.  An output
        with no issued candidate receives one deliberate empty-evidence candidate.  Wrong-family
        issuance and candidates omitted from the returned inventory fail closed rather than being
        relabelled or silently retained.
        """

        ordered_records = tuple(records)
        available: dict[int, list[Candidate[object]]] = {
            key: list(value) for key, value in self._by_record.items()
        }
        used: set[int] = set()
        ordered: list[Candidate[object]] = []
        for record in ordered_records:
            candidates = available.get(id(record), [])
            wrong = [
                candidate
                for candidate in candidates
                if id(candidate) not in used and self._validate(candidate).family is not family
            ]
            if wrong:
                raise ValueError(f"record was issued under {self._validate(wrong[0]).family.value}")
            candidate = next(
                (
                    candidate
                    for candidate in candidates
                    if id(candidate) not in used
                    and self._validate(candidate).family is family
                ),
                None,
            )
            if candidate is None:
                candidate = self.propose(family, record, defining=())
                available.setdefault(id(record), []).append(candidate)
            used.add(id(candidate))
            ordered.append(candidate)

        issued_for_family = {
            id(candidate)
            for candidate in self._candidates
            if self._validate(candidate).family is family
        }
        if issued_for_family != used:
            raise ValueError("family issued candidates absent from its returned inventory")
        return self._make_candidate_set(family, tuple(ordered))

    def snapshot_index(self) -> EvidenceIndex:
        """Copy the currently issued prefix into an immutable read capability."""

        for candidate in self._candidates:
            self._validate(candidate)
        result = object.__new__(EvidenceIndex)
        object.__setattr__(result, "_graph", self._graph)
        object.__setattr__(result, "_token", self._token)
        object.__setattr__(result, "_candidates", tuple(self._candidates))
        object.__setattr__(result, "_issued", MappingProxyType(dict(self._issued)))
        object.__setattr__(
            result,
            "_by_record",
            MappingProxyType(
                {key: tuple(value) for key, value in self._by_record.items()}
            ),
        )
        object.__setattr__(
            result,
            "_by_node",
            MappingProxyType({key: tuple(value) for key, value in self._by_node.items()}),
        )
        return result

    def freeze_index(self) -> EvidenceIndex:
        """Seal aggregate issuance once and return its complete immutable evidence index."""

        if self._sealed:
            raise RuntimeError("candidate issuance is already sealed")
        index = self.snapshot_index()
        self._sealed = True
        return index

    def _make_candidate_set(
        self, family: FamilyId, candidates: tuple[Candidate[object], ...]
    ) -> CandidateSet[object]:
        result = object.__new__(CandidateSet)
        object.__setattr__(result, "family", family)
        object.__setattr__(result, "candidates", candidates)
        object.__setattr__(result, "_issuer", self._token)
        return result

    def defining_of(self, subject: object) -> frozenset[FaceNode]:
        if isinstance(subject, Candidate):
            return self._validate(subject).evidence.defining
        candidates = self._by_record.get(id(subject), ())
        return self._validate(candidates[-1]).evidence.defining if candidates else frozenset()

    def candidates_of(self, node: FaceNode) -> tuple[Candidate[object], ...]:
        if not self._graph.owns(node):
            raise ValueError(f"{node!r} is not this graph's node")
        candidates = tuple(self._by_node.get(node, ()))
        for candidate in candidates:
            self._validate(candidate)
        return candidates

    def _validate(self, candidate: Candidate[object]) -> _IssuedCandidate:
        issued = self._issued.get(id(candidate))
        if issued is None or issued.candidate is not candidate:
            raise ValueError("candidate was not issued by this run")
        if (
            candidate._issuer is not self._token
            or candidate.family is not issued.family
            or candidate.record is not issued.record
            or candidate.evidence is not issued.evidence
            or candidate.evidence.defining is not issued.defining
        ):
            raise ValueError("candidate no longer matches its issued state")
        return issued
