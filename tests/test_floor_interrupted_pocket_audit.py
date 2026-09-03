from __future__ import annotations

import ast
import inspect

from tools import audit_mfcadpp_floor_interrupted_pockets as audit


def test_labels_are_read_after_the_geometric_candidate_roster() -> None:
    tree = ast.parse(inspect.getsource(audit._audit_model))
    assignments = {
        target.id: node.lineno
        for node in ast.walk(tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (
            node.targets if isinstance(node, ast.Assign) else (node.target,)
        )
        if isinstance(target, ast.Name)
    }
    label_reads = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "load_mfcadpp_truth"
    ]

    # The exceptional read only documents a failed import.  The normal-path read follows both
    # the neutral region inventory and every geometric probe.
    assert len(label_reads) == 2
    assert assignments["raw"] < assignments["probes"] < max(label_reads)


def test_target_scope_is_only_the_three_polygonal_pocket_classes() -> None:
    assert {13, 14, 15} == audit._TARGET_CLASSES
