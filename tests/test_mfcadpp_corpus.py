# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""Per-face recogniser accuracy on independently authored, labelled geometry.

Every other test in this project runs on solids this project wrote. That is fine for pinning
behaviour and useless for finding out that the behaviour is wrong: a fixture built to
exercise a recogniser tends to agree with it. MFCAD++ was built by someone else, for a
different purpose, and labels *every B-Rep face* with the machining feature it belongs to —
so a record can be matched back to the face that produced it and simply checked.

That is what found the defect these tests now guard. `recognise_chamfers` was reporting the
slanted walls of steps and passages as chamfers at 44% precision, and no synthetic fixture
had noticed, because none of them contained a step whose wall looked like a chamfer.

**Attribution is by face centre**, which works because `Chamfer.at` and `AngledStep.at` are
both the recognised face's centroid rounded to three places. It is not available for families
whose records do not anchor on a face, which is why this module covers only these two.

The vendored subset and the rule that selected it are in ``corpus/mfcadpp/MANIFEST.json``.
Forty models, chosen to cover the two families plus the three classes that were being
mistaken for chamfers, from the *test* split only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from build123d import import_step

from b123d_recognisers import recognise_angled_steps, recognise_chamfers

CORPUS = Path(__file__).parent / "corpus" / "mfcadpp"
#: MFCAD++ stores its per-face label as the name of each ``ADVANCED_FACE`` entity, in the
#: same order the kernel yields faces. ``test_the_label_to_face_mapping_holds`` is what makes
#: relying on that legitimate rather than hopeful.
_LABEL = re.compile(rb"ADVANCED_FACE\('(\d+)'")
CHAMFER, TRIANGULAR_BLIND_STEP = 0, 20


@pytest.fixture(scope="module")
def corpus():
    """Each model paired with a face-centre to label map. Loaded once; import_step is slow."""

    models = []
    for path in sorted(CORPUS.glob("*.step")):
        labels = [int(value) for value in _LABEL.findall(path.read_bytes())]
        part = import_step(str(path))
        faces = list(part.faces())
        at_label = {}
        # strict=False deliberately: a length mismatch means the vendored corpus is wrong, and
        # `test_the_label_to_face_mapping_holds` is what should report that, with the model
        # name and both counts. Raising here would break every test in the module at fixture
        # setup instead, and say less.
        for face, label in zip(faces, labels, strict=False):
            centre = face.center()
            at_label[(round(centre.X, 3), round(centre.Y, 3), round(centre.Z, 3))] = label
        models.append((path.name, part, labels, faces, at_label))
    assert models, "the vendored MFCAD++ subset is missing"
    return models


def test_the_selection_manifest_describes_what_is_actually_vendored():
    """The recorded rule and the files on disk agree, so the subset can be re-derived.

    A vendored corpus with no reproducible provenance is indistinguishable from an arbitrary
    pile of files that happened to pass. This is what makes it re-derivable.
    """

    manifest = json.loads((CORPUS / "MANIFEST.json").read_text(encoding="utf-8"))
    on_disk = sorted(path.name for path in CORPUS.glob("*.step"))

    assert manifest["models"] == on_disk
    assert manifest["licence"] == "CC BY 4.0"
    assert manifest["rule"]["split"] == "test", "train/val models must never be vendored here"
    for models in manifest["by_label"].values():
        assert set(models) <= set(on_disk)


def test_the_label_to_face_mapping_holds(corpus):
    """Every claim in this module rests on this one, so it is asserted rather than assumed.

    If ``ADVANCED_FACE`` order stopped matching ``part.faces()`` order, every test below would
    keep passing or failing for reasons unrelated to recognition. Checked two ways: the counts
    match, and label-0 faces are overwhelmingly oblique planes while other faces are not —
    which is a property of chamfers specifically, so it cannot hold by coincidence.
    """

    oblique = {True: [0, 0], False: [0, 0]}
    for name, _part, labels, faces, _at in corpus:
        assert len(faces) == len(labels), f"{name}: {len(faces)} faces, {len(labels)} labels"
        for face, label in zip(faces, labels, strict=True):
            try:
                normal = face.normal_at()
            except Exception:  # noqa: BLE001 - a degenerate face has no normal to read
                continue
            is_oblique = max(abs(normal.X), abs(normal.Y), abs(normal.Z)) < 0.99
            oblique[label == CHAMFER][is_oblique] += 1

    chamfer_oblique = oblique[True][1] / sum(oblique[True])
    other_oblique = oblique[False][1] / sum(oblique[False])
    assert chamfer_oblique > 0.75, "faces labelled Chamfer are not mostly oblique planes"
    assert other_oblique < 0.40, "oblique faces are not concentrated in the Chamfer label"


def test_every_angled_step_record_lands_on_a_labelled_triangular_blind_step(corpus):
    """100% precision, checked per face rather than fitted from counts.

    The discriminator is topological — a chamfer runs the full length of its edge, an angled
    step stops and a triangular flat closes it — so this is the test that fails if it is ever
    replaced by something tuned to a corpus.
    """

    wrong = []
    found = 0
    for name, part, _labels, _faces, at_label in corpus:
        for record in recognise_angled_steps(part):
            found += 1
            if at_label.get(record.at) != TRIANGULAR_BLIND_STEP:
                wrong.append((name, record.at, at_label.get(record.at)))

    assert found, "no angled steps recognised at all; the subset or the recogniser has moved"
    assert wrong == [], f"records on faces MFCAD++ does not label a blind step: {wrong}"


def test_no_chamfer_record_lands_on_a_labelled_angled_step(corpus):
    """The direct regression guard for the defect that motivated the family.

    Before `recognise_angled_steps` existed this failed on every model carrying one: on nine
    of ten such models the step's slant was the *only* chamfer reported, while the real
    chamfers on the same part were rejected. Removing the triangular-companion decline from
    `recognise_chamfers` reintroduces exactly that, and this is what says so.
    """

    stolen = [
        (name, record.at)
        for name, part, _labels, _faces, at_label in corpus
        for record in recognise_chamfers(part)
        if at_label.get(record.at) == TRIANGULAR_BLIND_STEP
    ]

    assert stolen == [], f"chamfer records on faces labelled a blind step: {stolen}"


def test_chamfer_precision_does_not_regress(corpus):
    """A floor, not a target: this subset is deliberately stocked with confusable classes.

    Twelve models were selected for each of triangular pocket, 2-sided through step and
    6-sided passage precisely because their walls are oblique planes that a chamfer
    recogniser can mistake, so precision here is a harder number than on a random sample —
    79% against 78% over 120 unselected models. It was 44% before the angled-step family.
    """

    records = correct = 0
    for _name, part, _labels, _faces, at_label in corpus:
        for record in recognise_chamfers(part):
            records += 1
            correct += at_label.get(record.at) == CHAMFER

    assert records, "no chamfers recognised at all"
    assert correct / records >= 0.70, (
        f"chamfer precision fell to {100 * correct / records:.0f}% "
        f"({correct}/{records}); it was 79% when this subset was vendored and 44% before "
        "recognise_angled_steps existed"
    )
