# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Shared public body-correlation key boundaries."""

from pathlib import Path

from build123d import Axis, Cylinder, GeomType, Pos, export_step, fillet, import_step

from b123d_recognisers._body_identity import unambiguous_body_keys


def test_oblique_curved_body_key_is_stable_across_step(tmp_path: Path) -> None:
    shaft = Pos(0, 0, 20) * Cylinder(15, 40) + Pos(0, 0, 55) * Cylinder(8, 30)
    curved = fillet([edge for edge in shaft.edges() if edge.geom_type == GeomType.CIRCLE], 0.2)
    source = curved.rotate(Axis.Y, 23)
    path = tmp_path / "oblique-curved.step"
    assert export_step(source, path)

    assert unambiguous_body_keys([import_step(path)], require_valid_solid=True) == (
        unambiguous_body_keys([source], require_valid_solid=True)[0],
    )
