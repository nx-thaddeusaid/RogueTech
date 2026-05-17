#!/usr/bin/env python3
"""
Item 12 cross-reference check: RogueTech chassisdef/vehiclechassisdef HardpointDataDefID
values must resolve to a hardpointdatadef_*.json file in at least one of the 12 CAB repos
or in RogueTech's own data.

Usage:
    python check_cab_refs.py <rt_path> [<cab_path1> <cab_path2> ...]

Exits 0 if no new missing references are found. Exits 1 if any HardpointDataDefID is
referenced in RT but not present in any known source AND not in the known-missing allowlist.

The allowlist (hardpoints_known_missing.txt) covers IDs that live in HBS Unity asset bundles
and therefore cannot be verified without a game install. Remove entries from the allowlist
as CAB contributors add the corresponding hardpointdatadef files.
"""

import json
import pathlib
import sys
import collections

SCRIPT_DIR = pathlib.Path(__file__).parent
ALLOWLIST_FILE = SCRIPT_DIR / "hardpoints_known_missing.txt"


def collect_cab_ids(paths):
    ids = set()
    for base in paths:
        for p in pathlib.Path(base).rglob("*.json"):
            if p.name.lower().startswith("hardpointdatadef_"):
                ids.add(p.stem.lower())
    return ids


def collect_rt_refs(rt_path):
    refs = collections.Counter()
    ref_sources = collections.defaultdict(list)
    rt = pathlib.Path(rt_path)
    for p in rt.rglob("*.json"):
        if not (p.name.startswith("chassisdef_") or p.name.startswith("vehiclechassisdef_")):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        val = data.get("HardpointDataDefID")
        if val:
            key = val.lower()
            refs[key] += 1
            ref_sources[key].append(p.name)
    return refs, ref_sources


def load_allowlist():
    if not ALLOWLIST_FILE.exists():
        return set()
    return {line.strip().lower() for line in ALLOWLIST_FILE.read_text().splitlines() if line.strip()}


def main():
    if len(sys.argv) < 2:
        print("Usage: check_cab_refs.py <rt_path> [<cab_path1> ...]", file=sys.stderr)
        sys.exit(2)

    rt_path = sys.argv[1]
    cab_paths = sys.argv[2:]

    all_paths = [rt_path] + cab_paths
    known = collect_cab_ids(all_paths)
    refs, ref_sources = collect_rt_refs(rt_path)
    allowlist = load_allowlist()

    new_missing = []
    allowed_missing = []
    now_found = []

    for ref, count in sorted(refs.items()):
        if ref in known:
            if ref in allowlist:
                now_found.append((ref, count))
        else:
            if ref in allowlist:
                allowed_missing.append((ref, count))
            else:
                new_missing.append((ref, count, ref_sources[ref]))

    if now_found:
        print(f"INFO: {len(now_found)} ID(s) now found in CABs — remove from allowlist:")
        for ref, count in now_found:
            print(f"  {ref}  ({count} refs)")
        print()

    if allowed_missing:
        print(f"OK: {len(allowed_missing)} known-missing ID(s) (vanilla HBS assets or pending CAB addition):")
        for ref, count in allowed_missing:
            print(f"  {ref}  ({count} refs)")
        print()

    if new_missing:
        print(f"ERROR: {len(new_missing)} NEW missing HardpointDataDefID(s) not in any CAB or allowlist:")
        for ref, count, sources in new_missing:
            sample = sources[:3]
            extra = f" +{len(sources)-3} more" if len(sources) > 3 else ""
            print(f"  {ref}  ({count} refs: {', '.join(sample)}{extra})")
        print()
        print("Fix: add the hardpointdatadef file to the appropriate CAB repo,")
        print("or add the ID to .github/scripts/hardpoints_known_missing.txt if it is a vanilla asset.")
        sys.exit(1)

    total = len(refs)
    found = total - len(allowed_missing)
    print(f"OK — {found}/{total} unique HardpointDataDefIDs resolved across CABs; {len(allowed_missing)} known-missing (allowlisted).")


if __name__ == "__main__":
    main()
