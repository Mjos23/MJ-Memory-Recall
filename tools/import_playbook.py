#!/usr/bin/env python3
"""Package the audited physics playbook as deterministic Bangel data shards.

This importer reads data only. It does not import or execute the recovered
reference implementation. Supply its historical product label explicitly; the
published catalog uses current Bangel spelling and retains original byte hashes.
The pinned audit extraction is the reviewed source for this catalog version.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


SCHEMA = "MJ-Playbook-Catalog/0.1.0"
AUDIT_SHA256 = {
    "plays.raw.jsonl": "b677c18ffadb96df6a97249e71311a6ab8e7bded1b2aa9d9cf553b2e167e5ced",
    "formations.raw.jsonl": "44deb6617b5667c2b7fc7f844165a13cd004f30e8ec7188a78419d4d0f4a8225",
    "families.raw.json": "6506761f976d37cc1188f4bedf7d6fb2628c7fd74defc50965af8f7ea72907d5",
    "profiles.raw.json": "2e9bf3eb2e705078557b93e22e90fca497d130d45b632c139ff3d3bdb8cd57bf",
    "archive-provenance.json": "e0c7390a7aaa425c34c32761f55ac0654b7fd6c9ac987b8033bc19abb68962d5",
    "summary.json": "74f457e5d091f98c4fd17b7d4f13b8fb0c9d7da58b4cd4c1749c459e4eb0e56c",
    "geometry-collisions.json": "d3ec01415cc784b19471c961d25fb54167f16bff8de64788fddb03890771238e",
}
FRAME = {
    "id": "lecanto-schematic-0.9.0",
    "x_min": "42",
    "y_min": "55",
    "width": "748",
    "height": "455",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode(value: Any, *, pretty: bool = False) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       indent=2 if pretty else None,
                       separators=None if pretty else (",", ":")) + "\n").encode("utf-8")


def load_audit(root: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = {}
    for name, expected in AUDIT_SHA256.items():
        raw = (root / name).read_bytes()
        if digest(raw) != expected:
            raise ValueError(f"reviewed audit checksum mismatch: {name}")
        loaded[name] = ([json.loads(line) for line in raw.splitlines()]
                        if name.endswith(".jsonl") else json.loads(raw))
    return loaded


def migration(label: str):
    if not re.fullmatch(r"[A-Za-z][A-Za-z -]{0,63}", label):
        raise ValueError("historical product label must be a short explicit alphabetic name")
    pattern = re.compile(re.escape(label), re.IGNORECASE)

    def text(value: str) -> str:
        def replace(match: re.Match[str]) -> str:
            old = match.group(0)
            return "BANGEL" if old.isupper() else "bangel" if old.islower() else "Bangel"
        return pattern.sub(replace, value)

    def convert(value: Any) -> Any:
        if isinstance(value, str):
            return text(value)
        if isinstance(value, list):
            return [convert(item) for item in value]
        if isinstance(value, dict):
            keys = [text(key) for key in value]
            if len(keys) != len(set(keys)):
                raise ValueError("identity migration would merge distinct object keys")
            return {text(key): convert(item) for key, item in value.items()}
        return value
    return convert


def source_record(source: dict[str, Any], original_id: str, convert) -> dict[str, Any]:
    views = {view["view_kind"]: view for view in source["views"]}
    primary = views.get("PLAY", views.get("FORMATION"))
    result = {
        "source_sha256": source["source_sha256"],
        "logic_sha256": source["original_logic_sha256"],
        "view_sha256": primary["render_sha256"],
        "original_id_sha256": digest(original_id.encode("utf-8")),
        "document_id": convert(source["document_id"]),
        "compilation_receipt_id": source["compilation_receipt_id"],
        "receipt_sha256": source["receipt_member_sha256"],
        "logic_archive": "playbook-atlas",
        "logic_member": "atlas.jsonl",
        "logic_line": source["atlas_line_1_based"],
        "logic_line_sha256": source["atlas_line_sha256"],
        "source_archive": "lecanto-atlas-0.9.0",
        "source_member": "sources.jsonl",
        "source_line": source["lecanto_line_1_based"],
        "source_line_sha256": source["lecanto_line_sha256"],
        "hash_scope": "ORIGINAL_UNMODIFIED_SOURCE_BYTES",
        "document_id_display_migrated": True,
    }
    if "SEQUENCE" in views:
        result["sequence_view_sha256"] = views["SEQUENCE"]["render_sha256"]
    return result


def package(audit: dict[str, Any], label: str) -> dict[str, bytes]:
    convert = migration(label)
    profiles = audit["profiles.raw.json"]
    if profiles["OFFENSE"][0]["profile"] != "BASE_" + label.upper():
        raise ValueError("historical product label does not match the reviewed source")
    raw_plays = audit["plays.raw.jsonl"]
    raw_formations = audit["formations.raw.jsonl"]
    raw_families = audit["families.raw.json"]
    if (len(raw_plays), len(raw_formations), len(raw_families)) != (1080, 360, 108):
        raise ValueError("incomplete source catalog")

    files: dict[str, bytes] = {}
    family_index: dict[str, str] = {}
    selection_index: dict[str, str] = {}
    formation_index: dict[str, str] = {}
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for play in raw_plays:
        groups[play["family_id"]].append(play)
    if set(groups) != {family["family_id"] for family in raw_families}:
        raise ValueError("catalog family coverage mismatch")

    path_count = 0
    for raw_family in raw_families:
        family = convert(raw_family)
        members = groups[raw_family["family_id"]]
        if len(members) != 10 or {p["profile_index"] for p in members} != set(range(10)):
            raise ValueError("each family must retain all ten profile variants")
        file = f"families/{family['side'].lower()}-{family['slug']}.json"
        if not re.fullmatch(r"families/(offense|defense)-[a-z0-9-]+\.json", file):
            raise ValueError("invalid family shard name")
        family["provenance"] = {
            "archive": "reference-implementation-0.10.0",
            "member_sha256": raw_family["provenance"]["member_sha256"],
            "read_rule_source_lines": raw_family["provenance"]["read_rule_source_lines"],
            "hash_scope": "ORIGINAL_UNMODIFIED_SOURCE_BYTES",
        }
        for shared in ("physics_algorithms", "player_technique_policy", "evidence_policy"):
            values = [p[shared] for p in members]
            if any(value != values[0] for value in values[1:]):
                raise ValueError(f"cannot share differing family field: {shared}")
            family[shared] = convert(values[0])
        selections = []
        for raw in sorted(members, key=lambda p: p["profile_index"]):
            value = convert(raw)
            paths = [{
                "actor": p["player_id"], "group": p["responsibility_group"],
                "kind": p["path_kind"], "start": p["start"], "control": p["control"],
                "end": p["end"], "line_style": p["line_style"],
            } for p in value["individual_assignment_paths"]]
            if len(paths) != 11 or len({p["actor"] for p in paths}) != 11:
                raise ValueError("a play must retain eleven distinct position paths")
            if any(type(x) is not int for p in paths for point in ("start", "control", "end") for x in p[point]):
                raise ValueError("source path coordinates must remain exact integers")
            path_count += len(paths)
            links = []
            for old_link in value["sequence_links"]:
                link = {k: v for k, v in old_link.items() if k != "target_selection_id"}
                link["target"] = old_link["target_selection_id"]
                links.append(link)
            selection = {
                "id": value["selection_id"], "name": value["name"],
                "family_id": value["family_id"], "profile": value["orchestration_profile"],
                "profile_index": value["profile_index"], "side": value["side"],
                "formation_id": value["formation_id"], "intent": value["intent"],
                "paths": paths, "read_rules": value["ordered_read_rules"],
                "source_decision": value["source_decision"], "roles": value["roles"],
                "interaction_surfaces": value["interaction_surfaces"],
                "sequence_links": links, "coverage_treatment": value["coverage_treatment"],
                "situations": value["situations"], "constraints": value["constraints"],
                "play_syntax": value["play_syntax"],
                "source": source_record(raw["source"], raw["selection_id"], convert),
            }
            if selection["id"] in selection_index:
                raise ValueError("identity migration would merge selection identifiers")
            selection_index[selection["id"]] = file
            selections.append(selection)
        family_index[family["family_id"]] = file
        files[file] = encode({"family": family, "selections": selections})

    for side in ("OFFENSE", "DEFENSE"):
        formations = [f for f in raw_formations if f["side"] == side]
        for start in range(0, len(formations), 12):
            file = f"formations/{side.lower()}-{start // 12 + 1:02d}.json"
            records = []
            for raw in formations[start:start + 12]:
                value = convert(raw)
                records.append({
                    "id": value["formation_id"], "name": value["name"], "side": value["side"],
                    "composition": value["composition"], "lifecycle": value["lifecycle"],
                    "roles": value["roles"], "physics_algorithms": value["physics_algorithms"],
                    "glyphs": [{"actor": g["player_id"], "group": g["group"], "shape": g["shape"],
                                "attributes": g["shape_attributes"]} for g in value["schematic_glyphs"]],
                    "source": source_record(raw["source"], raw["formation_id"], convert),
                })
                if value["formation_id"] in formation_index:
                    raise ValueError("identity migration would merge formation identifiers")
                formation_index[value["formation_id"]] = file
            files[file] = encode({"formations": records})

    if path_count != 11880:
        raise ValueError("assignment path coverage mismatch")
    for raw in raw_plays:
        if convert(raw["formation_id"]) not in formation_index:
            raise ValueError("selection references an unknown formation")
        if any(convert(link["target_selection_id"]) not in selection_index for link in raw["sequence_links"]):
            raise ValueError("sequence link references an unknown selection")

    files["profiles.json"] = encode({
        "variants": [{"id": side.lower() + ":" + convert(p["profile"]), "side": side,
                      "profile": convert(p["profile"]), "index": p["profile_index"],
                      "selection_count": p["selection_count"]}
                     for side in ("OFFENSE", "DEFENSE") for p in profiles[side]],
        "system_media": convert(audit["summary.json"]["system_media"]),
        "coach_program_profile": "SEPARATE_VERSIONED_READ_ONLY_COMPARISON; NEVER_TRAINING_INPUT",
    }, pretty=True)
    fieldbook = audit["summary.json"]["fieldbook"]
    files["fieldbook.json"] = encode({
        "source_pdf_display_label": convert(fieldbook["pdf"]),
        "source_pdf_sha256": fieldbook["sha256"], "source_pdf_label_migrated": True,
        "source_page_count": fieldbook["page_count"],
        "source_selection_method_display": convert(fieldbook["sampling_method"]),
        "source_selection_method_original_sha256": digest(fieldbook["sampling_method"].encode("utf-8")),
        "selections": [{**{k: convert(v) for k, v in p.items() if k != "selection_id"},
                        "id": convert(p["selection_id"])} for p in fieldbook["plays"]],
    }, pretty=True)
    source_members = audit["archive-provenance.json"]
    archive_ids = {
        row["archive_sha256"]: ("reference-implementation-0.10.0" if "Reference-Implementation" in row["archive"]
                                else "lecanto-atlas-0.9.0" if "Lecanto-Atlas" in row["archive"] else "playbook-atlas")
        for row in source_members
    }
    files["provenance.json"] = encode({
        "schema": "MJ-Playbook-Provenance/0.1.0",
        "original_byte_hashes_retained": True,
        "display_labels_migrated": True,
        "migration": {"historical_product_label_sha256": digest(label.lower().encode("utf-8")),
                      "current_product_label": "Bangel", "case_preserved": True,
                      "source_digests_describe_original_bytes": True,
                      "normalized_records_use_index_shard_digests": True},
        "archives": [{"id": archive_ids[key], "sha256": key,
                      "display_label": convert(next(row["archive"] for row in source_members if row["archive_sha256"] == key))}
                     for key in sorted(archive_ids)],
        "members": [{"archive": archive_ids[row["archive_sha256"]],
                     "member_display_label": convert(row["member"]),
                     "member_sha256": row["member_sha256"], "member_bytes": row["member_bytes"]}
                    for row in source_members],
        "audit_inputs_sha256": AUDIT_SHA256,
        "source_integrity_checks": convert(audit["summary.json"]["integrity_checks"]),
    }, pretty=True)
    files["geometry-collisions.json"] = encode({
        "signature_basis": "Original actor, kind, start, control, end and line style; schematic canvas units",
        "groups": convert(audit["geometry-collisions.json"]),
        "match_rule": "GEOMETRY_EQUALITY_DOES_NOT_ESTABLISH_IDENTITY",
    }, pretty=True)
    files["coverage.json"] = encode({
        "counts": {**audit["summary.json"]["counts"], "profile_variants": 20,
                   "distinct_profile_labels": 19, "fieldbook_selections": 20,
                   "formation_glyphs": 3960},
        "path_kind_counts": audit["summary.json"]["path_kind_counts"],
        "interaction_surface_counts": audit["summary.json"]["interaction_surface_counts"],
        "limitations": [
            "Coordinates are original schematic SVG canvas units, not observed positions or calibrated field yards.",
            "The 1080 plays contain 146 distinct full geometries. Preserve ambiguous candidates and independent context.",
            "Physics equations are original reference strings; they are not automatically executable or validated recall functions.",
            "The offense arrival equation t_ball - t_defender and its positive-before prose disagree in sign; do not infer physical timing from that prose.",
            "A role group and a position actor are separate source fields; coarse source role assignment does not establish player identity.",
            "A0-A4 are playbook lifecycle stages; historical R labels are namespaced playbook metadata, not Bangel/JP runtime-state definitions.",
            "No original playbook source defines an N1-N9 embedding, command association, or calibrated recall probability. Those require a versioned MJ mapping.",
            "Coach Program Profiles and Game Plans cannot train or mutate the model; immutable film is not direct training input.",
            "First observation is WATCH_ITEM_ONLY. Trusted retention requires 30 compatible classified observations and qualified independent review.",
            "Visual acquisition tuning may change bounded rendering parameters only, never play logic or the source assignment coordinates.",
            "Signed prediction residual is not a nonnegative statistical variance; preserve that type distinction in native computation.",
        ],
    }, pretty=True)

    if any(len(value) >= 100_000 for name, value in files.items() if name.startswith(("families/", "formations/"))):
        raise ValueError("catalog data shard exceeds the 100000-byte review bound")
    index = {
        "schema": SCHEMA, "version": "0.1.0", "frame": FRAME,
        "coordinate_kind": "ORIGINAL_SVG_SCHEMATIC_CANVAS_UNITS",
        "axis": {"x": "RIGHT", "y": "DOWN"},
        "formation_coordinate_encoding": "ORIGINAL_SVG_CIRCLE_CX_CY_OR_TRIANGLE_POINTS",
        "path_encoding": "QUADRATIC_BEZIER_START_CONTROL_END",
        "selections": selection_index, "families": family_index, "formations": formation_index,
        "metadata": {key: key + ".json" for key in
                     ("profiles", "fieldbook", "provenance", "geometry-collisions", "coverage")},
        "shard_sha256": {name: digest(raw) for name, raw in sorted(files.items())},
    }
    files["index.json"] = encode(index, pretty=True)
    token = label.lower().encode("utf-8")
    if any(token in path.lower().encode("utf-8") or token in raw.lower() for path, raw in files.items()):
        raise ValueError("historical product spelling remains in generated catalog")
    return files


def save(files: dict[str, bytes], destination: Path, *, check: bool) -> None:
    existing = {str(path.relative_to(destination)): path for path in destination.rglob("*") if path.is_file()}
    if check or existing:
        if set(existing) != set(files) or any(existing[name].read_bytes() != raw for name, raw in files.items()):
            raise ValueError("catalog differs from deterministic import; use a fresh output directory")
        return
    destination.mkdir(parents=True, exist_ok=True)
    for name, raw in sorted(files.items()):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", "--input-dir", type=Path, required=True)
    parser.add_argument("--historical-product-label", required=True)
    parser.add_argument("--output-dir", "--output", type=Path,
                        default=Path(__file__).resolve().parents[1] / "src/mj_memory_recall/data")
    parser.add_argument("--check", action="store_true", help="verify exact reproducibility without writing")
    args = parser.parse_args()
    try:
        files = package(load_audit(args.audit_dir), args.historical_product_label)
        save(files, args.output_dir, check=args.check)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"playbook import failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"schema": SCHEMA, "status": "VERIFIED" if args.check else "PACKAGED",
                      "files": len(files), "selections": 1080, "paths": 11880,
                      "largest_family_shard_bytes": max(len(raw) for name, raw in files.items() if name.startswith("families/"))}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
