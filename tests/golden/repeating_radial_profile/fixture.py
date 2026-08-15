from tests.golden._common import PROVENANCE as _PROVENANCE
from tests.golden._common import toothed_prism

PROVENANCE = dict(_PROVENANCE)


def build_fixture():
    return toothed_prism()
