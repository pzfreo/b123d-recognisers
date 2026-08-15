# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

from b123d_recognisers import __version__


def test_version_is_available() -> None:
    assert __version__
