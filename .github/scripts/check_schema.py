#!/usr/bin/env python3
"""
Schema depth validation for RogueTech JSON data files.

Checks field presence, types, and value ranges for the highest-volume def types.
Syntax errors are caught by validate_json.py; this script assumes files are valid JSON.

Exit code 0 = clean, non-zero = failures found.
"""

import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

root = Path(__file__).parent.parent.parent


def _load_known_owner_ids() -> frozenset[str]:
    ids = set()
    for p in root.rglob("faction_*.json"):
        if any(part.startswith(".") for part in p.parts):
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8-sig"))
            fid = d.get("ID", "")
            if fid.startswith("faction_"):
                ids.add(fid[len("faction_"):])
        except Exception:
            pass
    return frozenset(ids)


KNOWN_OWNER_IDS: frozenset[str] = _load_known_owner_ids()


# ── per-type checkers ─────────────────────────────────────────────────────────

def _check_mechdef(d: dict) -> list[str]:
    errs = []
    chassis_id = d.get("ChassisID")
    if not chassis_id or not isinstance(chassis_id, str):
        errs.append("ChassisID missing or not a string")
    locs = d.get("Locations")
    if not isinstance(locs, list) or len(locs) == 0:
        errs.append("Locations missing or empty")
    inv = d.get("inventory")
    if not isinstance(inv, list):
        errs.append("inventory missing or not an array")
    return errs


def _check_chassisdef(d: dict) -> list[str]:
    errs = []
    tonnage = d.get("Tonnage")
    if not isinstance(tonnage, (int, float)):
        errs.append("Tonnage missing or not a number")
    elif tonnage <= 0:
        errs.append(f"Tonnage must be positive: {tonnage}")
    locs = d.get("Locations")
    n = len(locs) if isinstance(locs, list) else None
    if n != 8:
        errs.append(
            f"Locations must be an array of exactly 8 entries, "
            f"got {n if n is not None else type(locs).__name__}"
        )
    return errs


def _check_vehicledef(d: dict) -> list[str]:
    chassis_id = d.get("ChassisID")
    if not chassis_id or not isinstance(chassis_id, str):
        return ["ChassisID missing or not a string"]
    return []


def _check_vehiclechassisdef(d: dict) -> list[str]:
    errs = []
    tonnage = d.get("Tonnage")
    if not isinstance(tonnage, (int, float)):
        errs.append("Tonnage missing or not a number")
    elif tonnage <= 0:
        errs.append(f"Tonnage must be positive: {tonnage}")
    locs = d.get("Locations")
    n = len(locs) if isinstance(locs, list) else None
    if n not in (4, 5):
        errs.append(
            f"Locations must be an array of 4 or 5 entries (vehicles), "
            f"got {n if n is not None else type(locs).__name__}"
        )
    return errs


def _check_weapon(d: dict) -> list[str]:
    errs = []
    min_range = d.get("MinRange")
    max_range = d.get("MaxRange")
    if isinstance(min_range, (int, float)) and isinstance(max_range, (int, float)):
        if min_range > max_range:
            errs.append(f"MinRange ({min_range}) > MaxRange ({max_range})")
    damage = d.get("Damage")
    if damage is not None and isinstance(damage, (int, float)) and damage < 0:
        errs.append(f"Damage is negative: {damage}")
    heat = d.get("HeatGenerated")
    if heat is not None and isinstance(heat, (int, float)) and heat < 0:
        errs.append(f"HeatGenerated is negative: {heat}")
    return errs


def _check_starsystemdef(d: dict) -> list[str]:
    owner = d.get("ownerID")
    if owner and owner not in KNOWN_OWNER_IDS:
        return [f"ownerID '{owner}' not in known faction list"]
    return []


CHECKS = {
    "mechdef_": _check_mechdef,
    "chassisdef_": _check_chassisdef,
    "vehicledef_": _check_vehicledef,
    "vehiclechassisdef_": _check_vehiclechassisdef,
    "starsystemdef_": _check_starsystemdef,
    "Weapon_": _check_weapon,
    "weapon_": _check_weapon,
}


# ── worker ────────────────────────────────────────────────────────────────────

def _check_one(args) -> tuple[str | None, list[str]]:
    """
    Called in a worker process. Returns (rel_path_str, errors).
    rel_path_str is None when the file is skipped.
    """
    path_str, root_str = args
    path = Path(path_str)
    root = Path(root_str)

    stem = path.stem
    checker = None
    for prefix, fn in CHECKS.items():
        if stem.startswith(prefix):
            checker = fn
            break
    if checker is None:
        return None, []

    try:
        d = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None, []  # syntax errors caught by validate_json.py

    if not isinstance(d, dict):
        return None, []

    errs = checker(d)
    if errs:
        rel = str(path.relative_to(root))
        return rel, errs
    return path_str, []  # non-None signals "was checked"


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    root_str = str(root)

    paths = []
    for path in root.rglob("*.json"):
        if any(part.startswith(".") for part in path.parts):
            continue
        if "advancedjsonmerge" in str(path).lower():
            continue
        paths.append(str(path))

    failures: list[str] = []
    checked = 0
    skipped = 0

    workers = max(1, min(os.cpu_count() or 1, 8))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_check_one, (p, root_str)) for p in paths]
        for future in as_completed(futures):
            rel, errs = future.result()
            if rel is None:
                skipped += 1
            else:
                checked += 1
                for e in errs:
                    failures.append(f"{rel}: {e}")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        print(f"\n{len(failures)} failure(s) in {checked} checked files ({skipped} skipped)")
        sys.exit(1)

    print(f"OK — {checked} files passed schema checks ({skipped} skipped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
