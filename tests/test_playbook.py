"""Source coverage and independent geometric/recall expectations."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

from mj_memory_recall import project_path, project_selection, recall
from mj_memory_recall.engine import HERE, catalog_index, selection


TOOL = Path(__file__).resolve().parents[1] / "tools/compare_recall.py"
SPEC = importlib.util.spec_from_file_location("mj_recall_comparison_fixtures", TOOL)
comparison = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(comparison)


class PlaybookCatalog(unittest.TestCase):
    def test_complete_source_catalog_and_hashes(self):
        index = catalog_index()
        self.assertEqual(index["schema"], "MJ-Playbook-Catalog/0.1.0")
        self.assertEqual(len(index["selections"]), 1080)
        self.assertEqual(len(index["families"]), 108)
        self.assertEqual(len(index["formations"]), 360)
        self.assertEqual(index["frame"], {
            "id": "lecanto-schematic-0.9.0", "x_min": "42", "y_min": "55", "width": "748", "height": "455"})
        for name, expected in index["shard_sha256"].items():
            with self.subTest(shard=name):
                self.assertEqual(hashlib.sha256((HERE / "data" / name).read_bytes()).hexdigest(), expected)
        counts = {"OFFENSE": 0, "DEFENSE": 0}
        profile_slots = set()
        path_count = 0
        link_count = 0
        for identity in index["selections"]:
            item = selection(identity)
            counts[item["side"]] += 1
            profile_slots.add((item["side"], item["profile"]))
            self.assertIn(item["formation_id"], index["formations"])
            self.assertEqual(len(item["paths"]), 11)
            self.assertEqual(len({path["actor"] for path in item["paths"]}), 11)
            self.assertEqual([rule["order"] for rule in item["read_rules"]],
                             [1, 2] if item["side"] == "OFFENSE" else [1, 2, 3])
            for path in item["paths"]:
                for key in ("start", "control", "end"):
                    x, y = path[key]
                    self.assertIs(type(x), int)
                    self.assertIs(type(y), int)
                    self.assertTrue(42 <= x <= 790 and 55 <= y <= 510)
            for link in item["sequence_links"]:
                self.assertIn(link["target"], index["selections"])
                link_count += 1
            path_count += len(item["paths"])
        self.assertEqual(counts, {"OFFENSE": 360, "DEFENSE": 720})
        self.assertEqual(len(profile_slots), 20)
        self.assertEqual(path_count, 11880)
        self.assertEqual(link_count, 4320)

    def test_fieldbook_refs_and_real_geometry_collisions_are_preserved(self):
        fieldbook = json.loads((HERE / "data/fieldbook.json").read_text())
        self.assertEqual(fieldbook["source_page_count"], 42)
        self.assertEqual(len(fieldbook["selections"]), 20)
        self.assertEqual([item["diagram_pdf_page_1_based"] for item in fieldbook["selections"]], list(range(3, 42, 2)))
        groups = json.loads((HERE / "data/geometry-collisions.json").read_text())["groups"]
        self.assertEqual(len(groups), 119)
        def geometry(identity):
            return [{key: p[key] for key in ("actor", "kind", "start", "control", "end", "line_style")}
                    for p in selection(identity)["paths"]]
        for identities in groups.values():
            expected = geometry(identities[0])
            self.assertGreater(len(identities), 1)
            for identity in identities[1:]:
                self.assertEqual(geometry(identity), expected)

    def test_native_grid_projection_has_bottom_row_numbering(self):
        # A straight diagonal crosses both exact thirds simultaneously. The
        # independently specified grid puts 7 at top-left and 3 at bottom-right.
        path = {"kind": "RUN_TRACK", "start": [42, 55],
                "control": [416, "282.5"], "end": [790, 510]}
        self.assertEqual(project_path(path, catalog_index()["frame"])["nodes"],
                         [7, 7, 7, 5, 5, 5, 3, 3, 3])
        # The reverse bottom-edge path must visit 3, then 2, then 1.
        path.update(start=[790, 510], control=[416, 510], end=[42, 510])
        self.assertEqual(project_path(path, catalog_index()["frame"])["nodes"],
                         [3, 3, 3, 2, 2, 2, 1, 1, 1])

    def test_native_projection_preserves_all_eleven_original_paths(self):
        identity = "dlxs:offense:inside-zone:base-bangel"
        original = selection(identity)
        result = project_selection(identity)
        self.assertEqual(len(result["paths"]), 11)
        self.assertEqual([p["actor"] for p in result["paths"]], [p["actor"] for p in original["paths"]])
        rb = next(path for path in result["paths"] if path["actor"] == "RB")
        # These exact three points are pinned to the audited original diagram.
        # y(1/4)=375.9375 is below the 358 1/3 boundary; y(3/8)=357.859375 is above it.
        self.assertEqual((rb["start"], rb["control"], rb["end"]),
                         ([445, 412], [450, 340], [461, 267]))
        self.assertEqual(rb["nodes"], [2, 2, 2, 5, 5, 5, 5, 5, 5])
        self.assertEqual(result["source"]["source_sha256"], original["source"]["source_sha256"])
        self.assertFalse(result["physical_actuation_allowed"])


class PlaybookRecallChallenges(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = comparison.build_cases()

    def test_comparison_covers_both_sides_all_profiles_and_exact_ablation(self):
        self.assertEqual(len(self.cases), 32)
        first = [c for c in self.cases if c["id"].startswith("fb-")]
        self.assertEqual(len({(c["target_side"], c["target_profile"]) for c in first}), 20)
        self.assertEqual({c["target_side"] for c in self.cases}, {"OFFENSE", "DEFENSE"})
        for case in self.cases:
            original = case["request"]
            ablated = comparison.trace_only(original)
            self.assertEqual(ablated["query"], original["query"])
            for a, b in zip(original["memories"], ablated["memories"]):
                expected = deepcopy(a)
                expected["selection_id"] = None
                self.assertEqual(b, expected)
            self.assertEqual(case["fixture_kind"], "SYNTHETIC_TEST_FIXTURE")

    def test_playbook_can_recover_a_trace_and_cue_tie(self):
        case = next(c for c in self.cases if c["group"] == "playbook_cue_tie" and c["target_side"] == "OFFENSE")
        full = recall(case["request"])
        ablated = recall(comparison.trace_only(case["request"]))
        self.assertFalse(full["baseline_available"])
        self.assertFalse(ablated["match_available"])
        self.assertEqual(full["candidate"], "memory-target")
        self.assertTrue(full["match_available"])
        self.assertFalse(full["model_updated"])
        self.assertFalse(full["advisory_ready"])

    def test_exact_collision_holds_despite_different_play_identifiers(self):
        case = next(c for c in self.cases if c["group"] == "geometry_collision")
        self.assertNotEqual(case["target_selection"], case["distractor_selection"])
        result = recall(case["request"])
        self.assertEqual(result["status"], "AMBIGUOUS")
        self.assertIsNone(result["candidate"])
        self.assertFalse(result["match_available"])

    def test_source_geometry_does_not_complete_missing_context(self):
        case = next(c for c in self.cases if c["group"] == "context_unknown")
        result = recall(case["request"])
        self.assertEqual(result["candidate"], "memory-target")
        self.assertEqual(result["status"], "CONTEXT_HOLD")
        self.assertFalse(result["match_available"])
        self.assertFalse(result["program_profile_changed"])


if __name__ == "__main__":
    unittest.main()
