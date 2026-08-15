from build123d import Rot

from tests.golden._common import hex_prism, provenance

PROVENANCE = provenance("tests/test_issue_1082_polygonal_stock.py")


def build_fixture():
    return Rot(0, 0, 17) * hex_prism()
