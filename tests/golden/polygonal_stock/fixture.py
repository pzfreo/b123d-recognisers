from build123d import Rot

from tests.golden._common import PROVENANCE as _PROVENANCE
from tests.golden._common import hex_prism

PROVENANCE = dict(_PROVENANCE)


def build_fixture():
    return Rot(0, 0, 17) * hex_prism()
