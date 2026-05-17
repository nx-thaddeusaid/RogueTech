#!/usr/bin/env python3
"""
Schema depth validation for RogueTech JSON data files.

Checks field presence, types, and value ranges for the highest-volume def types.
Syntax errors are caught by validate_json.py; this script assumes files are valid JSON.

Exit code 0 = clean, non-zero = failures found.
"""

import json
import sys
from pathlib import Path

root = Path(__file__).parent.parent.parent
failures: list[str] = []


def fail(path: Path, msg: str) -> None:
    failures.append(f"{path.relative_to(root)}: {msg}")


def load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None  # syntax errors caught by validate_json.py


# ── mechdef_* ─────────────────────────────────────────────────────────────────

def check_mechdef(path: Path, d: dict) -> None:
    chassis_id = d.get("ChassisID")
    if not chassis_id or not isinstance(chassis_id, str):
        fail(path, "ChassisID missing or not a string")

    locs = d.get("Locations")
    if not isinstance(locs, list) or len(locs) == 0:
        fail(path, "Locations missing or empty")

    inv = d.get("inventory")
    if not isinstance(inv, list):
        fail(path, "inventory missing or not an array")


# ── chassisdef_* ──────────────────────────────────────────────────────────────

def check_chassisdef(path: Path, d: dict) -> None:
    tonnage = d.get("Tonnage")
    if not isinstance(tonnage, (int, float)):
        fail(path, "Tonnage missing or not a number")
    elif tonnage <= 0:
        fail(path, f"Tonnage must be positive: {tonnage}")

    locs = d.get("Locations")
    if not isinstance(locs, list) or len(locs) != 8:
        fail(path, f"Locations must be an array of exactly 8 entries, got {len(locs) if isinstance(locs, list) else type(locs).__name__}")


# ── vehicledef_* ──────────────────────────────────────────────────────────────

def check_vehicledef(path: Path, d: dict) -> None:
    chassis_id = d.get("ChassisID")
    if not chassis_id or not isinstance(chassis_id, str):
        fail(path, "ChassisID missing or not a string")


# ── vehiclechassisdef_* ───────────────────────────────────────────────────────

def check_vehiclechassisdef(path: Path, d: dict) -> None:
    tonnage = d.get("Tonnage")
    if not isinstance(tonnage, (int, float)):
        fail(path, "Tonnage missing or not a number")
    elif tonnage <= 0:
        fail(path, f"Tonnage must be positive: {tonnage}")

    locs = d.get("Locations")
    if not isinstance(locs, list) or len(locs) == 0:
        fail(path, "Locations missing or empty")


# ── Weapon_* ──────────────────────────────────────────────────────────────────

def check_weapon(path: Path, d: dict) -> None:
    min_range = d.get("MinRange")
    max_range = d.get("MaxRange")
    if isinstance(min_range, (int, float)) and isinstance(max_range, (int, float)):
        if min_range > max_range:
            fail(path, f"MinRange ({min_range}) > MaxRange ({max_range})")

    damage = d.get("Damage")
    if damage is not None and isinstance(damage, (int, float)) and damage < 0:
        fail(path, f"Damage is negative: {damage}")


# ── dispatch ──────────────────────────────────────────────────────────────────

CHECKS = {
    "mechdef_": check_mechdef,
    "chassisdef_": check_chassisdef,
    "vehicledef_": check_vehicledef,
    "vehiclechassisdef_": check_vehiclechassisdef,
    "Weapon_": check_weapon,
    "weapon_": check_weapon,
}

checked = 0
skipped = 0

for path in root.rglob("*.json"):
    # skip hidden directories and AdvancedJSONMerge patches
    if any(part.startswith(".") for part in path.parts):
        continue
    if "advancedjsonmerge" in str(path).lower():
        continue

    stem = path.stem
    checker = None
    for prefix, fn in CHECKS.items():
        if stem.startswith(prefix):
            checker = fn
            break

    if checker is None:
        skipped += 1
        continue

    d = load(path)
    if d is None or not isinstance(d, dict):
        skipped += 1
        continue

    checker(path, d)
    checked += 1

if failures:
    for f in failures:
        print(f"FAIL: {f}")
    print(f"\n{len(failures)} failure(s) in {checked} checked files ({skipped} skipped)")
    sys.exit(1)

print(f"OK — {checked} files passed schema checks ({skipped} skipped)")
