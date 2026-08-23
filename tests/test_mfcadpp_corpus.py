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
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pytest
from build123d import import_step

import b123d_recognisers as recognition
from b123d_recognisers import _recess_core as recess_core
from b123d_recognisers import recognise_angled_steps, recognise_chamfers, recognise_slots
from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._reconcile import (
    chamfers_that_are_not_angled_steps,
    reconcile_recesses,
)

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))

from per_face_scan import scan_part  # noqa: E402

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
CHAMFER, TRIANGULAR_BLIND_STEP, STOCK = 0, 20, 24


def _bevels(part):
    """The two bevel families against one ledger: what each proposed, and what survives.

    ``recognise_chamfers`` proposes a blind step's slant, because on the face alone it is a
    bevel; the rule drops the ones ``recognise_angled_steps`` claimed. Every test below that
    asks about *chamfers* asks about ``kept``, since that is what a consumer running the
    aggregate or the census receives.
    """

    ledger = ClaimLedger(FaceGraph(part))
    proposed = recognise_chamfers(part, ledger=ledger)
    steps = recognise_angled_steps(part, ledger=ledger)
    return (
        proposed,
        chamfers_that_are_not_angled_steps(
            proposed, steps, ledger.snapshot_index()
        ),
        steps,
    )


def test_slot_walls_must_turn_consistently_into_one_void(corpus, monkeypatch):
    """A 0.19 mm wall overlap joins two labelled features only when AAG arcs are ignored.

    The two faces are parallel, opposed and overlap, so bounding boxes alone report a slot.
    They do not bound one recess: their shared boundary turns concavely from one wall and
    convexly from the other.  Disabling the arc-consistency gate restores two false candidates,
    including the grazing one from issue #119; with it, only the coherent slot remains.
    """

    part = next(part for name, part, *_rest in corpus if name == "10063.step")
    coherent = recognise_slots(part)
    assert len(coherent) == 1

    monkeypatch.setattr(recess_core, "_candidate_has_void_evidence", lambda *_args: True)
    assert len(recognise_slots(part)) == 1, "the AAG gate alone rejects both false pairs"

    monkeypatch.setattr(recess_core, "_bounds_one_void", lambda *_args: True)
    unguarded = recognise_slots(part)
    assert len(unguarded) == 3
    assert min(slot.d_hi - slot.d_lo for slot in unguarded) == pytest.approx(0.19, abs=1e-6)


def _is_oblique(face) -> bool:
    """A planar face aligned with no principal axis -- what a chamfer face is."""

    try:
        normal = face.normal_at()
    except Exception:  # noqa: BLE001 - a degenerate face has no normal to read
        return False
    return max(abs(normal.X), abs(normal.Y), abs(normal.Z)) < 0.99


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
    # Exact, not `in`: `rule["split"] in source.lower()` was satisfied by the word "latest",
    # so `source: "MFCAD++ train split, latest revision"` passed with `split: test` -- the
    # exact contradiction the check was added to catch.
    assert manifest["source"] == f"MFCAD++ {rule['split']} split"
    assert rule["order"] == "filename, ascending"
    assert rule["precondition"] == "STEP ADVANCED_FACE count equals part.faces() count"
    assert rule["targets"] == {
        "0": "Chamfer",
        "4": "6-sided passage",
        "9": "2-sided through step",
        "13": "Triangular pocket",
        "20": "Triangular blind step",
    }
    assert manifest["doi"] == (
        "https://doi.org/10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823"
    ), "the DOI is what locates this dataset upstream; a prefix match pins nothing"

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
    per_model_chamfers_all_oblique = []
    per_model_stock_all_axis_aligned = []
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

        # Per model, because the sums above cannot see corruption confined to a subset. Every
        # face MFCAD++ labels Chamfer in a given model is an oblique plane -- true of all 40
        # today, and the property that breaks first if face order stops matching label order
        # for some models and not others.
        # Stock, because every model has it and the chamfer label covers only 14 of 40 --
        # rotating the labels of a model with no chamfer faces was undetectable without this.
        # Every face MFCAD++ labels Stock is axis-aligned, in all 40 models, so a rotation
        # moves an oblique face under that label and fails here.
        stock = [f for f, label in zip(faces, labels, strict=True) if label == STOCK]
        assert stock, f"{name}: no Stock faces; the per-model check would be vacuous"
        if any(_is_oblique(f) for f in stock):
            per_model_stock_all_axis_aligned.append(name)

        chamfers = [f for f, label in zip(faces, labels, strict=True) if label == CHAMFER]
        if chamfers and not all(_is_oblique(f) for f in chamfers):
            per_model_chamfers_all_oblique.append(name)

    chamfer_oblique = oblique[True][1] / sum(oblique[True])

    # Corpus-wide, this bites only for corpus-wide corruption: a rotate-by-one across all 40
    # models drops it to 0.208. Rotating the 19 models that yield no records left it at 0.917
    # and the whole module green -- and a kernel upgrade reordering faces for one topology is
    # exactly that partial shape. So the per-model check below is the one that matters, and
    # this is the aggregate summary.
    assert chamfer_oblique > 0.75, "faces labelled Chamfer are not mostly oblique planes"
    assert per_model_stock_all_axis_aligned == [], (
        f"models with an oblique face labelled Stock: {per_model_stock_all_axis_aligned}"
    )
    assert per_model_chamfers_all_oblique == [], (
        f"models whose Chamfer-labelled faces are not all oblique planes: "
        f"{per_model_chamfers_all_oblique}"
    )

    # And this is the genuinely second check, on a different label and a different property.
    # Two previous attempts were not: `other_oblique < 0.40` cannot fail, since 30.9% of all
    # 1335 faces are oblique and only 24 carry label 0, so no relabelling can push the rest
    # past 0.315. Nor could `chamfer_oblique > 2 * other_oblique` -- bounded that way, twice
    # `other_oblique` never reaches 0.63, so the 0.75 line above already implies it. A
    # redundancy replacing a tautology. Note the blind spot both shared is NOT closed by this
    # one either -- swapping labels 0 and 4 leaves label 20 untouched, so this test still
    # passes and only `test_chamfer_precision_does_not_regress` catches it.
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
    chamfers on the same part were rejected. Breaking the reconciliation — the rule, the claims
    either family writes, or the blind-end test the step family gates on — reintroduces exactly
    that, and this is what says so.

    Asked of the reconciled list, which is what `feature_census` and
    `build_recognition_result` report. `recognise_chamfers` on its own proposes the slant; the
    next test is the one that pins that, and pins that the rule takes every one of them back.
    """

    stolen, resolved = [], 0
    for name, part, _labels, _faces, at_label in corpus:
        _, kept, _ = _bevels(part)
        for record in kept:
            label = at_label.get(record.at)
            resolved += label is not None
            if label == TRIANGULAR_BLIND_STEP:
                stolen.append((name, record.at))

    # Without this the test passes when attribution stops resolving entirely: replacing the
    # lookup key with one that can never match left it green, which would make "the direct
    # regression guard" a silent no-op. All 14 chamfer records resolve today.
    assert resolved, "no chamfer record resolved to a labelled face; attribution is broken"
    assert stolen == [], f"chamfer records on faces labelled a blind step: {stolen}"


def test_the_rule_takes_back_every_slant_the_chamfer_family_proposes(corpus):
    """What the reconciliation actually removes, on geometry this project did not author.

    Two claims at once, and neither is checkable from counts alone:

    - every record `recognise_chamfers` gains by no longer declining a triangular-ended bevel
      lands on a face MFCAD++ labels a *Triangular blind step* — so the proposals it now makes
      are exactly the slants, not some wider set;
    - the rule drops all of them, so nothing survives into the reconciled list that the labels
      call a step.

    Measured here: 8 of the 11 steps across 40 models are proposed as chamfers and all 8 are
    taken back. The other 3 never reach the rule — `recognise_chamfers` turns them away as
    spanning wedges, its own gate and nothing to do with the blind end, which is why "one
    proposal per step" is not the assertion.
    """

    dropped = matched = steps_found = 0
    wrong = []
    for name, part, _labels, _faces, at_label in corpus:
        proposed, kept, steps = _bevels(part)
        steps_found += len(steps)
        taken = [record for record in proposed if record not in kept]
        dropped += len(taken)
        assert len(kept) + len(taken) == len(proposed), f"{name}: the rule invented a record"
        for record in taken:
            if at_label.get(record.at) == TRIANGULAR_BLIND_STEP:
                matched += 1
            else:
                wrong.append((name, record.at, at_label.get(record.at)))

    assert steps_found == 11, f"the corpus no longer carries 11 angled steps: {steps_found}"
    assert dropped == 8, f"the rule dropped {dropped} chamfer proposals, not 8"
    assert wrong == [], f"proposals dropped on faces MFCAD++ does not label a blind step: {wrong}"
    assert matched == dropped


#: Record counts as of vendoring, **per model**. Not a correctness baseline -- a change
#: detector, as ``_OBSERVED`` is on the NIST side. Per model rather than per corpus because
#: two grand totals cannot see a redistribution: moving one angled step from the model that
#: owns it to a model that owns none leaves both sums intact, and that is a real behaviour
#: change on two of forty models. The NIST sibling was already per model; this was not, which
#: is the same asymmetry as the volume blindness it replaced.
_OBSERVED_RECORDS = {
    "10000.step": {
        "angled_steps": 1
    },
    "10007.step": {
        "angled_steps": 1
    },
    "10020.step": {
        "chamfers": 1
    },
    "10033.step": {
        "chamfers": 2
    },
    "10049.step": {
        "angled_steps": 1
    },
    "10063.step": {
        "angled_steps": 1
    },
    "10077.step": {
        "chamfers": 2
    },
    "1008.step": {
        "chamfers": 1
    },
    "10092.step": {
        "chamfers": 1
    },
    "10101.step": {
        "angled_steps": 1
    },
    "10103.step": {
        "chamfers": 1
    },
    "10119.step": {
        "angled_steps": 1
    },
    "10131.step": {
        "chamfers": 1
    },
    "10138.step": {
        "angled_steps": 2
    },
    "10146.step": {
        "chamfers": 1
    },
    "10163.step": {
        "chamfers": 1
    },
    "1017.step": {
        "chamfers": 2
    },
    "10170.step": {
        "chamfers": 1
    },
    "10224.step": {
        "angled_steps": 1
    },
    "10245.step": {
        "angled_steps": 1
    },
    "10247.step": {
        "angled_steps": 1
    }
}


def test_the_records_each_model_yields_have_not_moved(corpus):
    """Volume and distribution. Precision and the >=1 gates are blind to both."""

    actual = {}
    for name, part, _labels, _faces, _at in corpus:
        _, kept, steps = _bevels(part)
        counts = {"angled_steps": len(steps), "chamfers": len(kept)}
        found = {k: v for k, v in counts.items() if v}
        if found:
            actual[name] = found

    assert actual == _OBSERVED_RECORDS


def test_chamfer_precision_does_not_regress(corpus):
    """A floor, not a target: this subset is deliberately stocked with confusable classes.

    Twelve models were selected for each of triangular pocket, 2-sided through step and
    6-sided passage precisely because their walls are oblique planes that a chamfer
    recogniser can mistake, so precision here is a harder number than on a random sample —
    79% against 78% over 120 unselected models. It was 44% before the angled-step family.
    """

    records = correct = 0
    for _name, part, _labels, _faces, at_label in corpus:
        _, kept, _ = _bevels(part)
        for record in kept:
            records += 1
            correct += at_label.get(record.at) == CHAMFER

    assert records, "no chamfers recognised at all"
    assert correct / records >= 0.70, (
        f"chamfer precision fell to {100 * correct / records:.0f}% "
        f"({correct}/{records}); it was 79% when this subset was vendored and 44% before "
        "recognise_angled_steps existed"
    )


def _per_face(corpus):
    """Every claimed face across the corpus, as ``{family: Counter(label)}``.

    Attribution by *claim* rather than by matching a record's ``at`` against a face centroid,
    which is what the two tests above have to do because their families' records happen to
    anchor on a face. A claim names its faces, so this needs no coincidence of coordinates and
    works for a family whose record anchors on nothing in particular.
    """

    totals: dict[str, Counter] = defaultdict(Counter)
    for _name, part, labels, _faces, _at in corpus:
        claimed, _records, _covered = scan_part(part, labels)
        for family, counts in claimed.items():
            totals[family].update(counts)
    return totals


def test_no_claim_lands_on_a_stock_face(corpus):
    """A change detector on this subset, and not the invariant it first claimed to be.

    ``Stock`` labels 271 of these models' faces, and no family claims one. That is worth
    pinning: a family could start claiming unmachined billet and still score well on precision
    if it claimed enough real faces alongside, so this catches something a rate cannot.

    **It is not a universal law, and an earlier version of this docstring said it was.** Over
    2,000 models four claims do land on *Stock*, and the clearest of them is not a defect:
    `recognise_passages` reports a genuine 6-sided passage on `11251.step` whose six walls
    carry *five different labels*, two of them ``Stock``. MFCAD++ assigns each face to exactly
    one feature, so where features intersect, a passage wall that is also chamfered is labelled
    *Chamfer* and one bounded by raw billet is labelled *Stock*. ``Stock`` means "assigned to
    no feature", which is weaker and corpus-specific.

    So a failure here is a prompt to look, not a proof of a bug -- and fitting a recogniser to
    this corpus's label assignment would cost more than it bought.
    """

    claimed = _per_face(corpus)
    on_stock = {
        family: counts[STOCK] for family, counts in claimed.items() if counts.get(STOCK)
    }
    assert on_stock == {}, f"claims on unmachined stock: {on_stock}"


def test_what_the_claiming_families_actually_claim_has_not_moved(corpus):
    """Per-face attribution for the four families MFCAD++ can see, as a change detector.

    Not a correctness baseline. Two of these are *invariants* and the other two are
    *observations*, and the difference matters when one of them moves:

    - **Angled steps and passages are exact**, and should stay exact. Every face either claims
      is labelled the feature it says it is -- for passages across all three shape variants,
      which the family deliberately does not distinguish.
    - **Chamfer at 11 of 14** is the same 79% ``test_chamfer_precision_does_not_regress``
      measures from record centroids, arrived at independently through the ledger. The two
      disagreeing would mean one of the attribution methods is wrong.
    - **Slot is the accepted aggregate inventory.** Boundary reconciliation has removed the
      paired-wall fragments that complete pocket and passage rings explain; the remainder is
      pinned here as a change detector, not asserted to match MFCAD++'s single-label taxonomy.
    """

    claimed = _per_face(corpus)
    passages = {"Triangular passage": 2, "Rectangular passage": 3, "6-sided passage": 4}

    steps = claimed["AngledStep"]
    assert set(steps) == {TRIANGULAR_BLIND_STEP} and sum(steps.values()) == 11

    ring = claimed["Passage"]
    assert set(ring) == set(passages.values()), "a passage claimed a non-passage face"
    assert sum(ring.values()) == 115

    bevels = claimed["Chamfer"]
    assert bevels[CHAMFER] == 11 and sum(bevels.values()) == 14

    slots = claimed["Slot"]
    # Exact prism evidence removes two paired-wall interpretations whose nominal boxes contain
    # material: a 6-sided pocket fragment in 10101 and a rectangular-slot-labelled pair in
    # 10138 whose proposed prism is 57% solid. The latter label is face-local evidence, not proof
    # that this particular opposed pair describes the labelled removal's volume.
    assert sum(slots.values()) == 34
    assert slots[16] == 28, "most accepted Slot walls are labelled Circular end pocket"

    # Pockets are the blind counterpart and land mostly where the name says. Complete ring
    # containment removes the old passage fragments; partial intersections deliberately remain.
    pockets = claimed["Pocket"]
    # #142 removes cross-feature and incomplete rectangular interpretations in 10131, 10170 and
    # 10212. Their proposed prisms are respectively 7%, 31% and 27% solid. Four removed defining
    # faces carry the corpus's rectangular-pocket label, illustrating why the corpus is diagnostic
    # evidence rather than the feature definition.
    assert sum(pockets.values()) == 87
    assert pockets[14] == 38, "most of what Pocket claims is labelled Rectangular pocket"
    assert pockets[3] == 2, "complete passage rings remove the old pocket fragments"


def test_accepted_recess_claims_have_no_containment_conflicts(corpus):
    """#112 leaves only compatible partial overlaps, not duplicate descriptions of one void."""

    overlaps = []
    for name, part, _labels, _faces, _at in corpus:
        graph = FaceGraph(part)
        ledger = ClaimLedger(graph)
        slots = recognition.recognise_slots(part, ledger=ledger)
        pockets = recognition.recognise_pockets(part, ledger=ledger)
        prismatic = recognition.recognise_prismatic_pockets(part, ledger=ledger)
        passages = recognition.recognise_passages(part, ledger=ledger)
        for family, records in (
            (FamilyId.SLOTS, slots),
            (FamilyId.POCKETS, pockets),
            (FamilyId.PRISMATIC_POCKETS, prismatic),
            (FamilyId.PASSAGES, passages),
        ):
            ledger.candidate_set_for(family, records)
        accepted = reconcile_recesses(
            slots,
            pockets,
            prismatic,
            passages,
            ledger.snapshot_index(),
        )
        records = [record for family in accepted for record in family]
        for index, left in enumerate(records):
            left_faces = ledger.defining_of(left)
            for right in records[index + 1 :]:
                if type(left) is type(right):
                    continue
                right_faces = ledger.defining_of(right)
                shared = left_faces & right_faces
                if shared:
                    overlaps.append(
                        (name, type(left).__name__, type(right).__name__, left_faces, right_faces)
                    )

    signatures = [
        (name, {left, right}, len(left_faces & right_faces))
        for name, left, right, left_faces, right_faces in overlaps
    ]
    assert signatures == [
        ("10190.step", {"Pocket", "Slot"}, 1),
    ]
    assert all(
        not left_faces <= right_faces and not right_faces <= left_faces
        for _name, _left, _right, left_faces, right_faces in overlaps
    )
