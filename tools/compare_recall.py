#!/usr/bin/env python3
"""Deterministic diagnostic fixtures for the native memory recall engine.

All returned-memory decisions and scores come from the Bangel engine. Python
generates synthetic fixture inputs, calculates label-based metrics, and writes
the report. These examples never enter a production memory store or training
lineage. OBSERVED in a request only simulates the trusted host's input role.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import random
import sys

from mj_memory_recall import recall
from mj_memory_recall.engine import HERE, catalog_index, path_command, request_digest, selection


SEED = 20260914
PROFILE = "MJ-Memory-Recall-Comparison/0.1.0"
NAMESPACE = "synthetic.fixture.recall"
STEPS = (4, 6, 8)
ACTORS = {"OFFENSE": ("X", "Y", "Z"), "DEFENSE": ("LCB", "FS", "SS")}
PATTERN = ["0.9"] * 9
THRESHOLDS = {
    "known_features_minimum": 3,
    "cue_baseline_score": "0.8",
    "cue_baseline_margin": "0.1",
    "full_and_trace_score": "0.8",
    "full_and_trace_margin": "0.1",
    "base_support": "0.8",
    "assisted_base_support": "0.5",
    "trace_or_playbook_support": "0.9",
    "trace_and_playbook_minimum_observations": 3,
    "weights": {"cue": "1", "trace": "2", "playbook": "2"},
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def curve_point(path, step):
    """Independent exact quadratic-Bezier fixture geometry, t = step / 8."""
    t = Fraction(step, 8)
    u = 1 - t
    return [u * u * a + 2 * u * t * b + t * t * c
            for a, b, c in zip(path["start"], path["control"], path["end"])]


def decimal_string(value):
    value = Fraction(value)
    return format(Decimal(value.numerator) / Decimal(value.denominator), "f")


def events_for(play, steps=STEPS):
    by_actor = {path["actor"]: path for path in play["paths"]}
    events = []
    for actor in ACTORS[play["side"]]:
        path = by_actor[actor]
        for step in steps:
            events.append({"actor": actor, "step": step,
                           "position": [decimal_string(v) for v in curve_point(path, step)],
                           "command": path_command(path["kind"])})
    return events


def far_distractor(target, pool):
    """Choose a diagnostic far-path contrast before any model is executed.

    This is fixture selection, not a classifier or a tuned decision threshold.
    Raw displacement over the predeclared actors and phases defines the order.
    """
    target_paths = {p["actor"]: p for p in target["paths"]}
    ranked = []
    for candidate in pool:
        if candidate["id"] == target["id"] or candidate["side"] != target["side"]:
            continue
        candidate_paths = {p["actor"]: p for p in candidate["paths"]}
        distance = Fraction(0)
        for actor in ACTORS[target["side"]]:
            for step in STEPS:
                a = curve_point(target_paths[actor], step)
                b = curve_point(candidate_paths[actor], step)
                distance += sum((first - second) ** 2 for first, second in zip(a, b))
        ranked.append((-distance, candidate["id"], candidate))
    return min(ranked, key=lambda row: (row[0], row[1]))[2]


def memory(play, name, pattern, trace):
    return {"id": "memory-" + name, "namespace": NAMESPACE, "pattern": list(pattern),
            "entity": "fixture-robot", "relation": "fixture-inspection", "context": "fixture-bench",
            "observed_at": 10, "available_at": 11, "provenance": "OBSERVED",
            "receipt_ref": "synthetic-fixture-only-" + name,
            "selection_id": play["id"], "trace": deepcopy(trace)}


def make_case(case_id, group, target, other, *, cue=None, target_pattern=None,
              other_pattern=None, with_trace=False, expected="memory-target"):
    query_events = events_for(target)
    request = {"profile": "MJ-Memory-Recall/0.1.0", "namespace": NAMESPACE,
               "as_of": 100, "frame": deepcopy(catalog_index()["frame"]),
               "memories": [
                   memory(target, "target", target_pattern or PATTERN,
                          events_for(target, range(9)) if with_trace else []),
                   memory(other, "distractor", other_pattern or PATTERN,
                          events_for(other, range(9)) if with_trace else [])],
               "query": {"id": "query-" + case_id, "observed_at": 100,
                         "cue": deepcopy(cue if cue is not None else PATTERN),
                         "entity": "fixture-robot", "relation": "fixture-inspection", "context": "fixture-bench",
                         "previous_command": query_events[0]["command"], "events": query_events}}
    return {"id": case_id, "group": group, "fixture_kind": "SYNTHETIC_TEST_FIXTURE",
            "expected_verified_match": expected, "target_selection": target["id"],
            "target_side": target["side"], "target_profile": target["profile"],
            "distractor_selection": other["id"], "request": request}


def build_cases():
    index = catalog_index()
    all_plays = [selection(key) for key in sorted(index["selections"])]
    by_id = {play["id"]: play for play in all_plays}
    book = json.loads((HERE / "data/fieldbook.json").read_text(encoding="utf-8"))
    book_ids = [row["id"] for row in book["selections"]]
    if len(book_ids) != 20 or len({(by_id[key]["side"], by_id[key]["profile"]) for key in book_ids}) != 20:
        raise ValueError("fieldbook no longer covers all twenty side/profile slots")
    rng = random.Random(SEED)
    cases = []
    for i, key in enumerate(book_ids):
        target = by_id[key]
        other = far_distractor(target, all_plays)
        if i < 4:
            case = make_case(f"fb-{i+1:02d}", "clean_cue", target, other,
                             other_pattern=["-0.9"] * 9)
        elif i < 12:
            case = make_case(f"fb-{i+1:02d}", "playbook_cue_tie", target, other)
        elif i < 16:
            case = make_case(f"fb-{i+1:02d}", "trace_cue_tie", target, other, with_trace=True)
        else:
            case = make_case(f"fb-{i+1:02d}", "noisy_partial_cue", target, other,
                             cue=["-0.9", "-0.9", None, None] + ["0.9"] * 5)
            for event in case["request"]["query"]["events"]:
                event["position"] = [decimal_string(Fraction(v) + rng.choice((-3, -2, 2, 3)))
                                     for v in event["position"]]
        cases.append(case)

    for side in ("OFFENSE", "DEFENSE"):
        target = by_id[next(key for key in book_ids if by_id[key]["side"] == side)]
        other = far_distractor(target, all_plays)
        corrupt = list(PATTERN)
        for offset in rng.sample(range(9), 3):
            corrupt[offset] = "-0.9"
        cases.append(make_case("misleading-" + side.lower(), "misleading_cue", target, other,
                               cue=corrupt, other_pattern=corrupt))

    collisions = json.loads((HERE / "data/geometry-collisions.json").read_text(encoding="utf-8"))["groups"]
    for side in ("OFFENSE", "DEFENSE"):
        groups = sorted(tuple(sorted(ids)) for ids in collisions.values()
                        if by_id[ids[0]]["side"] == side)
        for i, ids in enumerate(groups[:2]):
            cases.append(make_case(f"collision-{side.lower()}-{i+1}", "geometry_collision",
                                   by_id[ids[0]], by_id[ids[1]], expected=None))

    for group in ("context_unknown", "context_mismatch", "out_of_set"):
        for side in ("OFFENSE", "DEFENSE"):
            target = by_id[next(key for key in book_ids if by_id[key]["side"] == side)]
            other = far_distractor(target, all_plays)
            case = make_case(group.replace("_", "-") + "-" + side.lower(), group, target, other,
                             other_pattern=["-0.9"] * 9 if group != "out_of_set" else PATTERN,
                             expected=None)
            if group == "context_unknown":
                case["request"]["query"]["context"] = None
            elif group == "context_mismatch":
                case["request"]["query"]["context"] = "different-fixture-bench"
            else:
                case["request"]["query"]["cue"] = ["-0.9"] * 9
                third = next(p for p in all_plays if p["side"] == side and p["id"] not in (target["id"], other["id"]))
                case["request"]["query"]["events"] = events_for(third)
                case["out_of_set_selection"] = third["id"]
            cases.append(case)
    if len(cases) != 32 or len({case["id"] for case in cases}) != 32:
        raise ValueError("comparison must contain exactly thirty-two unique fixtures")
    return cases


def trace_only(request):
    result = deepcopy(request)
    for item in result["memories"]:
        item["selection_id"] = None
    return result


def compact_result(result):
    return {key: deepcopy(result[key]) for key in (
        "status", "candidate", "candidate_available", "match_available",
        "baseline_available", "baseline_candidate", "known_features", "scores", "margin",
        "forecast", "review_status", "advisory_ready", "request_sha256", "jp_sha256",
        "receipt_root", "source_sha256", "model_updated", "program_profile_changed")}


def accepted(result, arm):
    if arm == "cue_only":
        return result["baseline_candidate"] if result["baseline_available"] else None
    return result["candidate"] if result["match_available"] else None


def metrics(rows, arm):
    positives = sum(row["expected_verified_match"] is not None for row in rows)
    decisions = [(row["expected_verified_match"], row["decisions"][arm]) for row in rows]
    correct = sum(wanted is not None and got == wanted for wanted, got in decisions)
    false_matches = sum(got is not None and got != wanted for wanted, got in decisions)
    returned = sum(got is not None for _, got in decisions)
    return {"cases": len(rows), "positive_cases": positives,
            "correct_verified_matches": correct, "false_matches_or_unqualified_returns": false_matches,
            "missed_positive_cases": positives-correct, "returns": returned, "holds": len(rows)-returned,
            "recall": f"{correct}/{positives}" if positives else None,
            "recall_percent": round(100*correct/positives, 6) if positives else None,
            "coverage_percent": round(100*returned/len(rows), 6) if rows else None,
            "precision_percent": round(100*correct/returned, 6) if returned else None}


def run_comparison(cases):
    initial_sources = {"engine.py": sha((HERE / "engine.py").read_bytes()),
                       "recall.bangel": sha((HERE / "source/recall.bangel").read_bytes()),
                       "catalog_index.json": sha((HERE / "data/index.json").read_bytes())}
    rows = []
    for number, case in enumerate(cases, 1):
        request = deepcopy(case["request"])
        ablated = trace_only(request)
        full = recall(request)
        trace = recall(ablated)
        if full["source_sha256"]["recall.bangel"] != initial_sources["recall.bangel"] or trace["source_sha256"]["recall.bangel"] != initial_sources["recall.bangel"]:
            raise ValueError("native source changed during the controlled comparison")
        if full["baseline_candidate"] != trace["baseline_candidate"] or full["baseline_available"] != trace["baseline_available"]:
            raise ValueError("playbook ablation changed the cue-only baseline")
        if full["model_updated"] or trace["model_updated"] or full["advisory_ready"] or trace["advisory_ready"]:
            raise ValueError("a synthetic diagnostic fixture gained update or action authority")
        rows.append({**case, "input_sha256": request_digest(request), "trace_only_input_sha256": request_digest(ablated),
                     "decisions": {"cue_only": accepted(full, "cue_only"),
                                   "trace_only": accepted(trace, "trace_only"),
                                   "trace_plus_playbook": accepted(full, "trace_plus_playbook")},
                     "trace_plus_playbook": compact_result(full), "trace_only": compact_result(trace)})
        print(f"{number}/{len(cases)} {case['id']}: {rows[-1]['decisions']}", file=sys.stderr, flush=True)
    if sha((HERE / "engine.py").read_bytes()) != initial_sources["engine.py"]:
        raise ValueError("host adapter changed during the controlled comparison")
    arms = ("cue_only", "trace_only", "trace_plus_playbook")
    groups = defaultdict(list)
    for row in rows:
        groups[row["group"]].append(row)
    return {"profile": PROFILE, "fixture_kind": "SYNTHETIC_TEST_FIXTURE", "seed": SEED,
            "source_sha256": initial_sources, "tool_sha256": sha(Path(__file__).read_bytes()),
            "thresholds": THRESHOLDS, "fixture_count": len(rows), "native_retrieval_runs": 2*len(rows),
            "input_set_sha256": sha(canonical([row["request"] for row in rows]).encode()),
            "results_sha256": sha(canonical([{k: row[k] for k in ("id", "input_sha256", "trace_only_input_sha256", "decisions", "trace_only", "trace_plus_playbook")} for row in rows]).encode()),
            "metrics": {arm: metrics(rows, arm) for arm in arms},
            "group_metrics": {key: {arm: metrics(value, arm) for arm in arms} for key, value in sorted(groups.items())},
            "side_counts": dict(Counter(row["target_side"] for row in rows)),
            "fieldbook_profile_slots": sorted({row["target_side"] + ":" + row["target_profile"] for row in rows if row["id"].startswith("fb-")}),
            "production_training": False, "production_store_writes": False,
            "rows": rows}


def markdown(report):
    lines = ["# Controlled native recall comparison", "",
        "This is a deterministic diagnostic study of 32 explicitly synthetic fixtures, with two candidate memory episodes per query. It is not a production accuracy estimate, a biological result, or a claim of statistical significance.", "",
        "The first 20 queries use the exact 20 fieldbook selections and cover all 10 offense and 10 defense profile slots. The remaining cases test misleading cues, exact geometric collisions, missing or mismatched context, and out-of-set cues. Source curves retain their original schematic coordinates. Three source actors are sampled at phases 1/2, 3/4 and 1; noisy cases add a fixed-seed displacement of two or three canvas units, remove two cue values and reverse two cue signs.", "",
        "Far-path distractors are selected deterministically from same-side catalog geometry before calling the model. This deliberately tests discriminable paths. Exact-collision cases separately test refusal when geometry cannot distinguish memories. The dataset is small, constructed, and partly favorable to the overlay; results do not establish generalization across the ecosystem.", "",
        "All classifications and scores run in native Bangel. The cue-only baseline is emitted by the same native retrieval call. Trace-only ablation repeats the identical query, events, context, cue patterns and traces, changing only each memory's selection_id to null. The full-versus-trace contrast isolates access to the playbook. All arms use the same fixed 0.1 winner margin, 0.8 acceptance score, and minimum of three known cue features. Full and trace-only also use entity, relationship and context gates that the cue-only baseline lacks; their difference from cue-only is not solely a playbook effect.", "",
        "No thresholds were tuned on these results. Seed: `20260914`. Synthetic labels remain outside production requests. `OBSERVED` in fixture requests only simulates the trusted host's observation role; it is not authenticated provenance, real game-film evidence, or permission to train. The comparison performs no persistent store writes, kernel updates, or downstream actions.", "",
        "A positive case has one expected verified memory match. Negative cases have no acceptable verified return, including context holds and unresolved collisions. False matches below include any wrong memory **or unqualified return** in those negative cases. Recall divides correct positive returns by all positive cases; coverage divides returns by all 32 cases. Missing context is not counted as recovered evidence.", "",
        "| Arm | Correct positive returns | False or unqualified returns | Recall | Coverage | Holds |",
        "|---|---:|---:|---:|---:|---:|"]
    for arm, title in (("cue_only", "Cue only"), ("trace_only", "Cue + trace"), ("trace_plus_playbook", "Cue + trace + playbook")):
        m = report["metrics"][arm]
        lines.append(f"| {title} | {m['correct_verified_matches']}/{m['positive_cases']} | {m['false_matches_or_unqualified_returns']} | {m['recall_percent']:.2f}% | {m['coverage_percent']:.2f}% | {m['holds']} |")
    lines += ["", "| Fixture group | Cases | Cue correct / false | Trace correct / false | Full correct / false |",
              "|---|---:|---:|---:|---:|"]
    for group, values in report["group_metrics"].items():
        scores = [str(values[a]["correct_verified_matches"]) + " / " + str(values[a]["false_matches_or_unqualified_returns"]) for a in ("cue_only", "trace_only", "trace_plus_playbook")]
        lines.append(f"| {group} | {values['cue_only']['cases']} | {' | '.join(scores)} |")
    lines += ["", "The following hashes bind the generated inputs and outputs to the evaluated source. Re-run the checked-in tool against these sources to reproduce the report; the optional JSON output includes every request, expected label, native decision, receipt root and per-request source hash.", "",
              "| Material | SHA-256 |", "|---|---|"]
    for key, value in {**report["source_sha256"], "comparison_tool": report["tool_sha256"], "input_set": report["input_set_sha256"], "results": report["results_sha256"]}.items():
        lines.append(f"| {key} | `{value}` |")
    lines += ["", "| Fixture | Expected verified return | Cue | Trace | Full | Input SHA-256 |",
              "|---|---|---|---|---|---|"]
    for row in report["rows"]:
        def short(value): return "hold" if value is None else value.removeprefix("memory-")
        lines.append(f"| {row['id']} | {short(row['expected_verified_match'])} | {short(row['decisions']['cue_only'])} | {short(row['decisions']['trace_only'])} | {short(row['decisions']['trace_plus_playbook'])} | `{row['input_sha256']}` |")
    lines += ["", "```bash", "PYTHONPATH=language/python/src:plugins/mj_memory_recall/src python3 -B plugins/mj_memory_recall/tools/compare_recall.py --output comparison.json", "```", "",
              "The recall improvement in this fixture set is conditional on informative playbook geometry and the declared command binding. A larger blinded corpus, realistic distractors, source-independent trajectories, and equal-recall or equal-coverage comparisons remain necessary before making a deployment-performance claim.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write complete deterministic JSON report")
    parser.add_argument("--markdown", type=Path, help="write the comparison note")
    parser.add_argument("--list-fixtures", action="store_true", help="print input hashes before running any model")
    args = parser.parse_args()
    cases = build_cases()
    if args.list_fixtures:
        print(json.dumps([{k: v for k, v in case.items() if k != "request"} | {"input_sha256": request_digest(case["request"])} for case in cases], indent=2))
        return 0
    report = run_comparison(cases)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown(report), encoding="utf-8")
    print(json.dumps({"profile": PROFILE, "seed": SEED, "metrics": report["metrics"],
                      "input_set_sha256": report["input_set_sha256"], "results_sha256": report["results_sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
