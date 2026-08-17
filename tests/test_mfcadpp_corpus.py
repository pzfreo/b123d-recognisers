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
#: The sdist ships this module but not the 4.8 MB of STEP it reads, so absence must skip. A
#: packager running the sdist's suite is in a legitimate situation, not a broken one.
pytestmark = pytest.mark.skipif(
    not (CORPUS / "MANIFEST.json").is_file(),
    reason="the vendored MFCAD++ subset is excluded from the sdist",
)
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
        # Attribution is by rounded centroid, so two faces sharing a key would silently
        # overwrite one label with another and quietly corrupt every result below. Measured
        # at zero collisions across all 40 models; pinned so it stays that way.
        assert len(at_label) == min(len(faces), len(labels)), (
            f"{path.name}: faces share a rounded centroid"
        )
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
    rule = manifest["rule"]

    assert manifest["models"] == on_disk
    assert manifest["licence"] == "CC BY"
    assert rule["split"] == "test", "train/val models must never be vendored here"
    # `source` is checked against `split` because otherwise the manifest can contradict
    # itself in the one field that matters: `source: "MFCAD++ train split"` passed while
    # `rule.split` still read "test".
    assert rule["split"] in manifest["source"].lower()
    assert rule["order"] == "filename, ascending"
    assert rule["precondition"] == "STEP ADVANCED_FACE count equals part.faces() count"
    assert rule["targets"] == {
        "0": "Chamfer",
        "4": "6-sided passage",
        "9": "2-sided through step",
        "13": "Triangular pocket",
        "20": "Triangular blind step",
    }
    assert manifest["doi"].startswith("https://doi.org/10.17034/")

    # An earlier version stopped at the filename list, which meant the recorded rule could say
    # anything at all -- `per_label: 999`, an empty `by_label`, even `split: train` reworded --
    # and still pass. What is checkable offline is checked: the per-label counts, the stated
    # ordering, that the labelled sets account for every vendored file, and that each model
    # really does carry the label it is listed under. What is not checkable offline is that
    # these are the *first* N by filename in the upstream split, which needs the 1.5 GB
    # original; the rule records it so a future maintainer can re-derive it.
    labelled = set()
    for label, models in manifest["by_label"].items():
        assert models == sorted(models), f"label {label} is not in the recorded order"
        assert len(models) == rule["per_label"], f"label {label} has {len(models)} models"
        assert set(models) <= set(on_disk)
        labelled |= set(models)
        for name in models:
            tags = {int(v) for v in _LABEL.findall((CORPUS / name).read_bytes())}
            assert int(label) in tags, f"{name} is listed under {label} but does not carry it"
    assert labelled == set(on_disk), "vendored files that no target label accounts for"


def test_the_label_to_face_mapping_holds(corpus):
    """Every claim in this module rests on this one, so it is asserted rather than assumed.

    If ``ADVANCED_FACE`` order stopped matching ``part.faces()`` order, every test below would
    keep passing or failing for reasons unrelated to recognition. Checked two ways: the counts
    match, and label-0 faces are overwhelmingly oblique planes while other faces are not —
    which is a property of chamfers specifically, so it cannot hold by coincidence.
    """

    oblique = {True: [0, 0], False: [0, 0]}
    triangular = {True: [0, 0], False: [0, 0]}
    for name, _part, labels, faces, _at in corpus:
        assert len(faces) == len(labels), f"{name}: {len(faces)} faces, {len(labels)} labels"
        for face, label in zip(faces, labels, strict=True):
            try:
                normal = face.normal_at()
            except Exception:  # noqa: BLE001 - a degenerate face has no normal to read
                continue
            is_oblique = max(abs(normal.X), abs(normal.Y), abs(normal.Z)) < 0.99
            oblique[label == CHAMFER][is_oblique] += 1
            triangular[label == TRIANGULAR_BLIND_STEP][len(face.edges()) == 3] += 1

    chamfer_oblique = oblique[True][1] / sum(oblique[True])

    # This one bites: a rotate-by-one mismatch drops it to 0.208, a shuffle to 0.125.
    assert chamfer_oblique > 0.75, "faces labelled Chamfer are not mostly oblique planes"

    # And this is the genuinely second check, on a different label and a different property.
    # Two previous attempts were not: `other_oblique < 0.40` cannot fail, since 30.9% of all
    # 1335 faces are oblique and only 24 carry label 0, so no relabelling can push the rest
    # past 0.315. Nor could `chamfer_oblique > 2 * other_oblique` -- bounded that way, twice
    # `other_oblique` never reaches 0.63, so the 0.75 line above already implies it. A
    # redundancy replacing a tautology. Blind spot both shared: swapping labels 0 and 4
    # wholesale left the whole test green.
    tri_step = triangular[True][1] / sum(triangular[True])
    tri_rest = triangular[False][1] / sum(triangular[False])
    assert tri_step > 4 * tri_rest, (
        f"the Triangular blind step label does not concentrate three-edged faces: "
        f"{tri_step:.3f} against {tri_rest:.3f} elsewhere"
    )


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

    stolen, resolved = [], 0
    for name, part, _labels, _faces, at_label in corpus:
        for record in recognise_chamfers(part):
            label = at_label.get(record.at)
            resolved += label is not None
            if label == TRIANGULAR_BLIND_STEP:
                stolen.append((name, record.at))

    # Without this the test passes when attribution stops resolving entirely: replacing the
    # lookup key with one that can never match left it green, which would make "the direct
    # regression guard" a silent no-op. All 14 chamfer records resolve today.
    assert resolved, "no chamfer record resolved to a labelled face; attribution is broken"
    assert stolen == [], f"chamfer records on faces labelled a blind step: {stolen}"


#: Record counts as of vendoring, over the 40 models. **Not a correctness baseline** -- a
#: change detector, exactly as ``_OBSERVED`` is on the NIST side. Without it this module was
#: blind to volume: truncating `recognise_angled_steps` to one record for the entire run, a
#: 91% silent loss, left all five tests green, because every other assertion here is either a
#: >= 1 gate or a ratio.
_OBSERVED_RECORDS = {"angled_steps": 11, "chamfers": 14}


def test_the_number_of_records_has_not_moved(corpus):
    """Volume, which precision and the >=1 gates are both blind to by construction."""

    counts = {"angled_steps": 0, "chamfers": 0}
    for _name, part, _labels, _faces, _at in corpus:
        counts["angled_steps"] += len(recognise_angled_steps(part))
        counts["chamfers"] += len(recognise_chamfers(part))

    assert counts == _OBSERVED_RECORDS


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
