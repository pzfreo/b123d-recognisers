from build123d import Box, Pos

from tests.golden._common import PROVENANCE as _PROVENANCE
from tests.golden._common import hex_prism

PROVENANCE = dict(_PROVENANCE)


def build_fixture():
    return Box(100, 80, 10) + Pos(0, 0, 5) * hex_prism()
