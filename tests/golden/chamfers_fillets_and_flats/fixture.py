from build123d import Axis, Box, Compound, Cylinder, Pos, chamfer, fillet

from tests.golden._common import PROVENANCE as _PROVENANCE

PROVENANCE = dict(_PROVENANCE)


def build_fixture():
    chamfered = Pos(-70, 0, 0) * chamfer(Box(40, 30, 20).edges().filter_by(Axis.Z), 3)
    filleted = fillet(Box(40, 30, 20).edges().filter_by(Axis.Z), 4)
    flat_shaft = Pos(70, 0, 0) * (Cylinder(15, 40) & Pos(0, -2, 0) * Box(40, 26, 40))
    return Compound(children=[chamfered, filleted, flat_shaft])
