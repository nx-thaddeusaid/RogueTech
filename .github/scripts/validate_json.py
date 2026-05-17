#!/usr/bin/env python3
"""
Validates all JSON files in the RogueTech repo:
  - Syntax validity
  - Per-object duplicate key detection
  - Required fields per BattleTech def type (keyed by filename prefix)
  - Description.Id uniqueness per def type
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent

REQUIRED_FIELDS = {
    "mechdef_":              ["Description", "ChassisID", "inventory"],
    "chassisdef_":           ["Description", "HardpointDataDefID", "Locations"],
    "vehicledef_":           ["Description", "ChassisID", "inventory"],
    "vehiclechassisdef_":    ["Description", "HardpointDataDefID", "Locations"],
    "starsystemdef_":        ["Description", "StarType"],
    "lancedef_":             ["Description", "LanceUnits"],
    "pilot_":                ["Description", "BasePiloting", "BaseGunnery"],
    "event_":                ["Description", "EventType", "Options"],
    "turretdef_":            ["Description", "ChassisID"],
    "turretchassisdef_":     ["Description", "HardpointDataDefID"],
}

SKIP_DIRS = {"advancedjsonmerge", "tags"}


def _check_pairs(pairs):
    keys = [k for k, _ in pairs]
    seen = set()
    for k in keys:
        if k in seen:
            return None, f"duplicate key '{k}'"
        seen.add(k)
    return dict(pairs), None


def _validate_one(args):
    """
    Validate a single JSON file. Called in a worker process.
    Returns (rel_str, file_errors, prefix_matched, description_id).
    """
    path_str, root_str = args
    path = Path(path_str)
    root = Path(root_str)
    rel = path.relative_to(root)
    rel_str = str(rel)

    file_errors: list[str] = []
    prefix_matched: str | None = None
    description_id: str | None = None

    # Load JSON with duplicate-key detection.
    try:
        text = path.read_text(encoding="utf-8-sig")
        errors_inner: list[str] = []

        def hook(pairs):
            obj, err = _check_pairs(pairs)
            if err:
                errors_inner.append(err)
                return dict(pairs)
            return obj

        data = json.loads(text, object_pairs_hook=hook)
        file_errors.extend(errors_inner)
    except json.JSONDecodeError as e:
        return rel_str, [str(e)], None, None
    except OSError as e:
        return rel_str, [str(e)], None, None

    if not isinstance(data, dict):
        return rel_str, file_errors, None, None

    name = path.name

    # Required fields + Description.Id collection.
    for prefix, fields in REQUIRED_FIELDS.items():
        if name.startswith(prefix):
            prefix_matched = prefix
            missing = [f for f in fields if f not in data]
            if missing:
                file_errors.append(f"missing required fields: {missing}")

            if "advancedjsonmerge" not in rel_str:
                desc = data.get("Description")
                if isinstance(desc, dict):
                    did = desc.get("Id")
                    if did:
                        description_id = did
            break

    # mod.json: require Name if manifest keys present.
    if name == "mod.json":
        if any(k in data for k in ("Manifest", "AdvancedJSONMerge")):
            if "Name" not in data:
                file_errors.append("mod.json missing 'Name'")

    return rel_str, file_errors, prefix_matched, description_id


def main():
    # Collect paths to validate (filter before farming out to workers).
    paths = []
    for f in sorted(ROOT.rglob("*.json")):
        parts = f.parts
        if any(p.startswith(".") for p in parts):
            continue
        if any(p in SKIP_DIRS for p in parts):
            continue
        paths.append(str(f))

    root_str = str(ROOT)
    errors_by_file: dict[str, list[str]] = {}
    # id_map: prefix -> {description_id -> first_rel_path} — requires sequential dedup.
    id_map: dict[str, dict[str, str]] = {}

    workers = max(1, min(os.cpu_count() or 1, 8))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_validate_one, (p, root_str)): p
            for p in paths
        }
        for future in as_completed(futures):
            rel_str, file_errors, prefix_matched, description_id = future.result()

            if file_errors:
                errors_by_file[rel_str] = file_errors

            # Description.Id uniqueness: sequential, but just dict lookups.
            if prefix_matched and description_id:
                bucket = id_map.setdefault(prefix_matched, {})
                if description_id in bucket:
                    errors_by_file.setdefault(rel_str, []).append(
                        f"duplicate Description.Id '{description_id}' "
                        f"(first seen in {bucket[description_id]})"
                    )
                else:
                    bucket[description_id] = rel_str

    total = len(paths)
    if errors_by_file:
        for path, errs in sorted(errors_by_file.items()):
            for e in errs:
                print(f"ERROR {path}: {e}", file=sys.stderr)
        print(
            f"\n{len(errors_by_file)} file(s) with errors out of {total} checked.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {total} JSON files validated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
