from build123d import Align, Box, Cylinder

from tests.golden._common import PROVENANCE as _PROVENANCE

PROVENANCE = dict(_PROVENANCE)

_CENTER = (Align.CENTER, Align.CENTER, Align.CENTER)


def build_fixture():
    cutter = Cylinder(5, 20, align=_CENTER) & Box(7.2, 20, 30, align=_CENTER)
    return Box(30, 30, 10, align=_CENTER) - cutter
