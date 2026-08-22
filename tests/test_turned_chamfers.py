# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""Turned chamfers are conical rather than planar faces."""

import pytest
from build123d import Axis, Box, Cone, Cylinder, GeomType, Pos, Sphere, Torus, fillet

from b123d_recognisers import build_recognition_result, recognise_chamfers, recognise_fillets
from b123d_recognisers._geometry import _coaxial_axis_lines


def _chamfered_stepped_shaft():
    """Two turned diameters, with each free end and shoulder edge chamfered."""

    shaft = Pos(0, 0, 20) * Cylinder(15, 40) + Pos(0, 0, 55) * Cylinder(8, 30)
    circular_edges = [edge for edge in shaft.edges() if edge.geom_type == GeomType.CIRCLE]
    return shaft.chamfer(0.8, None, circular_edges)


def _filleted_stepped_shaft():
    shaft = Pos(0, 0, 20) * Cylinder(15, 40) + Pos(0, 0, 55) * Cylinder(8, 30)
    circular_edges = [edge for edge in shaft.edges() if edge.geom_type == GeomType.CIRCLE]
    return fillet(circular_edges, 0.8)


def test_direct_reader_recognises_conical_turned_chamfers():
    found = recognise_chamfers(_chamfered_stepped_shaft())

    assert len(found) == 4
    assert {(chamfer.axis, chamfer.leg1, chamfer.leg2, chamfer.angle) for chamfer in found} == {
        ("z", 0.8, 0.8, 45.0)
    }


def test_rotational_inventory_keeps_turned_chamfers():
    result = build_recognition_result(_chamfered_stepped_shaft(), rotational=True)

    assert len(result.chamfers) == 4
    assert all(chamfer.axis == "z" for chamfer in result.chamfers)


def test_rotational_inventory_keeps_toroidal_turned_fillets():
    result = build_recognition_result(_filleted_stepped_shaft(), rotational=True)

    assert len(recognise_fillets(_filleted_stepped_shaft())) == 4
    assert len(result.fillets) == 4
    assert {(fillet.axis, fillet.radius) for fillet in result.fillets} == {("z", 0.8)}


def test_internal_countersink_is_not_a_turned_chamfer():
    part = Box(60, 60, 20) - Cylinder(3, 20) - Pos(0, 0, 7) * Cone(3, 7, 6)

    assert recognise_chamfers(part) == []


def test_internal_toroidal_bore_round_is_not_a_turned_fillet():
    bored = Box(60, 60, 20) - Cylinder(5, 20)
    inner_rim = bored.edges().filter_by(GeomType.CIRCLE)[0]

    assert recognise_fillets(fillet(inner_rim, 1.0)) == []


def test_toroidal_bead_is_not_a_turned_fillet():
    bead = Cylinder(10, 20) + Torus(10, 2)

    assert recognise_fillets(bead) == []


def test_a_full_torus_is_not_a_turned_fillet():
    assert recognise_fillets(Torus(10, 2)) == []


def test_non_principal_turned_surfaces_are_out_of_scope():
    slanted_cone = Cone(10, 8, 2).rotate(Axis.X, 45)
    slanted_bead = (Cylinder(10, 20) + Torus(10, 2)).rotate(Axis.X, 45)

    assert recognise_chamfers(slanted_cone) == []
    assert recognise_fillets(slanted_bead) == []


def test_a_taper_into_a_rounded_nose_is_not_a_turned_chamfer():
    shaft_and_taper = Cylinder(10, 20).fuse(Pos(0, 0, 13) * Cone(10, 8, 6))
    rounded_nose = shaft_and_taper.fuse(Pos(0, 0, 16) * Sphere(8))

    assert recognise_chamfers(rounded_nose) == []


def test_coaxial_line_evidence_requires_three_component_directions():
    with pytest.raises(ValueError, match="directions must be 3-vectors"):
        _coaxial_axis_lines((0, 0, 0), (0, 1), (0, 0, 0), (0, 0, 1), tol=0.01)
