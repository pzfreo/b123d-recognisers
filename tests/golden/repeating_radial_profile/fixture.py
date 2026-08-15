from tests.golden._common import provenance, toothed_prism

PROVENANCE = provenance("tests/test_issue_1058_wheel_profile.py")


def build_fixture():
    return toothed_prism()
