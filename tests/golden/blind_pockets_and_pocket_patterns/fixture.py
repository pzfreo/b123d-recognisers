from build123d import Box, Pos

from tests.golden._common import PROVENANCE as _PROVENANCE

PROVENANCE = dict(_PROVENANCE)


def build_fixture():
    part = Box(120, 100, 20)
    for x in (-25, 25):
        for y in (-25, 0, 25):
            part -= Pos(x, y, 7) * Box(12, 10, 6)
    return part
