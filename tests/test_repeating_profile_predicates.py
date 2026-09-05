# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""The pure predicates behind repeating-radial-profile recognition.

Epic 0001 finding 4. I twice reported this module's uncovered lines as reachable only with
geometry built to fail, and that was wrong for a plainer reason than in ``polygonal_bosses``:
this module was already decomposed. ``_one_closed_cycle``, ``_cyclic_edge_orbits`` and
``_polar_signature`` are functions of edge endpoints and sampled points, so their rejection
paths are arithmetic. I had read the coverage percentage without reading the shape of the code
behind it.

The recogniser proves that an outer wire maps onto itself under a rotation, which is a strong
claim — it is the difference between "this looks like a gear" and "every edge participates in a
bijective sector rotation". These are the checks that make the claim safe to publish.
"""

from __future__ import annotations

from math import cos, pi, sin
from types import SimpleNamespace

import pytest
from build123d import GeomType

import quiddity.repeating_profiles as module
from quiddity.repeating_profiles import (
    _BoundaryEvidence,
    _common_circle_centre,
    _CurveEvidence,
    _curves_match,
    _cyclic_edge_orbits,
    _one_closed_cycle,
    _polar_signature,
    _profiles_correspond,
    _sector_signature,
)

TOL = 1e-6


def _segment(start, end, *, kind="LINE"):
    return _CurveEvidence(kind=kind, length=1.0, points=(start, end))


def _closed_polygon(count: int, radius: float = 10.0):
    corners = [
        (radius * cos(2 * pi * i / count), radius * sin(2 * pi * i / count)) for i in range(count)
    ]
    return tuple(_segment(corners[i], corners[(i + 1) % count]) for i in range(count))


def test_common_circle_centre_requires_two_and_has_inclusive_tolerance():
    def edge(x):
        return SimpleNamespace(
            geom_type=GeomType.CIRCLE,
            arc_center=SimpleNamespace(X=x, Y=0.0),
        )

    def wire(*edges):
        return SimpleNamespace(edges=lambda: list(edges))

    assert _common_circle_centre(wire(edge(0.0)), ("x", "y"), tol=TOL) is None
    assert _common_circle_centre(
        wire(edge(0.0), edge(2 * TOL)), ("x", "y"), tol=TOL
    ) == pytest.approx((TOL, 0.0))
    assert _common_circle_centre(wire(edge(0.0), edge(2.01 * TOL)), ("x", "y"), tol=TOL) is None
    malformed = SimpleNamespace(geom_type=GeomType.CIRCLE)
    assert _common_circle_centre(wire(edge(0.0), malformed), ("x", "y"), tol=TOL) is None


def test_wire_sampling_kernel_failure_returns_no_evidence():
    broken = SimpleNamespace(
        position_at=lambda _fraction: (_ for _ in ()).throw(RuntimeError("sampling failed")),
        geom_type=GeomType.LINE,
        length=1.0,
    )
    assert module._sample_wire(SimpleNamespace(edges=lambda: [broken]), ("x", "y")) is None


class TestOneClosedCycle:
    def test_a_closed_polygon_is_one_cycle(self):
        assert _one_closed_cycle(_closed_polygon(6), tol=TOL)

    def test_the_answer_does_not_depend_on_edge_order(self):
        """Traversal order is an OCCT artefact, so it must not decide the topology."""

        edges = _closed_polygon(6)
        shuffled = (edges[3], edges[0], edges[5], edges[1], edges[4], edges[2])

        assert _one_closed_cycle(shuffled, tol=TOL)

    def test_no_edges_is_not_a_cycle(self):
        assert not _one_closed_cycle((), tol=TOL)

    def test_an_open_chain_is_not_a_cycle(self):
        """Two endpoints of degree one — a profile that does not close cannot repeat."""

        assert not _one_closed_cycle(_closed_polygon(6)[:-1], tol=TOL)

    def test_a_degenerate_edge_returning_to_its_own_start_is_rejected(self):
        assert not _one_closed_cycle((_segment((0.0, 0.0), (0.0, 0.0)),), tol=TOL)

    def test_two_separate_rings_are_not_one_cycle(self):
        """Every endpoint has degree two here, so connectivity is the only thing that rejects it.

        Without the reachability walk this pair of triangles would pass as a single profile and
        a two-lobed shape would be reported with the wrong repeat count.
        """

        near = _closed_polygon(3, radius=5.0)
        far = tuple(
            _segment(
                (edge.points[0][0] + 100.0, edge.points[0][1]),
                (edge.points[-1][0] + 100.0, edge.points[-1][1]),
            )
            for edge in near
        )

        assert _one_closed_cycle(near + far, tol=TOL) is False

    def test_a_vertex_where_three_edges_meet_is_not_a_simple_profile(self):
        """A spur off the outline gives one node degree three, so the wire is not a clean loop."""

        edges = _closed_polygon(4)
        spur = _segment(edges[0].points[0], (0.0, 50.0))

        assert not _one_closed_cycle((*edges, spur), tol=TOL)

    def test_endpoint_node_tolerance_is_inclusive_then_refuses(self):
        edges = list(_closed_polygon(5))
        start = edges[0].points[0]
        end = edges[-1].points[-1]
        assert start == pytest.approx(end)
        edges[-1] = _segment(edges[-1].points[0], (end[0] + TOL, end[1]))
        assert _one_closed_cycle(tuple(edges), tol=TOL)
        edges[-1] = _segment(edges[-1].points[0], (end[0] + 1.01 * TOL, end[1]))
        assert not _one_closed_cycle(tuple(edges), tol=TOL)

    def test_one_endpoint_cannot_match_two_existing_nodes(self):
        edges = (
            _segment((0.0, 0.0), (2 * TOL, 0.0)),
            _segment((TOL, 0.0), (10.0, 0.0)),
        )
        assert not _one_closed_cycle(edges, tol=TOL)


class TestPolarSignature:
    def test_a_curve_and_its_reverse_share_a_signature(self):
        """Traversal direction is not a property of the shape."""

        points = ((10.0, 0.0), (9.0, 3.0), (8.0, 5.0))

        assert _polar_signature(points, (0.0, 0.0)) == _polar_signature(
            tuple(reversed(points)), (0.0, 0.0)
        )

    def test_rotating_a_curve_about_the_centre_does_not_change_its_signature(self):
        """Phase is removed, which is what lets one sector be compared with the next."""

        def turned(angle):
            return tuple(
                (r * cos(t + angle), r * sin(t + angle))
                for r, t in ((10.0, 0.0), (9.0, 0.3), (8.0, 0.55))
            )

        assert _polar_signature(turned(0.0), (0.0, 0.0)) == _polar_signature(
            turned(2 * pi / 7), (0.0, 0.0)
        )

    def test_a_mirrored_curve_shares_the_signature_of_its_original(self):
        points = ((10.0, 0.0), (9.0, 3.0), (8.0, 5.0))
        mirrored = tuple((x, -y) for x, y in points)

        assert _polar_signature(points, (0.0, 0.0)) == _polar_signature(mirrored, (0.0, 0.0))

    def test_a_genuinely_different_profile_has_a_different_signature(self):
        """The canonicalisation must not be so aggressive that unlike shapes collide."""

        tooth = ((10.0, 0.0), (9.0, 3.0), (8.0, 5.0))
        deeper = ((10.0, 0.0), (6.0, 3.0), (8.0, 5.0))

        assert _polar_signature(tooth, (0.0, 0.0)) != _polar_signature(deeper, (0.0, 0.0))


class TestOrbitBoundaries:
    def test_count_divisibility_and_complete_orbit_boundaries(self):
        edges = _closed_polygon(10)
        assert _cyclic_edge_orbits(edges, centre=(0.0, 0.0), repeat_count=5, tol=TOL)
        assert _cyclic_edge_orbits(edges[:5], centre=(0.0, 0.0), repeat_count=5, tol=TOL) is None
        assert _cyclic_edge_orbits(edges[:-1], centre=(0.0, 0.0), repeat_count=5, tol=TOL) is None
        # A divisor with cycles shorter than the declared count is not a complete orbit.
        assert _cyclic_edge_orbits(edges, centre=(0.0, 0.0), repeat_count=10, tol=TOL) is None

    def test_unique_match_and_bijection_are_required(self):
        edges = list(_closed_polygon(10))
        edges[1] = edges[0]
        assert _cyclic_edge_orbits(tuple(edges), centre=(0.0, 0.0), repeat_count=5, tol=TOL) is None

    def test_nonbijective_mapping_and_short_orbits_are_refused(self, monkeypatch):
        edges = _closed_polygon(10)
        indexes = {id(edge): index for index, edge in enumerate(edges)}

        def duplicate_target(source, target, **_kwargs):
            source_index = indexes[id(source)]
            target_index = indexes[id(target)]
            wanted = 0 if source_index in (0, 1) else source_index
            return target_index == wanted

        monkeypatch.setattr(module, "_curves_match", duplicate_target)
        assert _cyclic_edge_orbits(edges, centre=(0.0, 0.0), repeat_count=5, tol=TOL) is None

        monkeypatch.setattr(
            module, "_curves_match", lambda source, target, **_kwargs: source is target
        )
        assert _cyclic_edge_orbits(edges, centre=(0.0, 0.0), repeat_count=5, tol=TOL) is None

    def test_curve_kind_length_and_metric_equality_are_exact(self):
        source = _segment((10.0, 0.0), (8.0, 2.0))
        angle = 2 * pi / 5

        def rotate(point):
            return (
                point[0] * cos(angle) - point[1] * sin(angle),
                point[0] * sin(angle) + point[1] * cos(angle),
            )

        target = _CurveEvidence("LINE", 1.0 + TOL, tuple(rotate(p) for p in source.points))
        assert _curves_match(source, target, angle=angle, centre=(0.0, 0.0), tol=TOL)
        assert not _curves_match(
            source,
            _CurveEvidence("LINE", 1.0 + 1.01 * TOL, target.points),
            angle=angle,
            centre=(0.0, 0.0),
            tol=TOL,
        )
        point_tol = 0.5
        shifted_points = tuple((x + point_tol, y) for x, y in target.points)
        assert _curves_match(
            source,
            _CurveEvidence("LINE", 1.0, shifted_points),
            angle=angle,
            centre=(0.0, 0.0),
            tol=point_tol,
        )
        beyond = tuple((x + 1.01 * point_tol, y) for x, y in target.points)
        assert not _curves_match(
            source,
            _CurveEvidence("LINE", 1.0, beyond),
            angle=angle,
            centre=(0.0, 0.0),
            tol=point_tol,
        )
        assert not _curves_match(
            source,
            _CurveEvidence("CIRCLE", 1.0, target.points),
            angle=angle,
            centre=(0.0, 0.0),
            tol=TOL,
        )


def _boundary(*, axis="z", at=0.0, centre=(0.0, 0.0), repeats=5, edge=None):
    curve = _segment((10.0, 0.0), (8.0, 2.0)) if edge is None else edge
    return _BoundaryEvidence(
        face=object(),
        axis=axis,
        at=at,
        plane_axes=("x", "y"),
        centre=centre,
        repeat_count=repeats,
        edges=(curve,),
        orbits=((0,),),
    )


class TestBilateralCorrespondence:
    def test_centre_tolerance_equality_and_each_mismatch(self):
        lower = _boundary()
        shifted = _CurveEvidence(
            "LINE",
            1.0,
            tuple((x + TOL, y) for x, y in lower.edges[0].points),
        )
        assert _profiles_correspond(
            lower,
            _boundary(at=10, centre=(TOL, 0.0), edge=shifted),
            tol=TOL,
        )
        assert not _profiles_correspond(lower, _boundary(axis="x"), tol=TOL)
        assert not _profiles_correspond(lower, _boundary(centre=(1.01 * TOL, 0.0)), tol=TOL)
        assert not _profiles_correspond(lower, _boundary(repeats=6), tol=TOL)
        assert not _profiles_correspond(
            lower,
            _BoundaryEvidence(
                object(),
                "z",
                10,
                ("x", "y"),
                (0.0, 0.0),
                5,
                (lower.edges[0], lower.edges[0]),
                ((0,),),
            ),
            tol=TOL,
        )
        changed = _CurveEvidence("LINE", 2.0, lower.edges[0].points)
        assert _sector_signature(lower) != _sector_signature(_boundary(edge=changed))
        assert not _profiles_correspond(lower, _boundary(edge=changed), tol=TOL)

    def test_signature_rounding_is_exact_at_six_decimals(self):
        lower = _boundary()
        within = _CurveEvidence("LINE", 1.0 + 0.4e-6, lower.edges[0].points)
        beyond = _CurveEvidence("LINE", 1.0 + 0.6e-6, lower.edges[0].points)
        assert _sector_signature(lower) == _sector_signature(_boundary(edge=within))
        assert _sector_signature(lower) != _sector_signature(_boundary(edge=beyond))
