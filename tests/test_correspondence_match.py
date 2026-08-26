from __future__ import annotations

import ast
import math
from dataclasses import replace

import pytest
from build123d import (
    Align,
    Box,
    Compound,
    Cylinder,
    Plane,
    Polygon,
    Pos,
    Rot,
    export_step,
    extrude,
    import_step,
)
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface

import b123d_recognisers._correspondence_match as correspondence_match_module
from b123d_recognisers._body_geometry import ANGLE_TOL, DIRECTION_TOL
from b123d_recognisers._correspondence import correspondence_snapshot
from b123d_recognisers._correspondence_match import (
    IDENTITY_ROTATION,
    PROPER_ROTATIONS,
    ChangeKind,
    CorrespondenceMatchError,
    CorrespondenceRelation,
    CorrespondenceResult,
    RigidScaleWitness,
    _affine_point,
    _body_similarity,
    _compare_snapshots,
    _curve_similarity,
    _determinant,
    _direction_close,
    _face_similarity,
    _inverse_witness,
    _MatchBudget,
    _maximum_matchings,
    _order_bound,
    _scale_is_identity,
    _validate_result,
    _wire_alignments,
    correspondence_changes,
)
from b123d_recognisers._correspondence_partition import prism_fact
from b123d_recognisers.result import _take_inventory
from tests.test_correspondence_snapshot import (
    _line_rrp,
    _proper_signed_permutations,
    _proper_transform,
    _raw_planar_cycle_oracle,
    _rrp,
    _two_rrp_one_solid,
)


def _asymmetric_rrp():
    return _line_rrp(5) + Pos(18, 0, 5) * Box(
        4, 3, 2, align=(Align.CENTER, Align.CENTER, Align.CENTER)
    )


def _chiral_rrp():
    return (
        _line_rrp(5)
        + Pos(18, 0, 3) * Box(4, 3, 2, align=(Align.CENTER, Align.CENTER, Align.CENTER))
        + Pos(0, 18, 7) * Box(2, 5, 2, align=(Align.CENTER, Align.CENTER, Align.CENTER))
    )


def _partition_rrp(height: float, start: float = 0.0, *, phase: float = 13.0, repeats: int = 5):
    points = []
    for sector in range(repeats):
        for offset, radius in enumerate((20.0, 16.0, 20.0, 18.0)):
            angle = 2.0 * math.pi * (sector / repeats + offset / (4 * repeats))
            points.append((radius * math.cos(angle), radius * math.sin(angle)))
    return Pos(0, 0, start) * Rot(0, 0, phase) * extrude(Polygon(*points), height)


def _mixed_partition_rrp(
    height: float, start: float = 0.0, *, repeats: int = 7, phase: float = 13.0
):
    part = Cylinder(20, height)
    for index in range(repeats):
        part -= Rot(0, 0, phase + 360 * index / repeats) * Pos(18, 0, 0) * Box(8, 3, height)
    return Pos(0, 0, start + height / 2.0) * part


def _prism_fact_for(occurrence, *, graph=None, summary=None):
    summary = occurrence.summary if summary is None else summary
    return prism_fact(
        occurrence.matching_boundary if graph is None else graph,
        axis_name=summary.axis,
        span=summary.span,
        profile_centre=summary.centre,
        section_signature=summary.sector_signature,
        defining=summary.defining,
        repeat_count=summary.repeat_count,
        edge_count=summary.edge_count,
        volume=occurrence.body.intrinsic.volume,
        centre_of_mass=occurrence.body.placement.centre_of_mass,
        quantization=occurrence.body.quantization,
    )


def _raw_prism_partition_oracle(part):
    """Derive complete raw prism topology before any production snapshot is read."""

    solids = tuple(part.solids())
    facts = []
    for solid in solids:
        planar_cycles, raw_edges = _raw_planar_cycle_oracle(solid)
        faces = tuple(solid.faces())

        owners = {
            edge_at: tuple(
                face_at
                for face_at, face in enumerate(faces)
                if any(candidate.wrapped.IsSame(edge.wrapped) for candidate in face.edges())
            )
            for edge_at, edge in enumerate(raw_edges)
        }
        assert all(len(face_owners) == 2 for face_owners in owners.values())

        candidates = []
        planar_faces = tuple(
            face_at
            for face_at, face in enumerate(faces)
            if BRepAdaptor_Surface(face.wrapped).GetType().name == "GeomAbs_Plane"
            and (face_at, "outer") in planar_cycles
        )
        for left_at in planar_faces:
            for right_at in planar_faces:
                if right_at <= left_at:
                    continue
                left_face, right_face = faces[left_at], faces[right_at]
                left_normal = tuple(
                    float(value) for value in left_face.normal_at(left_face.center())
                )
                right_normal = tuple(
                    float(value) for value in right_face.normal_at(right_face.center())
                )
                if sum(a * b for a, b in zip(left_normal, right_normal, strict=True)) > -(
                    1.0 - 4.0 * DIRECTION_TOL
                ):
                    continue
                first_axis = next(value for value in left_normal if abs(value) > 1e-12)
                axis = tuple((1.0 if first_axis > 0.0 else -1.0) * value for value in left_normal)
                left_position = sum(
                    value * direction
                    for value, direction in zip(left_face.center(), axis, strict=True)
                )
                right_position = sum(
                    value * direction
                    for value, direction in zip(right_face.center(), axis, strict=True)
                )
                if right_position < left_position:
                    left_at, right_at = right_at, left_at
                    left_face, right_face = right_face, left_face
                    left_position, right_position = right_position, left_position
                low_cycle = planar_cycles[(left_at, "outer")]
                high_cycle = planar_cycles[(right_at, "outer")]
                low_edges = tuple(edge_at for edge_at, _direction in low_cycle)
                high_edges = tuple(edge_at for edge_at, _direction in high_cycle)
                low_sides = tuple(
                    next(face for face in owners[edge] if face != left_at) for edge in low_edges
                )
                high_sides = tuple(
                    next(face for face in owners[edge] if face != right_at) for edge in high_edges
                )
                if len(set(low_sides)) != len(low_sides) or set(low_sides) != set(high_sides):
                    continue
                side_set = set(low_sides)
                if side_set != set(range(len(faces))) - {left_at, right_at}:
                    continue
                if any(
                    sum(face in side_set for face in owners[edge]) != 2
                    for edge in owners
                    if edge not in set(low_edges) | set(high_edges)
                ):
                    continue
                side_pairs = tuple(
                    (
                        low_sides[index],
                        low_sides[(index + 1) % len(low_sides)],
                    )
                    for index in range(len(low_sides))
                )
                axial_pairs = {
                    tuple(sorted(owners[edge]))
                    for edge in owners
                    if edge not in set(low_edges) | set(high_edges)
                }
                if axial_pairs != {tuple(sorted(pair)) for pair in side_pairs}:
                    continue

                def label(edge_at: int, direction: int, raw_edges=raw_edges):
                    adaptor = BRepAdaptor_Curve(raw_edges[edge_at].wrapped)
                    kind = adaptor.GetType().name.removeprefix("GeomAbs_").upper()
                    base = (kind, round(float(raw_edges[edge_at].length), 9), direction)
                    if kind != "CIRCLE":
                        return base
                    circle = adaptor.Circle()
                    return (
                        *base,
                        round(float(circle.Radius()), 9),
                        round(float(adaptor.LastParameter() - adaptor.FirstParameter()), 12),
                    )

                low_labels = tuple(label(*item) for item in low_cycle)
                high_labels = tuple(label(*item) for item in high_cycle)

                def congruence_label(value):
                    if value[0] == "CIRCLE":
                        return (value[0], value[1], value[3], abs(value[4]))
                    return value[:2]

                # Both cycles are independently material-oriented; opposite cap normals reverse
                # the presentation while preserving the complete analytic curve roster.
                low_congruence = tuple(congruence_label(value) for value in low_labels)
                high_congruence = tuple(congruence_label(value) for value in high_labels)
                high_presentations = {
                    high_congruence[offset:] + high_congruence[:offset]
                    for offset in range(len(high_congruence))
                } | {
                    tuple(reversed(high_congruence))[offset:]
                    + tuple(reversed(high_congruence))[:offset]
                    for offset in range(len(high_congruence))
                }
                if low_congruence not in high_presentations:
                    continue
                candidates.append(
                    (
                        left_position,
                        right_position,
                        tuple(round(value, 12) for value in axis),
                        low_labels,
                        tuple(sorted(side_set)),
                        tuple(sorted(axial_pairs)),
                        float(solid.volume),
                        tuple(float(value) for value in solid.center()),
                    )
                )
        assert len(candidates) == 1
        facts.append(candidates[0])
    return tuple(facts)


def test_empty_products_have_one_successful_empty_correspondence() -> None:
    before = _take_inventory(Box(10, 10, 10))
    after = _take_inventory(Box(20, 10, 10))
    result = correspondence_changes(before, after)
    assert result.schema_version == 2
    assert result.before_schema == result.after_schema == 3
    assert result.relations == ()


def test_exact_occurrences_are_unchanged_without_symmetry_witnesses() -> None:
    before = _take_inventory(_line_rrp(5))
    after = _take_inventory(_line_rrp(5))
    result = correspondence_changes(before, after)
    assert [relation.kind for relation in result.relations] == [ChangeKind.UNCHANGED]
    (relation,) = result.relations
    assert relation.witness is None
    assert relation.candidate_witnesses == ()
    assert relation.before_refs[0].occurrence == correspondence_snapshot(before).occurrences[0]
    assert relation.after_refs[0].occurrence == correspondence_snapshot(after).occurrences[0]


def test_exact_equal_distinct_body_groups_remain_one_ambiguous_component() -> None:
    before = _take_inventory(Compound([_rrp(5), _rrp(5)]))
    after = _take_inventory(Compound([_rrp(5), _rrp(5)]))
    before_snapshot = correspondence_snapshot(before)
    after_snapshot = correspondence_snapshot(after)
    assert before_snapshot.body_groups == after_snapshot.body_groups == ((0,), (1,))
    assert before_snapshot.occurrences[0] == before_snapshot.occurrences[1]

    (relation,) = correspondence_changes(before, after).relations
    assert relation.kind is ChangeKind.AMBIGUOUS
    assert tuple(ref.position for ref in relation.before_refs) == (0, 1)
    assert tuple(ref.position for ref in relation.after_refs) == (0, 1)
    assert relation.witness is None


def test_empty_to_nonempty_and_inverse_preserve_every_occurrence() -> None:
    empty = _take_inventory(Box(10, 10, 10))
    populated = _take_inventory(_line_rrp(5))
    added = correspondence_changes(empty, populated)
    removed = correspondence_changes(populated, empty)
    assert [relation.kind for relation in added.relations] == [ChangeKind.ADDED]
    assert [relation.kind for relation in removed.relations] == [ChangeKind.REMOVED]
    assert (
        added.relations[0].after_refs[0].occurrence
        == removed.relations[0].before_refs[0].occurrence
    )


def test_unique_two_child_geometric_partition_and_inverse() -> None:
    whole = _take_inventory(_partition_rrp(10.0))
    pieces = _take_inventory(Compound([_partition_rrp(4.0), _partition_rrp(6.0, 4.0)]))
    split = correspondence_changes(whole, pieces)
    merge = correspondence_changes(pieces, whole)

    assert split.schema_version == merge.schema_version == 2
    (split_relation,) = split.relations
    (merge_relation,) = merge.relations
    assert split_relation.kind is ChangeKind.SPLIT
    assert merge_relation.kind is ChangeKind.MERGED
    assert len(split_relation.before_refs) == len(merge_relation.after_refs) == 1
    assert len(split_relation.after_refs) == len(merge_relation.before_refs) == 2
    assert split_relation.witness is not None
    assert merge_relation.witness == _inverse_witness(split_relation.witness)


@pytest.mark.parametrize(
    ("factory", "repeats", "expected"),
    [
        (_partition_rrp, 5, ChangeKind.SPLIT),
        (_mixed_partition_rrp, 7, ChangeKind.SPLIT),
        (_partition_rrp, 8, ChangeKind.AMBIGUOUS),
    ],
)
def test_reviewed_line_mixed_and_higher_prism_roster(
    factory, repeats: int, expected: ChangeKind
) -> None:
    whole_part = factory(10.0, repeats=repeats)
    pieces_part = Compound(
        [
            factory(4.0, repeats=repeats),
            factory(6.0, 4.0, repeats=repeats),
        ]
    )
    whole_oracle = _raw_prism_partition_oracle(whole_part)
    pieces_oracle = _raw_prism_partition_oracle(pieces_part)
    assert len(whole_oracle) == 1 and len(pieces_oracle) == 2
    assert pieces_oracle[0][0] == pytest.approx(whole_oracle[0][0])
    assert pieces_oracle[-1][1] == pytest.approx(whole_oracle[0][1])
    assert sum(fact[6] for fact in pieces_oracle) == pytest.approx(whole_oracle[0][6])

    whole = _take_inventory(whole_part)
    pieces = _take_inventory(pieces_part)
    (relation,) = correspondence_changes(whole, pieces).relations
    assert relation.kind is expected
    if expected is ChangeKind.AMBIGUOUS:
        assert len(relation.candidate_witnesses) == 4


def test_duplicate_partition_alternatives_make_the_whole_component_ambiguous() -> None:
    whole = _take_inventory(_partition_rrp(10.0))
    pieces = _take_inventory(
        Compound(
            [
                _partition_rrp(4.0),
                _partition_rrp(4.0),
                _partition_rrp(6.0, 4.0),
            ]
        )
    )
    (relation,) = correspondence_changes(whole, pieces).relations
    assert relation.kind is ChangeKind.AMBIGUOUS
    assert relation.candidate_witnesses


def test_gap_does_not_become_a_partial_geometric_partition() -> None:
    whole = _take_inventory(_partition_rrp(10.0))
    pieces = _take_inventory(Compound([_partition_rrp(4.0), _partition_rrp(5.0, 5.0)]))
    assert all(
        relation.kind not in {ChangeKind.SPLIT, ChangeKind.MERGED}
        for relation in correspondence_changes(whole, pieces).relations
    )


def test_prism_fact_binds_summary_winding_and_exact_incidence() -> None:
    occurrence = correspondence_snapshot(_take_inventory(_partition_rrp(10.0))).occurrences[0]
    graph = occurrence.matching_boundary
    summary = occurrence.summary
    assert _prism_fact_for(occurrence) is not None

    assert (
        _prism_fact_for(
            occurrence,
            summary=replace(summary, repeat_count=summary.repeat_count + 1),
        )
        is None
    )
    assert (
        _prism_fact_for(
            occurrence,
            summary=replace(summary, edge_count=summary.edge_count + 1),
        )
        is None
    )
    changed_signature = (
        "CIRCLE" if summary.sector_signature[0][0] == "LINE" else "LINE",
    ) + summary.sector_signature[0][1:]
    assert (
        _prism_fact_for(
            occurrence,
            summary=replace(
                summary,
                sector_signature=(changed_signature, *summary.sector_signature[1:]),
            ),
        )
        is None
    )
    sampled = summary.sector_signature[0][2]
    changed_sample = (sampled[0][0] + 1.0, sampled[0][1])
    changed_samples = (changed_sample, *sampled[1:])
    assert (
        _prism_fact_for(
            occurrence,
            summary=replace(
                summary,
                sector_signature=(
                    (*summary.sector_signature[0][:2], changed_samples),
                    *summary.sector_signature[1:],
                ),
            ),
        )
        is None
    )
    assert (
        _prism_fact_for(
            occurrence,
            summary=replace(
                summary,
                centre=(summary.centre[0] + 1.0, *summary.centre[1:]),
            ),
        )
        is None
    )
    changed_defining = replace(summary.defining[0], area=summary.defining[0].area + 1.0)
    assert (
        _prism_fact_for(
            occurrence,
            summary=replace(summary, defining=(changed_defining, summary.defining[1])),
        )
        is None
    )

    cap_at = next(
        at
        for at, face in enumerate(graph.faces)
        if face.kind == "PLANE"
        and len(face.parameters) == 4
        and abs(abs(face.parameters[2]) - 1.0) <= 4.0 * DIRECTION_TOL
    )
    cap = graph.faces[cap_at]
    changed_wire = replace(cap.wires[0], theta_winding=1)
    changed_faces = (
        *graph.faces[:cap_at],
        replace(cap, wires=(changed_wire,)),
        *graph.faces[cap_at + 1 :],
    )
    assert _prism_fact_for(occurrence, graph=replace(graph, faces=changed_faces)) is None

    half_edge = cap.wires[0].cycle[0]
    assert half_edge.start is not None
    changed_half_edge = replace(
        half_edge,
        start=replace(
            half_edge.start,
            parameter=(half_edge.start.parameter[0] + 1.0, half_edge.start.parameter[1]),
        ),
    )
    changed_cycle = (changed_half_edge, *cap.wires[0].cycle[1:])
    changed_wire = replace(cap.wires[0], cycle=changed_cycle)
    changed_faces = (
        *graph.faces[:cap_at],
        replace(cap, wires=(changed_wire,)),
        *graph.faces[cap_at + 1 :],
    )
    assert _prism_fact_for(occurrence, graph=replace(graph, faces=changed_faces)) is None

    cap_curve = cap.wires[0].cycle[0].curve
    incidence = dict(graph.incidence)
    incidence[cap_curve] = (*incidence[cap_curve], incidence[cap_curve][0])
    changed_incidence = tuple(sorted(incidence.items()))
    assert _prism_fact_for(occurrence, graph=replace(graph, incidence=changed_incidence)) is None


def test_two_independent_partitions_share_one_exact_cover_without_order_authority() -> None:
    before = _take_inventory(
        Compound(
            [
                Pos(-40, 0, 0) * _partition_rrp(10.0),
                Pos(40, 0, 0) * _partition_rrp(10.0, repeats=7),
            ]
        )
    )
    after = _take_inventory(
        Compound(
            [
                Pos(40, 0, 0) * _partition_rrp(3.0, repeats=7),
                Pos(-40, 0, 0) * _partition_rrp(4.0),
                Pos(40, 0, 3) * _partition_rrp(7.0, repeats=7),
                Pos(-40, 0, 4) * _partition_rrp(6.0),
            ]
        )
    )
    result = correspondence_changes(before, after)
    assert [relation.kind for relation in result.relations] == [
        ChangeKind.SPLIT,
        ChangeKind.SPLIT,
    ]
    assert sorted(len(relation.after_refs) for relation in result.relations) == [2, 2]


def test_partition_and_unrelated_multi_occurrence_f6b1_group_share_joint_cover() -> None:
    before = _take_inventory(
        Compound(
            [
                Pos(-90, 0, 0) * _partition_rrp(10.0),
                Pos(90, 0, 0) * _two_rrp_one_solid(),
            ]
        )
    )
    after = _take_inventory(
        Compound(
            [
                Pos(-90, 0, 0) * _partition_rrp(4.0),
                Pos(-90, 0, 4) * _partition_rrp(6.0),
                Pos(90, 0, 0) * _two_rrp_one_solid(),
            ]
        )
    )
    result = correspondence_changes(before, after)
    assert [relation.kind for relation in result.relations].count(ChangeKind.SPLIT) == 1
    assert [relation.kind for relation in result.relations].count(ChangeKind.UNCHANGED) == 2
    assert all(
        relation.kind not in {ChangeKind.ADDED, ChangeKind.REMOVED} for relation in result.relations
    )


def test_three_child_partition_accepts_one_shared_moved_scaled_rotation() -> None:
    whole = _take_inventory(_partition_rrp(10.0))
    pieces = Compound(
        [
            _partition_rrp(2.0),
            _partition_rrp(3.0, 2.0),
            _partition_rrp(5.0, 5.0),
        ]
    ).scale(1.25)
    pieces = Pos(3, -4, 7) * Rot(90, 0, 0) * pieces
    (relation,) = correspondence_changes(whole, _take_inventory(pieces)).relations
    assert relation.kind is ChangeKind.SPLIT
    assert len(relation.after_refs) == 3
    assert relation.witness is not None
    assert relation.witness.rotation == ((1, 0, 0), (0, 0, -1), (0, 1, 0))
    assert relation.witness.scale == pytest.approx(1.25, abs=1e-7)
    assert relation.witness.translation == pytest.approx((3.0, -4.0, 7.0), abs=1e-6)


def test_raw_partition_oracle_and_matcher_cover_all_24_proper_rotations() -> None:
    before = _take_inventory(_partition_rrp(10.0))
    low = _partition_rrp(4.0)
    high = _partition_rrp(6.0, 4.0)
    for rotation in _proper_signed_permutations():
        transformed = Compound(
            [_proper_transform(low, rotation), _proper_transform(high, rotation)]
        )
        raw = _raw_prism_partition_oracle(transformed)
        assert len(raw) == 2
        (relation,) = correspondence_changes(before, _take_inventory(transformed)).relations
        assert relation.kind is ChangeKind.SPLIT
        assert relation.witness is not None
        assert relation.witness.rotation == rotation


def test_partition_is_stable_through_step_roundtrip(tmp_path) -> None:
    whole_path = tmp_path / "partition-whole.step"
    pieces_path = tmp_path / "partition-pieces.step"
    whole_part = _partition_rrp(10.0)
    pieces_part = Compound([_partition_rrp(4.0), _partition_rrp(6.0, 4.0)])
    export_step(whole_part, whole_path)
    export_step(pieces_part, pieces_path)
    imported_whole = import_step(whole_path)
    imported_pieces = import_step(pieces_path)
    assert len(_raw_prism_partition_oracle(imported_whole)) == 1
    assert len(_raw_prism_partition_oracle(imported_pieces)) == 2
    (relation,) = correspondence_changes(
        _take_inventory(imported_whole), _take_inventory(imported_pieces)
    ).relations
    assert relation.kind is ChangeKind.SPLIT


def test_partition_witness_is_independent_of_unequal_child_presentation_order() -> None:
    before = correspondence_snapshot(_take_inventory(_partition_rrp(10.0)))
    after = correspondence_snapshot(
        _take_inventory(Compound([_partition_rrp(4.0), _partition_rrp(6.0, 4.0)]))
    )
    assert after.occurrences[0].body.quantization != after.occurrences[1].body.quantization
    direct = _compare_snapshots(before, after)
    reversed_after = replace(
        after,
        occurrences=tuple(reversed(after.occurrences)),
        body_groups=((0,), (1,)),
    )
    reversed_result = _compare_snapshots(before, reversed_after)
    assert [relation.kind for relation in direct.relations] == [ChangeKind.SPLIT]
    assert [relation.kind for relation in reversed_result.relations] == [ChangeKind.SPLIT]
    assert direct.relations[0].witness == reversed_result.relations[0].witness


def test_split_merge_result_shapes_and_candidate_witness_roster_are_closed() -> None:
    whole_product = _take_inventory(_partition_rrp(10.0))
    pieces_product = _take_inventory(Compound([_partition_rrp(4.0), _partition_rrp(6.0, 4.0)]))
    whole = correspondence_snapshot(whole_product)
    pieces = correspondence_snapshot(pieces_product)
    split = correspondence_changes(whole_product, pieces_product).relations[0]
    merge = correspondence_changes(pieces_product, whole_product).relations[0]
    assert split.witness is not None and merge.witness is not None

    malformed = (
        (replace(split, before_refs=()), whole, pieces),
        (replace(split, after_refs=split.after_refs[:1]), whole, pieces),
        (replace(split, candidate_witnesses=(split.witness,)), whole, pieces),
        (replace(merge, before_refs=merge.before_refs[:1]), pieces, whole),
        (replace(merge, after_refs=()), pieces, whole),
        (replace(merge, candidate_witnesses=(merge.witness,)), pieces, whole),
    )
    for relation, before_snapshot, after_snapshot in malformed:
        with pytest.raises(CorrespondenceMatchError, match="split|merge"):
            _validate_result(
                CorrespondenceResult(2, 3, 3, (relation,)),
                before_snapshot,
                after_snapshot,
            )

    symmetric_whole = _take_inventory(_partition_rrp(10.0))
    symmetric_pieces = _take_inventory(
        Compound(
            [
                _partition_rrp(4.0),
                _partition_rrp(4.0),
                _partition_rrp(6.0, 4.0),
            ]
        )
    )
    relation = correspondence_changes(symmetric_whole, symmetric_pieces).relations[0]
    before = correspondence_snapshot(symmetric_whole)
    after = correspondence_snapshot(symmetric_pieces)
    with pytest.raises(CorrespondenceMatchError, match="canonical"):
        _validate_result(
            CorrespondenceResult(
                2,
                3,
                3,
                (
                    replace(
                        relation,
                        candidate_witnesses=(
                            relation.candidate_witnesses[0],
                            relation.candidate_witnesses[0],
                        ),
                    ),
                ),
            ),
            before,
            after,
        )


def test_snapshot_only_leaf_rejects_unsupported_schema() -> None:
    product = _take_inventory(Box(10, 10, 10))
    snapshot = correspondence_snapshot(product)
    with pytest.raises(CorrespondenceMatchError, match="invalid"):
        _compare_snapshots(replace(snapshot, schema_version=1), snapshot)


def test_product_authority_is_required_before_snapshot_matching() -> None:
    product = _take_inventory(_line_rrp(5))
    copied = replace(product)
    with pytest.raises(CorrespondenceMatchError, match="authority"):
        correspondence_changes(copied, product)


def test_one_body_translation_has_one_shared_moved_witness() -> None:
    before = _take_inventory(_asymmetric_rrp())
    after = _take_inventory(Pos(11, -7, 3) * _asymmetric_rrp())
    result = correspondence_changes(before, after)
    assert [relation.kind for relation in result.relations] == [ChangeKind.MOVED]
    (relation,) = result.relations
    assert relation.witness is not None
    assert relation.witness.scale == 1.0
    assert relation.witness.translation == pytest.approx((11.0, -7.0, 3.0), abs=1e-6)


def test_uniform_scale_precedes_its_placement_change() -> None:
    before = _take_inventory(_asymmetric_rrp())
    after = _take_inventory((Pos(11, -7, 3) * _asymmetric_rrp()).scale(2.0))
    result = correspondence_changes(before, after)
    assert [relation.kind for relation in result.relations] == [ChangeKind.RESIZED]
    (relation,) = result.relations
    assert relation.witness is not None
    assert relation.witness.scale == pytest.approx(2.0, rel=1e-7)


def test_all_24_proper_rotations_produce_the_exact_supported_witness() -> None:
    part = _asymmetric_rrp()
    before = _take_inventory(part)
    for rotation in _proper_signed_permutations():
        relation = correspondence_changes(
            before, _take_inventory(_proper_transform(part, rotation))
        ).relations[0]
        if rotation == IDENTITY_ROTATION:
            assert relation.kind is ChangeKind.UNCHANGED
            assert relation.witness is None
        else:
            assert relation.kind is ChangeKind.MOVED
            assert relation.witness is not None
            assert relation.witness.rotation == rotation
            assert relation.witness.scale == pytest.approx(1.0, rel=1e-12)


def test_proper_rotation_scale_and_translation_share_one_affine_witness() -> None:
    part = _asymmetric_rrp()
    rotation = _proper_signed_permutations()[8]
    transformed = Pos(11, -7, 3) * _proper_transform(part, rotation).scale(2.0)
    relation = correspondence_changes(
        _take_inventory(part), _take_inventory(transformed)
    ).relations[0]
    assert relation.kind is ChangeKind.RESIZED
    assert relation.witness is not None
    assert relation.witness.rotation == rotation
    assert relation.witness.scale == pytest.approx(2.0, rel=1e-7)


def test_symmetric_nonidentity_witnesses_are_one_whole_ambiguity() -> None:
    before = _take_inventory(_line_rrp(5))
    after = _take_inventory(Pos(11, -7, 3) * _line_rrp(5))
    result = correspondence_changes(before, after)
    assert [relation.kind for relation in result.relations] == [ChangeKind.AMBIGUOUS]


def test_chiral_mirror_has_no_invented_proper_similarity() -> None:
    part = _chiral_rrp()
    result = correspondence_changes(_take_inventory(part), _take_inventory(part.mirror(Plane.YZ)))
    assert {relation.kind for relation in result.relations} == {
        ChangeKind.ADDED,
        ChangeKind.REMOVED,
    }


def test_representation_preserving_step_uses_identity_precedence(tmp_path) -> None:
    part = _asymmetric_rrp()
    path = tmp_path / "correspondence.step"
    assert export_step(part, path)
    relation = correspondence_changes(
        _take_inventory(part), _take_inventory(import_step(path))
    ).relations[0]
    assert relation.kind is ChangeKind.UNCHANGED
    assert relation.witness is None


def test_independent_unique_and_ambiguous_components_do_not_contaminate() -> None:
    unique = Pos(60, 0, 0) * _asymmetric_rrp()
    symmetric = Pos(-60, 0, 0) * _line_rrp(5)
    before = _take_inventory(Compound([unique, symmetric]))
    after = _take_inventory(Pos(11, -7, 3) * Compound([unique, symmetric]))
    result = correspondence_changes(before, after)
    assert sorted(relation.kind.value for relation in result.relations) == [
        "ambiguous",
        "moved",
    ]
    ambiguous = next(
        relation for relation in result.relations if relation.kind is ChangeKind.AMBIGUOUS
    )
    assert len(ambiguous.before_refs) == len(ambiguous.after_refs) == 1
    assert len(ambiguous.candidate_witnesses) > 1


def test_discrete_repeat_change_is_added_and_removed_not_resized() -> None:
    result = correspondence_changes(_take_inventory(_line_rrp(5)), _take_inventory(_line_rrp(7)))
    assert {relation.kind for relation in result.relations} == {
        ChangeKind.ADDED,
        ChangeKind.REMOVED,
    }


def test_equal_rrp_record_with_different_host_geometry_does_not_match() -> None:
    left = _line_rrp(5) + Pos(18, 0, 5) * Box(
        4, 3, 2, align=(Align.CENTER, Align.CENTER, Align.CENTER)
    )
    right = _line_rrp(5) + Pos(18, 0, 5) * Box(
        7, 2, 3, align=(Align.CENTER, Align.CENTER, Align.CENTER)
    )
    before = correspondence_snapshot(_take_inventory(left))
    after = correspondence_snapshot(_take_inventory(right))
    assert before.occurrences[0].record_value == after.occurrences[0].record_value
    result = correspondence_changes(_take_inventory(left), _take_inventory(right))
    assert {relation.kind for relation in result.relations} == {
        ChangeKind.ADDED,
        ChangeKind.REMOVED,
    }


def test_snapshot_tuple_permutation_changes_only_presentation_refs() -> None:
    before_product = _take_inventory(
        Compound([Pos(-60, 0, 0) * _asymmetric_rrp(), Pos(60, 0, 0) * _chiral_rrp()])
    )
    after_product = _take_inventory(
        Pos(11, -7, 3)
        * Compound([Pos(-60, 0, 0) * _asymmetric_rrp(), Pos(60, 0, 0) * _chiral_rrp()])
    )
    before = correspondence_snapshot(before_product)
    after = correspondence_snapshot(after_product)
    direct = _compare_snapshots(before, after)
    permuted_before = replace(
        before,
        occurrences=tuple(reversed(before.occurrences)),
        body_groups=tuple(
            sorted((len(before.occurrences) - 1 - group[0],) for group in before.body_groups)
        ),
    )
    permuted_after = replace(
        after,
        occurrences=tuple(reversed(after.occurrences)),
        body_groups=tuple(
            sorted((len(after.occurrences) - 1 - group[0],) for group in after.body_groups)
        ),
    )
    permuted = _compare_snapshots(permuted_before, permuted_after)
    assert [relation.kind for relation in direct.relations] == [
        relation.kind for relation in permuted.relations
    ]
    assert [relation.witness for relation in direct.relations] == [
        relation.witness for relation in permuted.relations
    ]


def test_one_group_cannot_distribute_into_two_equal_target_groups() -> None:
    before = _take_inventory(_line_rrp(5))
    after = _take_inventory(Compound([_line_rrp(5), _line_rrp(5)]))
    result = correspondence_changes(before, after)
    assert [relation.kind for relation in result.relations] == [ChangeKind.AMBIGUOUS]
    (relation,) = result.relations
    assert len(relation.before_refs) == 1
    assert len(relation.after_refs) == 2
    assert relation.witness is None


def test_moved_coincident_groups_remain_one_whole_ambiguity_component() -> None:
    before = _take_inventory(Compound([_line_rrp(5), _line_rrp(5)]))
    after = _take_inventory(Pos(11, -7, 3) * Compound([_line_rrp(5), _line_rrp(5)]))
    result = correspondence_changes(before, after)
    assert [relation.kind for relation in result.relations] == [ChangeKind.AMBIGUOUS]
    (relation,) = result.relations
    assert len(relation.before_refs) == len(relation.after_refs) == 2


def test_two_occurrences_on_one_body_share_one_group_witness() -> None:
    before = _take_inventory(_two_rrp_one_solid())
    after = _take_inventory(Pos(11, -7, 3) * _two_rrp_one_solid())
    result = correspondence_changes(before, after)
    assert [relation.kind for relation in result.relations] == [
        ChangeKind.MOVED,
        ChangeKind.MOVED,
    ]
    first, second = result.relations
    assert first.witness == second.witness
    assert first.witness is not None
    assert first.witness.translation == pytest.approx((11.0, -7.0, 3.0), abs=1e-6)


def test_two_occurrences_on_one_body_share_one_rotation_witness() -> None:
    part = _two_rrp_one_solid()
    rotation = _proper_signed_permutations()[9]
    result = correspondence_changes(
        _take_inventory(part), _take_inventory(_proper_transform(part, rotation))
    )
    assert [relation.kind for relation in result.relations] == [
        ChangeKind.MOVED,
        ChangeKind.MOVED,
    ]
    assert result.relations[0].witness == result.relations[1].witness
    assert result.relations[0].witness is not None
    assert result.relations[0].witness.rotation == rotation


def test_one_body_group_cannot_split_across_two_target_groups() -> None:
    before_product = _take_inventory(_two_rrp_one_solid())
    after_product = _take_inventory(Pos(11, -7, 3) * _two_rrp_one_solid())
    before = correspondence_snapshot(before_product)
    after = correspondence_snapshot(after_product)
    assert before.body_groups == after.body_groups == ((0, 1),)
    split_after = replace(after, body_groups=((0,), (1,)))
    forward = _compare_snapshots(before, split_after)
    inverse = _compare_snapshots(split_after, before)
    assert [relation.kind for relation in forward.relations] == [ChangeKind.AMBIGUOUS]
    assert [relation.kind for relation in inverse.relations] == [ChangeKind.AMBIGUOUS]
    assert len(forward.relations[0].before_refs) == 2
    assert len(forward.relations[0].after_refs) == 2


def test_unequal_weight_body_group_alternative_is_wholly_ambiguous() -> None:
    before_product = _take_inventory(_two_rrp_one_solid())
    after_product = _take_inventory(Pos(11, -7, 3) * _two_rrp_one_solid())
    before = correspondence_snapshot(before_product)
    after = correspondence_snapshot(after_product)
    expanded_after = replace(
        after,
        occurrences=(*after.occurrences, after.occurrences[0]),
        body_groups=((0, 1), (2,)),
    )
    forward = _compare_snapshots(before, expanded_after)
    inverse = _compare_snapshots(expanded_after, before)
    assert [relation.kind for relation in forward.relations] == [ChangeKind.AMBIGUOUS]
    assert [relation.kind for relation in inverse.relations] == [ChangeKind.AMBIGUOUS]
    assert len(forward.relations[0].before_refs) == 2
    assert len(forward.relations[0].after_refs) == 3


@pytest.mark.parametrize("scale", (1.0, 2.0))
def test_swapping_products_inverts_the_identity_rotation_witness(scale: float) -> None:
    before = _take_inventory(_asymmetric_rrp())
    transformed = (Pos(11, -7, 3) * _asymmetric_rrp()).scale(scale)
    after = _take_inventory(transformed)
    forward = correspondence_changes(before, after).relations[0]
    backward = correspondence_changes(after, before).relations[0]
    assert forward.kind is backward.kind
    assert forward.witness is not None and backward.witness is not None
    assert backward.witness.scale == pytest.approx(1.0 / forward.witness.scale, rel=1e-9)
    assert backward.witness.translation == pytest.approx(
        tuple(-value / forward.witness.scale for value in forward.witness.translation),
        abs=1e-6,
    )


def test_swapping_a_rotated_resize_uses_the_exact_inverse_witness() -> None:
    part = _asymmetric_rrp()
    rotation = _proper_signed_permutations()[8]
    transformed = Pos(11, -7, 3) * _proper_transform(part, rotation).scale(2.0)
    forward = correspondence_changes(_take_inventory(part), _take_inventory(transformed)).relations[
        0
    ]
    backward = correspondence_changes(
        _take_inventory(transformed), _take_inventory(part)
    ).relations[0]
    assert forward.kind is backward.kind is ChangeKind.RESIZED
    assert forward.witness is not None and backward.witness is not None
    assert backward.witness.rotation == _inverse_witness(forward.witness).rotation
    assert backward.witness.scale == pytest.approx(0.5, rel=1e-9)
    assert backward.witness.translation == pytest.approx(
        _inverse_witness(forward.witness).translation, abs=1e-6
    )


def test_hypothesis_budget_is_inclusive_and_never_truncates(monkeypatch) -> None:
    import b123d_recognisers._correspondence_match as module

    edges = {0: (0, 1), 1: (0, 1)}
    monkeypatch.setattr(module, "MATCH_HYPOTHESIS_BUDGET", 7)
    assert _maximum_matchings(2, 2, edges) == (
        ((0, 0), (1, 1)),
        ((0, 1), (1, 0)),
    )
    monkeypatch.setattr(module, "MATCH_HYPOTHESIS_BUDGET", 6)
    with pytest.raises(CorrespondenceMatchError, match="budget"):
        _maximum_matchings(2, 2, edges)


def test_late_global_budget_refusal_returns_no_prefix_or_input_mutation(monkeypatch) -> None:
    import b123d_recognisers._correspondence_match as module

    before_product = _take_inventory(_asymmetric_rrp())
    after_product = _take_inventory(Pos(11, -7, 3) * _asymmetric_rrp())
    before = correspondence_snapshot(before_product)
    after = correspondence_snapshot(after_product)
    monkeypatch.setattr(module, "MATCH_HYPOTHESIS_BUDGET", 1)
    with pytest.raises(CorrespondenceMatchError, match="budget"):
        correspondence_changes(before_product, after_product)
    assert correspondence_snapshot(before_product) == before
    assert correspondence_snapshot(after_product) == after


def test_reciprocal_scale_identity_boundary_is_inclusive_and_swap_stable() -> None:
    from b123d_recognisers._correspondence_match import SCALE_TOL

    upper = 1.0 + SCALE_TOL
    lower = 1.0 / upper
    assert _scale_is_identity(upper)
    assert _scale_is_identity(lower)
    assert not _scale_is_identity(float("nan"))
    assert not _scale_is_identity(0.0)
    assert not _scale_is_identity(float("inf"))
    assert not _scale_is_identity(math.nextafter(upper, math.inf))
    assert not _scale_is_identity(math.nextafter(lower, 0.0))


def test_complete_similarity_numeric_bounds_are_inclusive_and_nextafter_closed() -> None:
    occurrence = correspondence_snapshot(_take_inventory(_asymmetric_rrp())).occurrences[0]
    quantization = occurrence.body.quantization
    metric = _order_bound(quantization, quantization, 1.0, 1)
    area = _order_bound(quantization, quantization, 1.0, 2)
    volume = _order_bound(quantization, quantization, 1.0, 3)
    moment = _order_bound(quantization, quantization, 1.0, 5)
    assert _direction_close((0.0, 0.0, 0.0), (4.0 * DIRECTION_TOL, 0.0, 0.0))
    assert not _direction_close(
        (0.0, 0.0, 0.0),
        (math.nextafter(4.0 * DIRECTION_TOL, math.inf), 0.0, 0.0),
    )
    diagonal = 4.0 * DIRECTION_TOL / math.sqrt(2.0)
    assert _direction_close((0.0, 0.0, 0.0), (diagonal, diagonal, 0.0))
    outside_diagonal = math.nextafter(math.nextafter(diagonal, math.inf), math.inf)
    assert not _direction_close(
        (0.0, 0.0, 0.0),
        (outside_diagonal, outside_diagonal, 0.0),
    )

    line_index = next(
        index
        for index, curve in enumerate(occurrence.matching_boundary.curves)
        if curve.kind == "LINE"
    )
    line = occurrence.matching_boundary.curves[line_index]
    vertex_map = tuple(range(len(occurrence.matching_boundary.vertices)))
    assert (
        _curve_similarity(
            line,
            replace(line, length=line.length + metric),
            vertex_map,
            IDENTITY_ROTATION,
            1.0,
            metric,
        )
        is not None
    )
    assert (
        _curve_similarity(
            line,
            replace(line, length=math.nextafter(line.length + metric, math.inf)),
            vertex_map,
            IDENTITY_ROTATION,
            1.0,
            metric,
        )
        is None
    )

    curved_occurrence = correspondence_snapshot(_take_inventory(_rrp(5))).occurrences[0]
    curved_vertex_map = tuple(range(len(curved_occurrence.matching_boundary.vertices)))
    circle = next(
        curve
        for curve in curved_occurrence.matching_boundary.curves
        if curve.kind == "CIRCLE" and not curve.full
    )
    assert circle.sweep is not None
    sweep_inside = math.nextafter(circle.sweep + 4.0 * ANGLE_TOL, circle.sweep)
    assert (
        _curve_similarity(
            circle,
            replace(circle, sweep=sweep_inside),
            curved_vertex_map,
            IDENTITY_ROTATION,
            1.0,
            metric,
        )
        is not None
    )
    assert (
        _curve_similarity(
            circle,
            replace(
                circle,
                sweep=math.nextafter(circle.sweep + 4.0 * ANGLE_TOL, math.inf),
            ),
            curved_vertex_map,
            IDENTITY_ROTATION,
            1.0,
            metric,
        )
        is None
    )

    face = occurrence.matching_boundary.faces[0]
    assert (
        _face_similarity(
            face,
            replace(face, area=face.area + area),
            IDENTITY_ROTATION,
            1.0,
            metric,
            area,
        )
        is not None
    )
    assert (
        _face_similarity(
            face,
            replace(face, area=math.nextafter(face.area + area, math.inf)),
            IDENTITY_ROTATION,
            1.0,
            metric,
            area,
        )
        is None
    )

    for field, bound in (("volume", volume), ("surface_area", area)):
        intrinsic = occurrence.body.intrinsic
        changed = replace(intrinsic, **{field: getattr(intrinsic, field) + bound})
        target = replace(occurrence, body=replace(occurrence.body, intrinsic=changed))
        assert _body_similarity(
            occurrence,
            target,
            IDENTITY_ROTATION,
            1.0,
            _MatchBudget(),
        )
        outside = replace(
            intrinsic,
            **{field: math.nextafter(getattr(intrinsic, field) + bound, math.inf)},
        )
        assert not _body_similarity(
            occurrence,
            replace(occurrence, body=replace(occurrence.body, intrinsic=outside)),
            IDENTITY_ROTATION,
            1.0,
            _MatchBudget(),
        )

    intrinsic = occurrence.body.intrinsic
    moments = list(intrinsic.principal_moments)
    moments[0] += moment
    assert _body_similarity(
        occurrence,
        replace(
            occurrence,
            body=replace(
                occurrence.body,
                intrinsic=replace(intrinsic, principal_moments=tuple(moments)),
            ),
        ),
        IDENTITY_ROTATION,
        1.0,
        _MatchBudget(),
    )
    moments[0] = math.nextafter(moments[0], math.inf)
    assert not _body_similarity(
        occurrence,
        replace(
            occurrence,
            body=replace(
                occurrence.body,
                intrinsic=replace(intrinsic, principal_moments=tuple(moments)),
            ),
        ),
        IDENTITY_ROTATION,
        1.0,
        _MatchBudget(),
    )


def test_wire_alignment_enumerates_reversed_whole_wire_presentation() -> None:
    occurrence = correspondence_snapshot(_take_inventory(_asymmetric_rrp())).occurrences[0]
    graph = occurrence.matching_boundary
    face = next(face for face in graph.faces if face.kind == "PLANE" and face.wires)
    wire = face.wires[0]
    reversed_wire = replace(
        wire,
        cycle=tuple(
            replace(edge, start=edge.end, end=edge.start, direction=-edge.direction)
            for edge in reversed(wire.cycle)
        ),
        theta_winding=-wire.theta_winding,
    )
    alignments = _wire_alignments(
        wire,
        reversed_wire,
        face,
        replace(face, wires=(reversed_wire,)),
        tuple(range(len(graph.vertices))),
        tuple(range(len(graph.curves))),
        tuple(1 for _curve in graph.curves),
        graph.vertices,
        2,
        _order_bound(
            occurrence.body.quantization,
            occurrence.body.quantization,
            1.0,
            1,
        ),
        _MatchBudget(),
    )
    assert alignments


def test_proper_rotation_roster_and_affine_inverse_are_exact() -> None:
    assert len(PROPER_ROTATIONS) == 24
    assert len(set(PROPER_ROTATIONS)) == 24
    assert tuple(sorted(PROPER_ROTATIONS)) == PROPER_ROTATIONS
    point = (2.5, -3.0, 7.25)
    for rotation in PROPER_ROTATIONS:
        assert _determinant(rotation) == 1
        witness = RigidScaleWitness(rotation, (11.0, -7.0, 3.0), 2.0)
        transformed = _affine_point(
            witness.rotation,
            witness.translation,
            witness.scale,
            point,
        )
        inverse = _inverse_witness(witness)
        assert _affine_point(
            inverse.rotation,
            inverse.translation,
            inverse.scale,
            transformed,
        ) == pytest.approx(point, abs=1e-12)


@pytest.mark.parametrize(
    "witness",
    (
        RigidScaleWitness(((1, 0, 0), (0, -1, 0), (0, 0, 1)), (0.0, 0.0, 0.0), 1.0),
        RigidScaleWitness(IDENTITY_ROTATION, (0.0, float("nan"), 0.0), 1.0),
        RigidScaleWitness(IDENTITY_ROTATION, (0.0, 0.0, 0.0), 0.0),
    ),
)
def test_closed_result_validation_refuses_malformed_witnesses(
    witness: RigidScaleWitness,
) -> None:
    before_product = _take_inventory(_asymmetric_rrp())
    after_product = _take_inventory(Pos(2, 0, 0) * _asymmetric_rrp())
    before = correspondence_snapshot(before_product)
    after = correspondence_snapshot(after_product)
    relation = correspondence_changes(before_product, after_product).relations[0]
    malformed = CorrespondenceResult(2, 3, 3, (replace(relation, witness=witness),))
    with pytest.raises(CorrespondenceMatchError, match="witness"):
        _validate_result(malformed, before, after)


def test_closed_result_validation_refuses_kind_shape_drift() -> None:
    before_product = _take_inventory(_asymmetric_rrp())
    after_product = _take_inventory(Pos(2, 0, 0) * _asymmetric_rrp())
    before = correspondence_snapshot(before_product)
    after = correspondence_snapshot(after_product)
    moved = correspondence_changes(before_product, after_product).relations[0]
    malformed = CorrespondenceResult(
        2,
        3,
        3,
        (
            CorrespondenceRelation(
                ChangeKind.ADDED,
                moved.before_refs,
                moved.after_refs,
                moved.witness,
                (moved.witness,) if moved.witness is not None else (),
            ),
        ),
    )
    with pytest.raises(CorrespondenceMatchError, match="added"):
        _validate_result(malformed, before, after)


def test_closed_reference_and_result_schema_validation_matrix() -> None:
    product = _take_inventory(_asymmetric_rrp())
    snapshot = correspondence_snapshot(product)
    unchanged = correspondence_changes(product, _take_inventory(_asymmetric_rrp())).relations[0]

    for side, position, message in (
        ("wrong", 0, "malformed"),
        ("before", True, "malformed"),
        ("before", -1, "out of range"),
        ("before", len(snapshot.occurrences), "out of range"),
    ):
        with pytest.raises(CorrespondenceMatchError, match=message):
            correspondence_match_module._ref(side, position, snapshot)

    valid_ref = unchanged.before_refs[0]
    stale_ref = replace(valid_ref, occurrence=replace(valid_ref.occurrence, family="changed"))
    with pytest.raises(CorrespondenceMatchError, match="reference changed"):
        correspondence_match_module._validate_ref(stale_ref, snapshot)

    malformed_results = (
        (object(), "schema"),
        (replace(CorrespondenceResult(2, 3, 3, ()), schema_version=1), "schema"),
        (CorrespondenceResult(2, 3, 3, (object(),)), "relation"),
        (
            CorrespondenceResult(
                2,
                3,
                3,
                (replace(unchanged, before_refs=(replace(valid_ref, side="after"),)),),
            ),
            "wrong-side",
        ),
        (
            CorrespondenceResult(
                2,
                3,
                3,
                (
                    replace(
                        unchanged,
                        after_refs=(replace(unchanged.after_refs[0], side="before"),),
                    ),
                ),
            ),
            "wrong-side",
        ),
        (CorrespondenceResult(2, 3, 3, (replace(unchanged, kind=ChangeKind.ADDED),)), "added"),
        (CorrespondenceResult(2, 3, 3, (replace(unchanged, kind=ChangeKind.REMOVED),)), "removed"),
        (
            CorrespondenceResult(
                2,
                3,
                3,
                (replace(unchanged, before_refs=(), kind=ChangeKind.UNCHANGED),),
            ),
            "unchanged",
        ),
        (
            CorrespondenceResult(2, 3, 3, (replace(unchanged, kind=ChangeKind.MOVED),)),
            "transformed",
        ),
        (
            CorrespondenceResult(
                2,
                3,
                3,
                (
                    replace(
                        unchanged,
                        kind=ChangeKind.AMBIGUOUS,
                        witness=RigidScaleWitness(IDENTITY_ROTATION, (0.0, 0.0, 0.0), 1.0),
                    ),
                ),
            ),
            "ambiguous",
        ),
        (CorrespondenceResult(2, 3, 3, ()), "cover"),
    )
    for result, message in malformed_results:
        with pytest.raises(CorrespondenceMatchError, match=message):
            _validate_result(result, snapshot, snapshot)


def test_closed_bijection_search_covers_empty_unique_and_competing_assignments() -> None:
    assert correspondence_match_module._unique_bijection(((),)) is None
    assert correspondence_match_module._unique_bijection(((0,), (1,))) == (0, 1)
    assert correspondence_match_module._unique_bijection(((0, 1), (0, 1))) is None
    assert not correspondence_match_module._has_bijection(((),))
    assert correspondence_match_module._has_bijection(((0,), (1,)))
    assert not correspondence_match_module._has_bijection(((0,), (0,)))


def test_defining_face_and_rrp_signature_refusal_matrix() -> None:
    occurrence = correspondence_snapshot(_take_inventory(_asymmetric_rrp())).occurrences[0]
    quantization = occurrence.body.quantization
    plane = occurrence.summary.defining[0]
    assert correspondence_match_module._defining_face_similarity(
        plane, plane, IDENTITY_ROTATION, 1.0, quantization, quantization
    )
    assert not correspondence_match_module._defining_face_similarity(
        plane,
        replace(plane, parameters=plane.parameters[:-1]),
        IDENTITY_ROTATION,
        1.0,
        quantization,
        quantization,
    )
    assert not correspondence_match_module._defining_face_similarity(
        plane,
        replace(plane, parameters=(0.0, 1.0, 0.0, *plane.parameters[3:])),
        IDENTITY_ROTATION,
        1.0,
        quantization,
        quantization,
    )
    assert not correspondence_match_module._defining_face_similarity(
        plane,
        replace(plane, parameters=(*plane.parameters[:3], plane.parameters[3] + 1.0)),
        IDENTITY_ROTATION,
        1.0,
        quantization,
        quantization,
    )

    cylinder = replace(
        plane,
        kind="CYLINDER",
        parameters=(*plane.parameters[:3], 0.0, 0.0, 0.0, 2.0),
    )
    assert correspondence_match_module._defining_face_similarity(
        cylinder, cylinder, IDENTITY_ROTATION, 1.0, quantization, quantization
    )
    for changed in (
        replace(cylinder, parameters=(*cylinder.parameters[:3], 1.0, 0.0, 0.0, 2.0)),
        replace(cylinder, parameters=(*cylinder.parameters[:6], 3.0)),
        replace(cylinder, material_side=-cylinder.material_side),
        replace(cylinder, kind="SPHERE"),
    ):
        assert not correspondence_match_module._defining_face_similarity(
            cylinder, changed, IDENTITY_ROTATION, 1.0, quantization, quantization
        )

    signature = occurrence.summary.sector_signature
    metric = correspondence_match_module._order_bound(quantization, quantization, 1.0, 1)
    assert correspondence_match_module._signature_scaled(signature, signature, 1.0, metric)
    for malformed in (
        object(),
        signature[:-1],
        (("LINE",),),
        ((signature[0][0], signature[0][1], object()),),
        ((signature[0][0], signature[0][1], (*signature[0][2], (1.0, 2.0))),),
    ):
        assert not correspondence_match_module._signature_scaled(signature, malformed, 1.0, metric)


def test_occurrence_similarity_refuses_each_closed_rrp_authority_mismatch() -> None:
    occurrence = correspondence_snapshot(_take_inventory(_asymmetric_rrp())).occurrences[0]

    def witness(target):
        return correspondence_match_module._similarity_witness(
            occurrence, target, IDENTITY_ROTATION, _MatchBudget()
        )

    assert witness(occurrence) is not None
    intrinsic = occurrence.body.intrinsic
    quantization = occurrence.body.quantization
    summary = occurrence.summary
    mismatches = (
        replace(occurrence, family="OTHER"),
        replace(occurrence, record_type="Other"),
        replace(occurrence, summary=replace(summary, repeat_count=summary.repeat_count + 1)),
        replace(occurrence, summary=replace(summary, edge_count=summary.edge_count + 1)),
        replace(
            occurrence,
            body=replace(occurrence.body, intrinsic=replace(intrinsic, volume=0.0)),
        ),
        replace(
            occurrence,
            body=replace(
                occurrence.body,
                quantization=replace(quantization, characteristic_scale=float("nan")),
            ),
        ),
        replace(occurrence, summary=replace(summary, sector_signature=())),
        replace(occurrence, summary=replace(summary, centre=(999.0, 999.0, 999.0))),
        replace(occurrence, summary=replace(summary, axis="y" if summary.axis != "y" else "x")),
        replace(occurrence, summary=replace(summary, span=(999.0, 1000.0))),
        replace(
            occurrence,
            summary=replace(
                summary,
                defining=(
                    replace(summary.defining[0], kind="SPHERE"),
                    summary.defining[1],
                ),
            ),
        ),
    )
    assert all(witness(target) is None for target in mismatches)


def test_body_graph_similarity_refuses_each_complete_label_and_topology_mutation() -> None:
    occurrence = correspondence_snapshot(_take_inventory(_asymmetric_rrp())).occurrences[0]
    graph = occurrence.matching_boundary

    def refuses(changed_graph) -> bool:
        target = replace(occurrence, matching_boundary=changed_graph)
        return not _body_similarity(occurrence, target, IDENTITY_ROTATION, 1.0, _MatchBudget())

    assert _body_similarity(occurrence, occurrence, IDENTITY_ROTATION, 1.0, _MatchBudget())
    assert refuses(replace(graph, face_count=graph.face_count + 1))
    assert refuses(replace(graph, wire_count=graph.wire_count + 1))
    assert refuses(
        replace(
            graph,
            vertices=(
                (graph.vertices[0][0] + 1000.0, *graph.vertices[0][1:]),
                *graph.vertices[1:],
            ),
        )
    )

    line_at = next(index for index, curve in enumerate(graph.curves) if curve.kind == "LINE")
    line = graph.curves[line_at]
    curve_mutations = (
        (line_at, replace(line, kind="CIRCLE")),
        (line_at, replace(line, length=line.length + 1000.0)),
        (line_at, replace(line, vertices=None)),
    )
    for curve_at, changed in curve_mutations:
        curves = list(graph.curves)
        curves[curve_at] = changed
        assert refuses(replace(graph, curves=tuple(curves)))

    face_at = next(index for index, face in enumerate(graph.faces) if face.wires)
    face = graph.faces[face_at]
    wire = face.wires[0]
    face_mutations = (
        replace(face, kind="CYLINDER" if face.kind == "PLANE" else "PLANE"),
        replace(face, area=face.area + 1000.0),
        replace(face, centroid=(999.0, 999.0, 999.0)),
        replace(face, material_side=-face.material_side),
        replace(face, wires=()),
        replace(face, wires=(replace(wire, role="changed"), *face.wires[1:])),
        replace(
            face,
            wires=(replace(wire, theta_winding=wire.theta_winding + 7), *face.wires[1:]),
        ),
        replace(
            face,
            wires=(
                replace(
                    wire,
                    cycle=(replace(wire.cycle[0], curve=len(graph.curves)), *wire.cycle[1:]),
                ),
                *face.wires[1:],
            ),
        ),
    )
    for changed in face_mutations:
        faces = list(graph.faces)
        faces[face_at] = changed
        assert refuses(replace(graph, faces=tuple(faces)))

    assert refuses(replace(graph, incidence=graph.incidence[:-1]))


def test_curve_similarity_refuses_every_analytic_circle_field_mismatch() -> None:
    occurrence = correspondence_snapshot(_take_inventory(_rrp(5))).occurrences[0]
    graph = occurrence.matching_boundary
    circle = next(curve for curve in graph.curves if curve.kind == "CIRCLE" and not curve.full)
    metric = _order_bound(occurrence.body.quantization, occurrence.body.quantization, 1.0, 1)
    vertex_map = tuple(range(len(graph.vertices)))

    def similarity(target):
        return _curve_similarity(circle, target, vertex_map, IDENTITY_ROTATION, 1.0, metric)

    assert similarity(circle) is not None
    mutations = (
        replace(circle, kind="LINE"),
        replace(circle, centre=None),
        replace(circle, centre=(999.0, 999.0, 999.0)),
        replace(circle, axis=None),
        replace(circle, axis=(1.0, 0.0, 0.0)),
        replace(circle, radius=None),
        replace(circle, radius=(circle.radius or 0.0) + 1000.0),
        replace(circle, sweep=None),
        replace(circle, sweep=(circle.sweep or 0.0) + 1.0),
        replace(circle, full=True),
    )
    assert all(similarity(target) is None for target in mutations)

    line = next(curve for curve in graph.curves if curve.kind == "LINE")
    assert (
        _curve_similarity(
            line,
            replace(line, kind="CIRCLE"),
            vertex_map,
            IDENTITY_ROTATION,
            1.0,
            metric,
        )
        is None
    )

    full = replace(circle, vertices=None, sweep=2.0 * math.pi, full=True)
    assert _curve_similarity(full, full, vertex_map, IDENTITY_ROTATION, 1.0, metric) is not None
    assert (
        _curve_similarity(
            full,
            replace(full, sweep=0.0),
            vertex_map,
            IDENTITY_ROTATION,
            1.0,
            metric,
        )
        is None
    )
    assert (
        _curve_similarity(
            full,
            replace(full, vertices=(0, 1)),
            vertex_map,
            IDENTITY_ROTATION,
            1.0,
            metric,
        )
        is None
    )
    assert (
        _curve_similarity(
            line,
            replace(line, vertices=None),
            vertex_map,
            IDENTITY_ROTATION,
            1.0,
            metric,
        )
        is None
    )


def test_matching_face_parameter_and_wire_alignment_refusal_matrix() -> None:
    occurrence = correspondence_snapshot(_take_inventory(_rrp(5))).occurrences[0]
    graph = occurrence.matching_boundary
    metric = _order_bound(occurrence.body.quantization, occurrence.body.quantization, 1.0, 1)
    area = _order_bound(occurrence.body.quantization, occurrence.body.quantization, 1.0, 2)
    plane = next(face for face in graph.faces if face.kind == "PLANE" and face.wires)
    cylinder = next(face for face in graph.faces if face.kind == "CYLINDER" and face.wires)
    assert _face_similarity(plane, plane, IDENTITY_ROTATION, 1.0, metric, area)
    assert _face_similarity(cylinder, cylinder, IDENTITY_ROTATION, 1.0, metric, area)
    for source, changed in (
        (plane, replace(plane, parameters=(0.0, 1.0, 0.0, *plane.parameters[3:]))),
        (plane, replace(plane, parameters=(*plane.parameters[:3], plane.parameters[3] + 1.0))),
        (plane, replace(plane, material_side=-plane.material_side)),
        (
            cylinder,
            replace(
                cylinder,
                parameters=(*cylinder.parameters[:3], 999.0, 999.0, 999.0, cylinder.parameters[6]),
            ),
        ),
        (
            cylinder,
            replace(
                cylinder,
                parameters=(*cylinder.parameters[:6], cylinder.parameters[6] + 1000.0),
            ),
        ),
        (cylinder, replace(cylinder, material_side=-cylinder.material_side)),
        (plane, replace(plane, kind="SPHERE")),
    ):
        assert _face_similarity(source, changed, IDENTITY_ROTATION, 1.0, metric, area) is None

    def first_vertex(face):
        edge = next(item for wire in face.wires for item in wire.cycle if item.start is not None)
        assert edge.start is not None and edge.start.vertex is not None
        return graph.vertices[edge.start.vertex], edge.start.parameter

    vertex, parameter = first_vertex(plane)
    assert correspondence_match_module._parameter_matches(vertex, parameter, plane, metric)
    assert not correspondence_match_module._parameter_matches(
        vertex, (parameter[0] + 1.0, parameter[1] + 1.0), plane, metric
    )
    theta, z = first_vertex(cylinder)[1]
    axis = cylinder.parameters[:3]
    axis_point = cylinder.parameters[3:6]
    radius = cylinder.parameters[6]
    u, v = correspondence_match_module._plane_basis(axis)
    radial = tuple(
        radius * (math.cos(theta) * left + math.sin(theta) * right)
        for left, right in zip(u, v, strict=True)
    )
    cylinder_vertex = tuple(
        origin + radial_component + z * axis_component
        for origin, radial_component, axis_component in zip(axis_point, radial, axis, strict=True)
    )
    assert correspondence_match_module._parameter_matches(
        cylinder_vertex, (theta, z), cylinder, metric
    )
    assert not correspondence_match_module._parameter_matches(
        cylinder_vertex, (theta + 1.0, z + 1.0), cylinder, metric
    )

    vertex_map = tuple(range(len(graph.vertices)))
    curve_map = tuple(range(len(graph.curves)))
    curve_signs = tuple(1 for _curve in graph.curves)

    def align(source, target, source_face=plane, target_face=plane):
        return _wire_alignments(
            source,
            target,
            source_face,
            target_face,
            vertex_map,
            curve_map,
            curve_signs,
            graph.vertices,
            1,
            metric,
            _MatchBudget(),
        )

    wire = plane.wires[0]
    assert not align(wire, replace(wire, role="inner" if wire.role == "outer" else "outer"))
    assert not align(wire, replace(wire, cycle=wire.cycle[:-1]))
    first = wire.cycle[0]
    assert first.start is not None and first.end is not None
    assert not align(
        wire,
        replace(wire, cycle=(replace(first, start=None, end=None), *wire.cycle[1:])),
    )
    assert not align(
        wire,
        replace(
            wire,
            cycle=(
                replace(first, start=replace(first.start, vertex=None)),
                *wire.cycle[1:],
            ),
        ),
    )
    assert not align(
        wire,
        replace(
            wire,
            cycle=(
                replace(
                    first,
                    start=replace(first.start, vertex=(first.start.vertex or 0) + 1),
                ),
                *wire.cycle[1:],
            ),
        ),
    )
    assert not align(
        wire,
        replace(
            wire,
            cycle=(
                replace(
                    first,
                    start=replace(first.start, parameter=(999.0, 999.0)),
                ),
                *wire.cycle[1:],
            ),
        ),
    )

    endpoint_free_wire = replace(
        wire,
        cycle=(replace(first, start=None, end=None), *wire.cycle[1:]),
    )
    assert not align(
        endpoint_free_wire,
        replace(
            endpoint_free_wire,
            cycle=(first, *endpoint_free_wire.cycle[1:]),
        ),
    )


def test_degenerate_gauges_search_budget_and_schema_gate_refuse_closed_inputs(
    monkeypatch,
) -> None:
    with pytest.raises(CorrespondenceMatchError, match="axis is degenerate"):
        correspondence_match_module._canonical_axis((0.0, 0.0, 0.0))
    monkeypatch.setattr(correspondence_match_module, "DIRECTION_TOL", 2.0)
    with pytest.raises(CorrespondenceMatchError, match="basis is degenerate"):
        correspondence_match_module._plane_basis((1.0, 0.0, 0.0))

    budget = _MatchBudget()
    assert correspondence_match_module._enumerate_bijections(((0,), (0,)), budget) == ()
    assert budget.attempts
    assert correspondence_match_module._maximum_weight_matchings(
        (0, 1), (0,), {0: (0, 1), 1: (0,)}, {(0, 0): 1, (1, 0): 1}, _MatchBudget()
    )

    snapshot = correspondence_snapshot(_take_inventory(Box(10, 10, 10)))
    with pytest.raises(CorrespondenceMatchError, match="schema 3"):
        _compare_snapshots(replace(snapshot, schema_version=1), snapshot, _issuer_validated=True)


def test_matcher_dependency_and_policy_rosters_are_closed() -> None:
    from pathlib import Path

    path = Path(__file__).parents[1] / "src" / "b123d_recognisers" / "_correspondence_match.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        node.module: {alias.name for alias in node.names}
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        in {
            "b123d_recognisers._body_geometry",
            "b123d_recognisers._correspondence",
        }
    }
    assert set(imports) == {
        "b123d_recognisers._body_geometry",
        "b123d_recognisers._correspondence",
    }
    assert imports["b123d_recognisers._body_geometry"] == {
        "ANGLE_TOL",
        "DESCRIPTOR_REL",
        "DIRECTION_TOL",
        "DescriptorQuantization",
        "FaceGeometry",
        "MatchingBoundaryGraph",
        "MatchingCurve",
        "MatchingFace",
        "MatchingWire",
    }
    assert imports["b123d_recognisers._correspondence"] == {
        "AcceptedOccurrenceSnapshot",
        "CorrespondenceSnapshot",
        "CorrespondenceSnapshotError",
        "_InventoryProduct",
        "_validate_snapshot",
        "correspondence_snapshot",
    }
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert (
        not {
            "Candidate",
            "EvidenceIndex",
            "FaceGraph",
            "SolidRef",
            "RecognitionResult",
            "ClaimLedger",
            "hash",
            "digest",
        }
        & names
    )
    trusted_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_compare_snapshots"
        and any(
            keyword.arg == "_issuer_validated"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in node.keywords
        )
    ]
    assert len(trusted_calls) == 1
    owner = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and trusted_calls[0] in tuple(ast.walk(node))
    )
    assert owner.name == "correspondence_changes"
    assert "correspondence_changes" not in __import__("b123d_recognisers").__all__
