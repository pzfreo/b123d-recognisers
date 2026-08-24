"""Closed F5b source-path and executable-case roster."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[1]

AUDITED_CASES = {
    "prismatic_pockets.py": {
        "test_a_triangular_recess_is_recognised_where_wall_pairing_cannot_see_it",
        "test_both_cap_orientations_issue_complete_wall_evidence",
        "test_the_section_is_what_separates_a_triangle_from_a_hexagon",
        "test_a_rectangular_recess_is_reported_by_both_families_and_reconciled_to_one",
        "test_a_void_open_at_both_ends_is_a_passage_and_not_reported_here",
    },
    "passages.py": {
        "test_the_side_count_is_the_polygon_and_not_a_class",
        "test_two_passages_on_one_part_are_reported_separately_and_in_order",
        "test_a_concave_cross_section_is_probed_from_a_point_inside_it",
        "test_a_passage_records_the_ring_it_was_built_from",
        "test_a_part_with_no_void_has_no_passages",
    },
    "groove_exclusions.py": {
        "test_a_narrow_band_between_two_equal_walls_is_a_groove",
        "test_a_groove_with_lead_in_chamfers_is_recognised",
        "test_a_radiused_lead_in_joins_the_groove_bands",
        "test_a_plain_cylinder_has_no_groove",
    },
    "groove_step_claims.py": {
        "test_a_groove_claims_its_floor_band_and_not_the_shaft_either_side",
        "test_a_turned_step_claims_the_bands_that_set_its_diameter",
    },
    "turned_steps.py": {
        "test_two_step_shaft",
        "test_plain_cylinder_is_empty",
    },
    "turned_chamfers.py": {
        "test_direct_reader_recognises_conical_turned_chamfers",
        "test_two_tenths_turned_edge_break_stays_below_evidence_floor",
    },
    "bevel_claims.py": {
        "test_a_chamfer_claims_the_bevel_and_not_the_two_walls_it_bridges",
        "test_an_angled_step_claims_the_slant_and_not_the_flat_that_closes_it",
        "test_the_rule_pairs_each_chamfer_with_its_own_claim_and_not_the_next_ones",
    },
    "angled_steps.py": {
        "test_successful_step_owns_only_the_slant",
        "test_a_bolt_hole_through_the_blind_end_does_not_hide_the_step",
        "test_records_are_ordered_deterministically_and_are_plain_data",
        "test_a_part_with_no_oblique_face_has_no_angled_steps",
    },
    "diagnostics.py": {"test_split_terminal_near_miss_flows_through_the_real_aggregate"},
}

CONSTRUCTOR_COUNTS = {
    "prismatic_pockets.py": ("PrismaticPocket", 1),
    "passages.py": ("Passage", 1),
    "grooves.py": ("Groove", 1),
    "turned.py": ("TurnedStep", 1),
    "chamfers.py": ("Chamfer", 2),
    "angled_steps.py": ("AngledStep", 1),
}


def _function_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }


def test_every_fully_attributed_path_has_named_executable_audit_cases() -> None:
    for filename, required in AUDITED_CASES.items():
        assert required <= _function_names(ROOT / "tests" / f"test_{filename}")


def test_new_record_constructor_paths_require_f5b_roster_review() -> None:
    for filename, (constructor, expected) in CONSTRUCTOR_COUNTS.items():
        tree = ast.parse(
            (ROOT / "src" / "b123d_recognisers" / filename).read_text(encoding="utf-8")
        )
        found = sum(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == constructor
            for node in ast.walk(tree)
        )
        assert found == expected, f"{filename} added or removed an unaudited {constructor} path"
