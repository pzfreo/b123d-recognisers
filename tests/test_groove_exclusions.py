# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""What ``recognise_grooves`` refuses, and why.

Epic 0001 finding 4 asked for negative and boundary coverage where the geometry is hardest, and
``docs/capabilities.md`` already lists the excluded classes: internal grooves, end reliefs without
two larger neighbours, and non-turned recesses. The positive case is covered by the turned golden;
every branch exercised below is a ``continue`` that the golden never reaches.

Each test is a shape a looser recogniser would call a groove. The point of the module's gates is
that a reduced band is not sufficient evidence — a groove is a narrow channel cut into *uniform*
stock, and each gate removes one way of failing that.
"""

from __future__ import annotations

from build123d import Cone, Cylinder, Pos

from b123d_recognisers import recognise_grooves


def _shaft_with_reduced_band(*, wall_r=15.0, band_r=12.0, lo_h=20.0, band_h=5.0, hi_h=20.0):
    """A shaft of three coaxial bands: wall, reduced band, wall."""

    shaft = Cylinder(wall_r, lo_h)
    shaft += Pos(0, 0, (lo_h + band_h) / 2) * Cylinder(band_r, band_h)
    shaft += Pos(0, 0, (lo_h + band_h) / 2 + (band_h + hi_h) / 2) * Cylinder(wall_r, hi_h)
    return shaft


def test_a_narrow_band_between_two_equal_walls_is_a_groove():
    """The positive control. Without it the exclusions below prove nothing."""

    (groove,) = recognise_grooves(_shaft_with_reduced_band())

    assert groove.diameter == 24.0
    assert groove.width == 5.0


def test_a_monotonic_step_down_is_a_shoulder_not_a_groove():
    """A groove is a strict local OD *minimum* — the OD must step down into it and up out.

    A descending staircase satisfies one side only. Calling it a groove would report a shoulder
    as an annular channel and dimension it as a recess that is not there.
    """

    shaft = Cylinder(15, 20)
    shaft += Pos(0, 0, 12.5) * Cylinder(12, 5)
    shaft += Pos(0, 0, 22.5) * Cylinder(9, 15)

    assert recognise_grooves(shaft) == []


def test_a_band_between_walls_of_different_diameters_is_a_stepped_profile():
    """Cut into uniform stock means the two walls return to the *same* OD.

    Unequal neighbours are a stepped shaft that happens to dip, not round bar with a channel in
    it, and its ``diameter`` would not describe a real ring groove.
    """

    shaft = Cylinder(15, 20)
    shaft += Pos(0, 0, 12.5) * Cylinder(12, 5)
    shaft += Pos(0, 0, 22.5) * Cylinder(14, 15)

    assert recognise_grooves(shaft) == []


def test_a_band_as_wide_as_its_walls_is_a_staircase_step():
    """A groove is *narrow* relative to the stock it interrupts.

    Without this gate an alternating fine-step profile reports every reduced segment as a
    groove, which is how a turned staircase becomes a row of phantom channels.
    """

    shaft = _shaft_with_reduced_band(lo_h=6.0, band_h=20.0, hi_h=6.0)

    assert recognise_grooves(shaft) == []


def test_a_reduced_band_at_the_end_of_the_shaft_is_a_relief_not_a_groove():
    """An end relief has one wall, not two. It is an excluded class in `docs/capabilities.md`."""

    shaft = Cylinder(15, 30)
    shaft += Pos(0, 0, 17.5) * Cylinder(12, 5)

    assert recognise_grooves(shaft) == []


def test_bands_separated_by_a_gap_are_not_one_another_s_walls():
    """Contiguity is evidence: a band floating clear of its neighbours is a separate feature.

    Two coaxial discs with air between them are not a grooved shaft, and pairing them would
    measure a channel across a void.
    """

    shaft = Cylinder(15, 20)
    shaft += Pos(0, 0, 20) * Cylinder(12, 5)
    shaft += Pos(0, 0, 40) * Cylinder(15, 20)

    assert recognise_grooves(shaft) == []


def test_a_band_wider_than_the_wall_before_it_is_not_a_local_minimum():
    """The OD must step *down* into the band. Here it steps up, then down.

    The mirror of the monotonic-step case: a groove needs both sides to fail an ascent, and this
    profile fails only the second. Covered separately because the two gates are separate reads
    of the neighbour, and a copy-paste slip between them would leave one direction unchecked.
    """

    shaft = Cylinder(6, 20)
    shaft += Pos(0, 0, 12.5) * Cylinder(7.5, 5)
    shaft += Pos(0, 0, 22.5) * Cylinder(4.5, 15)

    assert recognise_grooves(shaft) == []


def test_a_chamfered_groove_is_outside_the_proven_scope():
    """Conical transitions break the band contiguity the recogniser requires.

    This is a real shape — a ring groove with lead-in chamfers — and it is **not** recognised,
    because the cone faces sit between the cylindrical bands so the walls are no longer the
    band's immediate neighbours. Recorded as a test rather than left implicit: it is a false
    negative, not a nonsense input, and anyone widening the recogniser should have to change
    this expectation deliberately.
    """

    shaft = Cylinder(15, 20)
    shaft += Pos(0, 0, 11.5) * Cone(15, 12, 3)
    shaft += Pos(0, 0, 15.5) * Cylinder(12, 5)
    shaft += Pos(0, 0, 19.5) * Cone(12, 15, 3)
    shaft += Pos(0, 0, 31.0) * Cylinder(15, 20)

    assert recognise_grooves(shaft) == []


def test_a_plain_cylinder_has_no_groove():
    assert recognise_grooves(Cylinder(15, 40)) == []
