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

from b123d_recognisers.repeating_profiles import (
    _CurveEvidence,
    _one_closed_cycle,
    _polar_signature,
)

TOL = 1e-6


def _segment(start, end, *, kind="LINE"):
    return _CurveEvidence(kind=kind, length=1.0, points=(start, end))


def _closed_polygon(count: int, radius: float = 10.0):
    corners = [
        (radius * cos(2 * pi * i / count), radius * sin(2 * pi * i / count)) for i in range(count)
    ]
    return tuple(_segment(corners[i], corners[(i + 1) % count]) for i in range(count))


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
