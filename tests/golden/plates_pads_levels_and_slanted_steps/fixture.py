from build123d import Box, Pos

from tests.golden._common import PROVENANCE as _PROVENANCE

PROVENANCE = dict(_PROVENANCE)


def build_fixture():
    base = Box(120, 70, 8)
    wall = Pos(-50, 0, 20) * Box(10, 70, 32)
    lower_step = Pos(10, 0, 8) * Box(45, 50, 8)
    raised_pad = Pos(30, 0, 20) * Box(24, 18, 16)
    return base + wall + lower_step + raised_pad
