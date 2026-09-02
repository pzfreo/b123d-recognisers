"""Measure analytic recovery on an external STEP corpus without vendoring its models.

The scanner has two deliberately separate passes.  It first discovers every STEP member that
actually declares a B-spline surface, then chooses an evenly spaced deterministic sample from
that population.  Only those selected models are imported into OCCT.  This avoids presenting a
prefix of a provider's archive as a representative corpus and keeps the expensive geometry pass
bounded.

The report is observational evidence.  Corpus labels never tune recovery tolerances or recognition
predicates, and failed imports/refused fits remain counted rather than silently disappearing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import statistics
import sys
import tempfile
import zipfile
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from types import ModuleType
from typing import Any, BinaryIO, Protocol

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import OCP  # noqa: E402
import OCP.BRepAdaptor  # noqa: E402
from OCP.BRepAdaptor import BRepAdaptor_Surface  # noqa: E402
from OCP.GeomAbs import (  # noqa: E402
    GeomAbs_BezierSurface,
    GeomAbs_BSplineSurface,
    GeomAbs_Cone,
    GeomAbs_Cylinder,
    GeomAbs_Plane,
    GeomAbs_Sphere,
)
from OCP.gp import gp_Cone, gp_Cylinder, gp_Pln, gp_Sphere  # noqa: E402
from OCP.ShapeAnalysis import ShapeAnalysis_CanonicalRecognition  # noqa: E402

from b123d_recognisers import import_step_geometry as import_step  # noqa: E402
from b123d_recognisers._adjacency import FaceGraph, GraphRunToken  # noqa: E402
from b123d_recognisers._effective_surfaces import (  # noqa: E402
    AnalyticSurfaceFact,
    EffectiveFaceSurfaceQuery,
    EffectiveSurfaceIndex,
    MaterialSideRefusalReason,
    RefusedSurfaceFact,
    SurfaceProvenance,
    SurfaceRefusalReason,
    SurfaceUseRefusal,
    effective_faces_for_graph,
)
from b123d_recognisers._typing import FaceLike  # noqa: E402
from b123d_recognisers.pads import _discover_rectangular_pads  # noqa: E402
from b123d_recognisers.result import RecognitionResult, _take_inventory  # noqa: E402

FUSION_EXTENDED_STEP_URL = (
    "https://fusion-360-gallery-dataset.s3.us-west-2.amazonaws.com/"
    "segmentation/s2.0.1/s2.0.1_extended_step.zip"
)
FUSION_LICENSE_URL = (
    "https://github.com/AutodeskAILab/Fusion360GalleryDataset/blob/master/LICENSE.md"
)
FUSION_DOCUMENTATION_URL = (
    "https://github.com/AutodeskAILab/Fusion360GalleryDataset/blob/master/docs/segmentation.md"
)
JSON_REPORT = ROOT / "docs" / "benchmarks" / "nurbs-external-corpus-spike.json"
MARKDOWN_REPORT = ROOT / "docs" / "benchmarks" / "nurbs-external-corpus-spike.md"
MEASURED_RECOVERY_COMMIT = "63e6d3ae4dde11704e7806ef7bc29bff7535189c"
MEASURED_AT = "2026-08-28"
_STEP_SUFFIXES = (".step", ".stp")
_BSPLINE_DECLARATION = re.compile(rb"(?<![A-Z0-9_])B_SPLINE_SURFACE(?:_WITH_KNOTS)?\s*\(", re.ASCII)
_SPLINE_TYPES = frozenset({GeomAbs_BSplineSurface, GeomAbs_BezierSurface})
_NATIVE_SURFACE_ADAPTOR = BRepAdaptor_Surface
_COUNTERFACTUAL_TYPES = {
    "plane": GeomAbs_Plane,
    "cylinder": GeomAbs_Cylinder,
    "cone": GeomAbs_Cone,
    "sphere": GeomAbs_Sphere,
}


@dataclass(frozen=True, slots=True)
class _CounterfactualBinding:
    """One recovered primitive exposed to raw surface readers during a measurement run."""

    face: Any
    primitive: str
    analytic: Any


class _CounterfactualSurfaceAdaptor:
    """Surface adaptor overlay that preserves the original face and all non-analytic reads.

    The overlay deliberately changes only ``GetType`` and the matching analytic primitive getter.
    UV bounds, derivatives, topology and triangulation continue to come from the untouched
    exporter-produced B-spline. This is a measurement instrument, not a production migration.
    """

    bindings: tuple[_CounterfactualBinding, ...] = ()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._delegate = _NATIVE_SURFACE_ADAPTOR(*args, **kwargs)
        face = args[0] if args else None
        self._binding = next(
            (
                binding
                for binding in self.bindings
                if face is not None and bool(face.IsSame(binding.face))
            ),
            None,
        )

    def GetType(self):
        if self._binding is not None:
            return _COUNTERFACTUAL_TYPES[self._binding.primitive]
        return self._delegate.GetType()

    def Plane(self):
        if self._binding is not None and self._binding.primitive == "plane":
            return self._binding.analytic
        return self._delegate.Plane()

    def Cylinder(self):
        if self._binding is not None and self._binding.primitive == "cylinder":
            return self._binding.analytic
        return self._delegate.Cylinder()

    def Cone(self):
        if self._binding is not None and self._binding.primitive == "cone":
            return self._binding.analytic
        return self._delegate.Cone()

    def Sphere(self):
        if self._binding is not None and self._binding.primitive == "sphere":
            return self._binding.analytic
        return self._delegate.Sphere()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)


def _surface_reader_modules() -> Iterator[ModuleType]:
    """Yield loaded raw-reader modules while excluding the recovery implementation itself."""

    excluded = {
        "b123d_recognisers._analytic_surfaces",
        "b123d_recognisers._effective_surfaces",
    }
    for name, module in tuple(sys.modules.items()):
        if module is None or name in excluded:
            continue
        if name.startswith("b123d_recognisers.") or name == "build123d.topology.shape_core":
            yield module


@contextmanager
def _counterfactual_surfaces(bindings: list[_CounterfactualBinding]) -> Iterator[None]:
    """Expose recovered primitives to all current raw readers without changing the B-rep."""

    if _CounterfactualSurfaceAdaptor.bindings:
        raise RuntimeError("counterfactual surface overlays cannot be nested")
    patched: list[tuple[ModuleType, Any]] = []
    _CounterfactualSurfaceAdaptor.bindings = tuple(bindings)
    ocp_module = OCP.BRepAdaptor
    ocp_original = ocp_module.BRepAdaptor_Surface
    ocp_patched = False
    try:
        for module in _surface_reader_modules():
            if getattr(module, "BRepAdaptor_Surface", None) is _NATIVE_SURFACE_ADAPTOR:
                patched.append((module, _NATIVE_SURFACE_ADAPTOR))
                module.BRepAdaptor_Surface = _CounterfactualSurfaceAdaptor
        ocp_module.BRepAdaptor_Surface = _CounterfactualSurfaceAdaptor
        ocp_patched = True
        yield
    finally:
        if ocp_patched:
            ocp_module.BRepAdaptor_Surface = ocp_original
        for module, original in patched:
            module.BRepAdaptor_Surface = original
        _CounterfactualSurfaceAdaptor.bindings = ()


@dataclass(frozen=True, slots=True)
class Candidate:
    """One archive member with at least one STEP B-spline declaration."""

    name: str
    declarations: int
    uncompressed_bytes: int


class _ZipLike(Protocol):
    def infolist(self) -> list[zipfile.ZipInfo]: ...

    def open(self, name: str | zipfile.ZipInfo, mode: str = "r") -> BinaryIO: ...


class _NativeOnlyFaceSurfaces:
    """Counterfactual Pad query that makes recovered surfaces unavailable.

    Native facts and material-side certificates still come from the exact same graph/query.  This
    isolates the Pad result change caused by analytic recovery without maintaining a second
    recogniser implementation.
    """

    def __init__(self, delegate: EffectiveFaceSurfaceQuery) -> None:
        self._delegate = delegate

    @property
    def run_token(self) -> GraphRunToken:
        return self._delegate.run_token

    def fact(self, face: FaceLike):
        found = self._delegate.fact(face)
        if (
            isinstance(found, AnalyticSurfaceFact)
            and found.provenance is SurfaceProvenance.RECOVERED
        ):
            return RefusedSurfaceFact(found.node, SurfaceRefusalReason.UNSUPPORTED_KIND)
        return found

    def use(self, face: FaceLike, *, material_side: bool = False):
        found = self._delegate.fact(face)
        if (
            isinstance(found, AnalyticSurfaceFact)
            and found.provenance is SurfaceProvenance.RECOVERED
        ):
            return SurfaceUseRefusal(found.node, MaterialSideRefusalReason.SURFACE_UNAVAILABLE)
        return self._delegate.use(face, material_side=material_side)


def _counterfactual_binding(face: FaceLike, fact: AnalyticSurfaceFact) -> _CounterfactualBinding:
    """Re-run the certified fit and retain OCCT's full primitive coordinate frame."""

    primitives = {
        "plane": ("IsPlane", gp_Pln),
        "cylinder": ("IsCylinder", gp_Cylinder),
        "cone": ("IsCone", gp_Cone),
        "sphere": ("IsSphere", gp_Sphere),
    }
    method, constructor = primitives[fact.kind.value]
    primitive = constructor()
    recogniser = ShapeAnalysis_CanonicalRecognition(face.wrapped)
    if not bool(getattr(recogniser, method)(fact.requested_tolerance, primitive)):
        raise RuntimeError("certified analytic fit was not repeatable")
    if recogniser.GetStatus() != 0:
        raise RuntimeError("repeated analytic fit returned a non-zero status")
    gap = float(recogniser.GetGap())
    if gap > fact.requested_tolerance:
        raise RuntimeError("repeated analytic fit exceeded its certified tolerance")
    return _CounterfactualBinding(face.wrapped, fact.kind.value, primitive)


def _inventory_counts(result: RecognitionResult) -> dict[str, int]:
    """Flatten every public result family into a stable count map."""

    counts: dict[str, int] = {}
    for name in result.__dataclass_fields__:
        value = getattr(result, name)
        if name == "rotational":
            continue
        if name == "cylinders":
            counts["external_cylinder_patches"] = len(value[0])
            counts["internal_cylinder_patches"] = len(value[1])
            continue
        counts[name] = len(value)
    return counts


def _exception_record(exc: Exception) -> dict[str, str]:
    return {
        "exception": type(exc).__name__,
        "message": str(exc).splitlines()[0][:240],
    }


def _measure_counterfactual(
    part: Any,
    bindings: list[_CounterfactualBinding],
    *,
    rotational: bool = False,
) -> dict[str, Any]:
    """Compare untouched recognition with per-primitive and combined analytic overlays."""

    started = perf_counter()
    baseline_started = perf_counter()
    try:
        baseline = _inventory_counts(_take_inventory(part, rotational=rotational).result)
    except Exception as exc:  # noqa: BLE001 - an unsupported corpus model is measurement data
        return {
            "method": "raw-reader adaptor overlay; original TopoDS input remains unchanged",
            "baseline_error": _exception_record(exc),
            "scenarios": {},
            "baseline_timing_seconds": perf_counter() - baseline_started,
            "timing_seconds": perf_counter() - started,
        }
    baseline_timing = perf_counter() - baseline_started

    scenarios: dict[str, Any] = {}
    available = sorted({binding.primitive for binding in bindings})
    requested = [kind for kind in ("plane", "cylinder", "cone", "sphere") if kind in available]
    requested.append("combined")
    for scenario in requested:
        selected = (
            bindings if scenario == "combined" else [b for b in bindings if b.primitive == scenario]
        )
        scenario_started = perf_counter()
        try:
            with _counterfactual_surfaces(selected):
                observed = _inventory_counts(_take_inventory(part, rotational=rotational).result)
        except Exception as exc:  # noqa: BLE001 - overlay incompatibility is measurement data
            scenarios[scenario] = {
                "exposed_faces": len(selected),
                "error": _exception_record(exc),
                "timing_seconds": perf_counter() - scenario_started,
            }
            continue
        delta = {
            family: observed[family] - baseline[family]
            for family in baseline
            if observed[family] != baseline[family]
        }
        scenarios[scenario] = {
            "exposed_faces": len(selected),
            "counts": observed,
            "delta": delta,
            "timing_seconds": perf_counter() - scenario_started,
        }
    return {
        "method": "raw-reader adaptor overlay; original TopoDS input remains unchanged",
        "baseline_counts": baseline,
        "scenarios": scenarios,
        "baseline_timing_seconds": baseline_timing,
        "timing_seconds": perf_counter() - started,
    }


def _is_step(name: str) -> bool:
    return name.lower().endswith(_STEP_SUFFIXES)


def _count_declarations(stream: BinaryIO) -> int:
    """Count declarations across chunks, retaining enough overlap for split tokens."""

    count = 0
    overlap = b""
    while chunk := stream.read(1024 * 1024):
        data = overlap + chunk
        prefix = len(overlap)
        count += sum(match.end() > prefix for match in _BSPLINE_DECLARATION.finditer(data))
        overlap = data[-64:]
    return count


def discover(archive: _ZipLike, *, progress_every: int = 0) -> tuple[list[Candidate], int]:
    """Return all STEP members containing B-spline declarations and total STEP population."""

    candidates: list[Candidate] = []
    step_entries = sorted(
        (info for info in archive.infolist() if _is_step(info.filename)),
        key=lambda info: info.filename,
    )
    for at, info in enumerate(step_entries, 1):
        with archive.open(info) as stream:
            declarations = _count_declarations(stream)
        if declarations:
            candidates.append(Candidate(info.filename, declarations, info.file_size))
        if progress_every and at % progress_every == 0:
            print(
                f"discovery {at}/{len(step_entries)} STEP, {len(candidates)} B-spline-bearing",
                file=sys.stderr,
                flush=True,
            )
    return candidates, len(step_entries)


def uniform_sample(population: list[Candidate], limit: int) -> list[Candidate]:
    """Choose a stable sample spanning the complete sorted population."""

    if limit < 1:
        raise ValueError("sample limit must be positive")
    if len(population) <= limit:
        return list(population)
    if limit == 1:
        return [population[len(population) // 2]]
    indices = [round(at * (len(population) - 1) / (limit - 1)) for at in range(limit)]
    if len(set(indices)) != limit:
        raise RuntimeError("uniform sample produced duplicate indices")
    return [population[index] for index in indices]


def _segmentation_name(step_name: str) -> str:
    directory, separator, filename = step_name.rpartition("/step/")
    if not separator:
        return ""
    return f"{directory}/seg/{Path(filename).stem}.seg"


def _read_labels(archive: zipfile.ZipFile, step_name: str) -> tuple[int, ...] | None:
    name = _segmentation_name(step_name)
    if not name:
        return None
    try:
        with archive.open(name) as stream:
            return tuple(int(line) for line in stream.read().splitlines() if line.strip())
    except KeyError:
        return None


def _read_label_names(archive: zipfile.ZipFile) -> tuple[str, ...]:
    matches = sorted(
        info.filename
        for info in archive.infolist()
        if info.filename.endswith("/segment_names.json")
    )
    if len(matches) != 1:
        return ()
    with archive.open(matches[0]) as stream:
        found = json.load(stream)
    if not isinstance(found, list) or not all(isinstance(name, str) for name in found):
        return ()
    return tuple(found)


def _write_temporary_step(raw: bytes) -> str:
    handle, path = tempfile.mkstemp(suffix=".step", prefix="b123d-nurbs-spike-")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(raw)
    except BaseException:
        os.unlink(path)
        raise
    return path


def _measure_model(
    archive: zipfile.ZipFile,
    candidate: Candidate,
    label_names: tuple[str, ...],
) -> tuple[dict[str, Any], Counter[str], Counter[str]]:
    with archive.open(candidate.name) as stream:
        raw = stream.read()
    labels = _read_labels(archive, candidate.name)
    path = _write_temporary_step(raw)
    started = perf_counter()
    try:
        part = import_step(path)
    finally:
        os.unlink(path)
    imported_at = perf_counter()
    graph = FaceGraph(part)
    surfaces = EffectiveSurfaceIndex(graph)
    face_surfaces = effective_faces_for_graph(graph, surfaces)
    spline_nodes = []
    for node in graph.nodes:
        if BRepAdaptor_Surface(graph.face(node).wrapped).GetType() in _SPLINE_TYPES:
            spline_nodes.append(node)
    graphed_at = perf_counter()

    recovered: Counter[str] = Counter()
    refused: Counter[str] = Counter()
    label_outcomes: Counter[str] = Counter()
    recovered_certificates: list[dict[str, Any]] = []
    plane_material_side: Counter[str] = Counter()
    counterfactual_bindings: list[_CounterfactualBinding] = []
    binding_failures: Counter[str] = Counter()
    for node in spline_nodes:
        fact = surfaces.fact(node)
        label = "unlabelled"
        if labels is not None and len(labels) == len(graph.nodes):
            label_index = labels[node.index]
            label = (
                label_names[label_index]
                if 0 <= label_index < len(label_names)
                else f"unknown-{label_index}"
            )
        if isinstance(fact, AnalyticSurfaceFact):
            if fact.provenance is SurfaceProvenance.RECOVERED:
                recovered[fact.kind.value] += 1
                label_outcomes[f"{label}:recovered-{fact.kind.value}"] += 1
                recovered_certificates.append(
                    {
                        "face": node.index,
                        "operation_label": label,
                        "primitive": fact.kind.value,
                        "requested_tolerance": fact.requested_tolerance,
                        "kernel_reported_gap": fact.kernel_reported_gap,
                        "gap_fraction_of_tolerance": (
                            fact.kernel_reported_gap / fact.requested_tolerance
                            if fact.requested_tolerance
                            else 0.0
                        ),
                    }
                )
                try:
                    counterfactual_bindings.append(_counterfactual_binding(graph.face(node), fact))
                except Exception as exc:  # noqa: BLE001 - repeatability failure is evidence
                    binding_failures[type(exc).__name__] += 1
                if fact.kind.value == "plane":
                    use = face_surfaces.use(graph.face(node), material_side=True)
                    if isinstance(use, SurfaceUseRefusal):
                        plane_material_side[f"refused-{use.reason.value}"] += 1
                    else:
                        plane_material_side["certified"] += 1
            else:
                refused["unexpected-native-provenance"] += 1
                label_outcomes[f"{label}:unexpected-native-provenance"] += 1
        else:
            refused[fact.reason.value] += 1
            label_outcomes[f"{label}:refused-{fact.reason.value}"] += 1
    recovered_at = perf_counter()

    effective_pads: list[dict[str, Any]] = []
    native_only_pads: list[dict[str, Any]] = []
    if recovered.get("plane", 0):
        effective_pads = [
            record.to_dict()
            for record in _discover_rectangular_pads(part, face_surfaces=face_surfaces)
        ]
        native_only_pads = [
            record.to_dict()
            for record in _discover_rectangular_pads(
                part, face_surfaces=_NativeOnlyFaceSurfaces(face_surfaces)
            )
        ]
    counterfactual = None
    if counterfactual_bindings:
        counterfactual = {
            "prismatic": _measure_counterfactual(part, counterfactual_bindings),
            "rotational": _measure_counterfactual(part, counterfactual_bindings, rotational=True),
        }
    finished = perf_counter()
    row = {
        "entry": candidate.name,
        "step_bspline_declarations": candidate.declarations,
        "uncompressed_bytes": candidate.uncompressed_bytes,
        "faces": len(graph.nodes),
        "bspline_faces": len(spline_nodes),
        "segmentation_labels_available": labels is not None,
        "segmentation_face_count_matches": labels is not None and len(labels) == len(graph.nodes),
        "recovered_by_primitive": dict(sorted(recovered.items())),
        "recovered_certificates": recovered_certificates,
        "refused_by_reason": dict(sorted(refused.items())),
        "recovered_plane_material_side": dict(sorted(plane_material_side.items())),
        "effective_pad_records": effective_pads,
        "native_only_pad_records": native_only_pads,
        "counterfactual_binding_failures": dict(sorted(binding_failures.items())),
        "feature_counterfactual": counterfactual,
        "timing_seconds": {
            "import": imported_at - started,
            "graph_and_surface_classification": graphed_at - imported_at,
            "recovery": recovered_at - graphed_at,
            "pad_and_feature_counterfactual": finished - recovered_at,
            "total": finished - started,
        },
    }
    return (
        row,
        label_outcomes,
        Counter(
            {
                "faces": len(graph.nodes),
                "bspline_faces": len(spline_nodes),
                "recovered_faces": sum(recovered.values()),
                "refused_faces": sum(refused.values()),
                "models_with_recovery": bool(recovered),
                "models_with_recovered_plane": bool(recovered.get("plane", 0)),
                "models_with_pad_delta": effective_pads != native_only_pads,
                "recovered_plane_material_side_certified": plane_material_side["certified"],
                "recovered_plane_material_side_refused": sum(
                    count
                    for reason, count in plane_material_side.items()
                    if reason.startswith("refused-")
                ),
                "segmentation_labels_available": labels is not None,
                "segmentation_face_count_matches": labels is not None
                and len(labels) == len(graph.nodes),
            }
        ),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _certificate_summary(certificates: list[dict[str, Any]]) -> dict[str, Any]:
    by_primitive: dict[str, list[dict[str, Any]]] = {}
    for certificate in certificates:
        by_primitive.setdefault(certificate["primitive"], []).append(certificate)
    result = {}
    for primitive, group in sorted(by_primitive.items()):
        fractions = [certificate["gap_fraction_of_tolerance"] for certificate in group]
        labels = Counter(certificate["operation_label"] for certificate in group)
        result[primitive] = {
            "faces": len(group),
            "operation_labels": dict(sorted(labels.items())),
            "minimum_gap_fraction_of_tolerance": min(fractions),
            "median_gap_fraction_of_tolerance": statistics.median(fractions),
            "maximum_gap_fraction_of_tolerance": max(fractions),
            "above_one_percent_of_tolerance": sum(fraction > 0.01 for fraction in fractions),
            "above_half_of_tolerance": sum(fraction > 0.5 for fraction in fractions),
        }
    return result


def _orchestration_summary(rows: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "models_with_baseline_error": 0,
        "baseline_failures_by_exception": Counter(),
        "baseline_timing_seconds": 0.0,
        "total_timing_seconds": 0.0,
        "scenarios": {},
    }
    scenarios: dict[str, Any] = summary["scenarios"]
    for name in ("plane", "cylinder", "cone", "sphere", "combined"):
        scenarios[name] = {
            "eligible_models": 0,
            "completed_models": 0,
            "failed_models": 0,
            "changed_models": 0,
            "exposed_faces": 0,
            "baseline_counts_by_family": Counter(),
            "observed_counts_by_family": Counter(),
            "net_count_delta_by_family": Counter(),
            "gained_counts_by_family": Counter(),
            "lost_counts_by_family": Counter(),
            "models_changed_by_family": Counter(),
            "failures_by_exception": Counter(),
            "timing_seconds": 0.0,
        }

    for row in rows:
        by_mode = row["feature_counterfactual"]
        if by_mode is None:
            continue
        counterfactual = by_mode[mode]
        summary["baseline_timing_seconds"] += counterfactual["baseline_timing_seconds"]
        summary["total_timing_seconds"] += counterfactual["timing_seconds"]
        if "baseline_error" in counterfactual:
            summary["models_with_baseline_error"] += 1
            summary["baseline_failures_by_exception"][
                counterfactual["baseline_error"]["exception"]
            ] += 1
            continue
        baseline = counterfactual["baseline_counts"]
        for name, observed in counterfactual["scenarios"].items():
            aggregate = scenarios[name]
            aggregate["eligible_models"] += 1
            aggregate["exposed_faces"] += observed["exposed_faces"]
            aggregate["timing_seconds"] += observed["timing_seconds"]
            aggregate["baseline_counts_by_family"].update(baseline)
            if "error" in observed:
                aggregate["failed_models"] += 1
                aggregate["failures_by_exception"][observed["error"]["exception"]] += 1
                continue
            aggregate["completed_models"] += 1
            aggregate["observed_counts_by_family"].update(observed["counts"])
            delta = observed["delta"]
            if delta:
                aggregate["changed_models"] += 1
            for family, count in delta.items():
                aggregate["net_count_delta_by_family"][family] += count
                aggregate["models_changed_by_family"][family] += 1
                if count > 0:
                    aggregate["gained_counts_by_family"][family] += count
                else:
                    aggregate["lost_counts_by_family"][family] += -count

    for aggregate in scenarios.values():
        for key, value in tuple(aggregate.items()):
            if isinstance(value, Counter):
                aggregate[key] = dict(sorted(value.items()))
    summary["baseline_failures_by_exception"] = dict(
        sorted(summary["baseline_failures_by_exception"].items())
    )
    return summary


def _counterfactual_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate licensed per-model counterfactuals into publishable family totals."""

    return {
        "method": "raw-reader adaptor overlay; original TopoDS input remains unchanged",
        "scope": (
            "single-threaded prismatic and rotational orchestrations; candidate-count deltas are "
            "migration signals, not correctness claims because recovered orientation is not "
            "certified"
        ),
        "models_with_binding_repeatability_failure": sum(
            bool(row["counterfactual_binding_failures"]) for row in rows
        ),
        "orchestrations": {
            mode: _orchestration_summary(rows, mode) for mode in ("prismatic", "rotational")
        },
    }


def measure(
    path: Path,
    *,
    max_models: int,
    progress_every: int = 100,
) -> dict[str, Any]:
    """Measure one zip corpus and return a JSON-serializable report."""

    run_started = perf_counter()
    with zipfile.ZipFile(path) as archive:
        discovered, step_files = discover(archive, progress_every=progress_every)
        selected = uniform_sample(discovered, max_models)
        label_names = _read_label_names(archive)
        discovery_finished = perf_counter()
        rows: list[dict[str, Any]] = []
        totals: Counter[str] = Counter()
        recovered: Counter[str] = Counter()
        refused: Counter[str] = Counter()
        label_outcomes: Counter[str] = Counter()
        import_failures: Counter[str] = Counter()
        plane_material_side: Counter[str] = Counter()
        gap_fractions = []
        failed_entries = []
        recovered_certificates: list[dict[str, Any]] = []
        binding_failures: Counter[str] = Counter()
        for at, candidate in enumerate(selected, 1):
            try:
                row, labels, counts = _measure_model(archive, candidate, label_names)
            except Exception as exc:  # noqa: BLE001 - external corpus failures are evidence
                import_failures[type(exc).__name__] += 1
                failed_entries.append(
                    {
                        "entry": candidate.name,
                        "exception": type(exc).__name__,
                        "message": str(exc).splitlines()[0][:240],
                    }
                )
            else:
                rows.append(row)
                totals.update(counts)
                recovered.update(row["recovered_by_primitive"])
                refused.update(row["refused_by_reason"])
                label_outcomes.update(labels)
                plane_material_side.update(row["recovered_plane_material_side"])
                binding_failures.update(row["counterfactual_binding_failures"])
                gap_fractions.extend(
                    certificate["gap_fraction_of_tolerance"]
                    for certificate in row["recovered_certificates"]
                )
                recovered_certificates.extend(row["recovered_certificates"])
            if progress_every and at % progress_every == 0:
                print(
                    f"measurement {at}/{len(selected)}, recovered {totals['recovered_faces']}, "
                    f"failed {sum(import_failures.values())}",
                    file=sys.stderr,
                    flush=True,
                )
        measurement_finished = perf_counter()

    total_spline_faces = totals["bspline_faces"]
    return {
        "schema": 2,
        "dataset": {
            "name": "Fusion 360 Gallery Segmentation Extended STEP s2.0.1",
            "archive": path.name,
            "archive_bytes": path.stat().st_size,
            "archive_sha256": _sha256(path),
            "source_url": FUSION_EXTENDED_STEP_URL,
            "documentation_url": FUSION_DOCUMENTATION_URL,
            "license_url": FUSION_LICENSE_URL,
            "license_scope": "non-commercial research; dataset is not redistributed here",
        },
        "environment": {
            "measured_at": MEASURED_AT,
            "measured_recovery_commit": MEASURED_RECOVERY_COMMIT,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "occt": OCP.__version__,
        },
        "selection": {
            "method": "evenly spaced indices over sorted B-spline-bearing STEP entries",
            "step_files": step_files,
            "bspline_bearing_step_files": len(discovered),
            "bspline_bearing_step_file_rate": len(discovered) / step_files if step_files else 0.0,
            "requested_models": max_models,
            "selected_models": len(selected),
            "segmentation_label_names": list(label_names),
            "selected_entries_sha256": hashlib.sha256(
                "\n".join(candidate.name for candidate in selected).encode()
            ).hexdigest(),
        },
        "totals": {
            **dict(sorted(totals.items())),
            "successfully_imported_models": len(rows),
            "failed_models": sum(import_failures.values()),
            "step_bspline_declarations": sum(candidate.declarations for candidate in selected),
            "recovered_by_primitive": dict(sorted(recovered.items())),
            "refused_by_reason": dict(sorted(refused.items())),
            "recovered_plane_material_side": dict(sorted(plane_material_side.items())),
            "maximum_recovered_gap_fraction_of_tolerance": max(gap_fractions, default=0.0),
            "recovery_rate": (
                totals["recovered_faces"] / total_spline_faces if total_spline_faces else 0.0
            ),
            "recovered_model_rate": (
                totals["models_with_recovery"] / len(selected) if selected else 0.0
            ),
            "recovered_certificate_summary": _certificate_summary(recovered_certificates),
            "import_failures_by_exception": dict(sorted(import_failures.items())),
            "counterfactual_binding_failures_by_exception": dict(sorted(binding_failures.items())),
            "label_outcomes": dict(sorted(label_outcomes.items())),
        },
        "feature_counterfactual": _counterfactual_summary(rows),
        "timing_seconds": {
            "discovery": discovery_finished - run_started,
            "measurement": measurement_finished - discovery_finished,
            "total_before_archive_hash": measurement_finished - run_started,
        },
        "failed_entries": failed_entries,
        "models": rows,
    }


def markdown(report: dict[str, Any]) -> str:
    selection = report["selection"]
    totals = report["totals"]
    recovered = totals["recovered_by_primitive"]
    refused = totals["refused_by_reason"]
    curved_recovered = totals["recovered_faces"] - recovered.get("plane", 0)
    counterfactual = report["feature_counterfactual"]
    orchestrations = counterfactual["orchestrations"]

    def family_counts(values: dict[str, int]) -> str:
        nonzero = {family: count for family, count in values.items() if count}
        return ", ".join(f"{family} {count}" for family, count in nonzero.items()) or "none"

    counterfactual_rows = []
    for mode in ("prismatic", "rotational"):
        orchestration = orchestrations[mode]
        for name in ("plane", "cylinder", "cone", "sphere", "combined"):
            scenario = orchestration["scenarios"][name]
            counterfactual_rows.append(
                f"| {mode} | {name} | {scenario['eligible_models']} | "
                f"{scenario['completed_models']} | {scenario['changed_models']} | "
                f"{scenario['exposed_faces']} | "
                f"{family_counts(scenario['gained_counts_by_family'])} | "
                f"{family_counts(scenario['lost_counts_by_family'])} | "
                f"{scenario['timing_seconds']:.3f} |"
            )
    counterfactual_total = sum(
        orchestration["total_timing_seconds"] for orchestration in orchestrations.values()
    )
    baseline_total = sum(
        orchestration["baseline_timing_seconds"] for orchestration in orchestrations.values()
    )
    combined_prismatic = orchestrations["prismatic"]["scenarios"]["combined"]
    combined_rotational = orchestrations["rotational"]["scenarios"]["combined"]

    lines = [
        "# External NURBS corpus measurement spike",
        "",
        "Generated by `tools/nurbs_dataset_spike.py`. The external dataset is downloaded",
        "locally and is not redistributed by this repository.",
        f"Measured `{report['environment']['measured_at']}` at recovery commit",
        f"`{report['environment']['measured_recovery_commit']}` with Python",
        f"`{report['environment']['python']}` and OCCT `{report['environment']['occt']}`.",
        "",
        "## Dataset and selection",
        "",
        f"- Dataset: [{report['dataset']['name']}]({report['dataset']['documentation_url']})",
        f"- STEP files: `{selection['step_files']}`",
        f"- B-spline-bearing STEP files: `{selection['bspline_bearing_step_files']}`",
        f"  (`{100.0 * selection['bspline_bearing_step_file_rate']:.2f}%` of the archive)",
        f"- Deterministic evenly spaced sample: `{selection['selected_models']}` models",
        f"- Successful imports: `{totals['successfully_imported_models']}`; failures: "
        f"`{totals['failed_models']}`",
        f"- License: [non-commercial research terms]({report['dataset']['license_url']}); no",
        "  dataset bytes are checked in",
        "",
        "## Result",
        "",
        f"The selected models contain `{totals['bspline_faces']}` imported B-spline/Bezier faces.",
        f"Analytic recovery accepted `{totals['recovered_faces']}` "
        f"(`{100.0 * totals['recovery_rate']:.4f}%`) and refused "
        f"`{totals['refused_faces']}`.",
        "",
        "Recovered by primitive: "
        + (", ".join(f"{kind} {count}" for kind, count in recovered.items()) or "none")
        + ".",
        "Refused by reason: "
        + (", ".join(f"{reason} {count}" for reason, count in refused.items()) or "none")
        + ".",
        "",
        f"Models with any recovered face: `{totals['models_with_recovery']}`; with a recovered",
        f"plane: `{totals['models_with_recovered_plane']}`; with a Raised Pad result changed by",
        f"recovery: `{totals['models_with_pad_delta']}`.",
        f"Recovered plane material-side certificates: "
        f"`{totals['recovered_plane_material_side_certified']}` certified, "
        f"`{totals['recovered_plane_material_side_refused']}` refused.",
        f"The largest accepted kernel gap was "
        f"`{100.0 * totals['maximum_recovered_gap_fraction_of_tolerance']:.4f}%` of its "
        "face-local recovery tolerance.",
        "",
        f"Discovery took `{report['timing_seconds']['discovery']:.3f}` seconds and importing plus",
        f"measuring the selected models took `{report['timing_seconds']['measurement']:.3f}`",
        "seconds on the recorded environment.",
        f"Segmentation face counts matched on "
        f"`{totals['segmentation_face_count_matches']}/{totals['successfully_imported_models']}`",
        "models; unmatched faces remain measured but unlabelled.",
        "",
        "| primitive | faces | operation labels | median gap/tolerance | maximum | >50% |",
        "| --- | ---: | --- | ---: | ---: | ---: |",
        *(
            f"| {primitive} | {summary['faces']} | "
            + ", ".join(f"{label} {count}" for label, count in summary["operation_labels"].items())
            + f" | {summary['median_gap_fraction_of_tolerance']:.6f} | "
            f"{summary['maximum_gap_fraction_of_tolerance']:.6f} | "
            f"{summary['above_half_of_tolerance']} |"
            for primitive, summary in totals["recovered_certificate_summary"].items()
        ),
        "",
        "## Feature-unlock counterfactual",
        "",
        "For each model with a repeatable recovered fit, the spike ran the complete recognition",
        "inventory in both caller-selected classification modes on the untouched input and again",
        "through a temporary raw-reader adaptor overlay. Every public result family was counted.",
        "The overlay changed only the reported analytic surface kind and",
        "primitive; it did not replace faces or alter topology. Because recovered orientation is",
        "not certified, changed candidate counts are migration signals requiring inspection, not",
        "claims that the added results are correct.",
        "",
        "| orchestration | overlay | eligible | completed | changed | exposed faces | gains | "
        "losses | seconds |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- | ---: |",
        *counterfactual_rows,
        "",
        "Baseline inventory failures: "
        + "; ".join(
            f"{mode} `{orchestration['models_with_baseline_error']}` "
            f"({family_counts(orchestration['baseline_failures_by_exception'])})"
            for mode, orchestration in orchestrations.items()
        )
        + ". Fit repeatability failures: "
        f"`{counterfactual['models_with_binding_repeatability_failure']}`.",
        "The caller-supplied prismatic or rotational classification was held constant between",
        "each baseline and overlay, so the deltas isolate analytic visibility rather than a",
        "classification change.",
        f"Counterfactual inventory runs took `{counterfactual_total:.3f}` seconds in total,",
        f"including `{baseline_total:.3f}` seconds for the",
        "untouched baselines.",
        "",
        "## Interpretation",
        "",
    ]
    if totals["recovered_faces"]:
        lines.extend(
            [
                "This corpus contains exporter-produced B-spline faces accepted under the reviewed",
                "bounded analytic-recovery contract. Inspect the per-model residual evidence and",
                "recognition deltas before graduating another family.",
            ]
        )
    else:
        lines.extend(
            [
                "No selected exporter-produced B-spline face satisfied the reviewed exact analytic",
                "recovery contract. This sample supports retaining fail-closed recovery machinery",
                "but does not supply corpus evidence for migrating additional recogniser families.",
            ]
        )
    lines.extend(
        [
            "",
            f"The observed recovery is sparse: {totals['models_with_recovery']}/"
            f"{selection['selected_models']} models and {totals['recovered_faces']}/"
            f"{totals['bspline_faces']} spline faces. Curved",
            f"primitives account for {curved_recovered} of those faces, while the "
            f"{recovered.get('plane', 0)} recovered planes changed no",
            "Raised Pad result.",
            "The combined prismatic overlay changed "
            f"{combined_prismatic['changed_models']}/"
            f"{combined_prismatic['completed_models']} "
            "eligible models, with gains of "
            f"{family_counts(combined_prismatic['gained_counts_by_family'])}; "
            "the combined rotational overlay changed "
            f"{combined_rotational['changed_models']}/"
            f"{combined_rotational['completed_models']}, with "
            "gains of "
            f"{family_counts(combined_rotational['gained_counts_by_family'])}. "
            "This does not by",
            "itself justify blanket family migration: each changed family now has a measured",
            "candidate set for orientation and semantic review. Cylinder support is the only",
            "additional migration with a non-zero signal in this sample; planes and cones unlocked",
            "no result in either classification mode.",
            "",
            "This is one exporter and operation-labelled corpus, not a market-frequency estimate.",
            "Fusion labels identify modelling operations, not this project's semantic feature",
            "families. The sample was fixed before geometry measurement by evenly spacing over the",
            "complete sorted population of STEP files that declare B-spline surfaces.",
            "",
            "## Reproduce",
            "",
            "```console",
            "curl -L --fail --output /path/to/s2.0.1_extended_step.zip \\",
            f"  {report['dataset']['source_url']}",
            "uv run python tools/nurbs_dataset_spike.py \\",
            "  /path/to/s2.0.1_extended_step.zip --max-models 1000 --write",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def publication_report(report: dict[str, Any]) -> dict[str, Any]:
    """Remove model-level licensed data while retaining reproducible aggregate evidence."""

    return {key: value for key, value in report.items() if key not in {"models", "failed_entries"}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path, help="Fusion Extended STEP zip archive")
    parser.add_argument("--max-models", type=int, default=1000)
    parser.add_argument("--progress-every", type=int, default=100)
    parser.add_argument("--write", action="store_true", help="update checked-in JSON/Markdown")
    args = parser.parse_args()
    if args.max_models < 1:
        parser.error("--max-models must be positive")
    if args.progress_every < 0:
        parser.error("--progress-every cannot be negative")
    if not args.archive.is_file():
        parser.error(f"archive does not exist: {args.archive}")
    report = measure(
        args.archive,
        max_models=args.max_models,
        progress_every=args.progress_every,
    )
    if args.write:
        published = publication_report(report)
        JSON_REPORT.write_text(
            json.dumps(published, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        MARKDOWN_REPORT.write_text(markdown(published), encoding="utf-8")
    else:
        print(json.dumps(report, indent=2, sort_keys=True), end="\n")


if __name__ == "__main__":
    main()
