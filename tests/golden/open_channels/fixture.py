from build123d import Box, Pos

from tests.golden._common import PROVENANCE as _PROVENANCE

PROVENANCE = dict(_PROVENANCE)


def build_fixture():
    return (
        Box(60, 50, 10)
        + Pos(0, -20, 13) * Box(60, 10, 16)
        + Pos(0, 20, 13) * Box(60, 10, 16)
    )
