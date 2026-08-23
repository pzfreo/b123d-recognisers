# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Run-local candidate identity and defining evidence for epic 0003.

Public recognition records compare by value.  A candidate is different: it is one proposal made
during one run, and two equal records may have been established by different faces.  Candidates
therefore compare by identity and can only be issued through :class:`EvidenceSink`, which validates
every face node against the run's graph before candidate and evidence become visible together.

Only defining evidence exists in this first slice.  Consulted and derived roles remain reserved
until real diagnostic consumers exist.  The sink intentionally has no lookup API; reconciliation
receives a separately frozen point-in-time index.  The sole aggregate-wide freeze remains a later
phase migration because unmigrated physical discovery still follows the first reconciliation.
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
    """Closed identifiers migrated to the candidate lifecycle so far.

    ``LEGACY`` is a temporary compatibility route for the existing ``ClaimLedger.add_defining``
    API.  It is not a public family and disappears when every physical family uses candidates.
    Adding a real member is an explicit integration change rather than an arbitrary string.
    """

    LEGACY = "legacy"
    ANGLED_STEPS = "angled_steps"
    PASSAGES = "passages"


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

    This is a copied prefix, not a live read-only facade.  The temporary legacy ledger may keep
    accepting proposals after a snapshot while aggregate phase migration is incomplete; those
    later proposals cannot appear here.  The one terminal freeze belongs to the later phase
    extraction, not this transitional capability.
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
        self.sink = EvidenceSink(self)

    def propose(
        self,
        family: FamilyId,
        record: RecordT,
        *,
        defining: Iterable[FaceNode],
    ) -> Candidate[RecordT]:
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
        result = object.__new__(CandidateSet)
        object.__setattr__(result, "family", family)
        object.__setattr__(result, "candidates", candidates)
        object.__setattr__(result, "_issuer", self._token)
        return result

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
