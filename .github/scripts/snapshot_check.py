#!/usr/bin/env python3
"""
RogueTech JSON regression snapshot (T1B).

Captures file counts bucketed two ways:

  - By filename prefix (everything before the first `_`, e.g. `mechdef`,
    `chassisdef`, `weapondef`). Catches drops across whole def types.
  - By directory relative to repo root. Catches drops of one-off files with
    no shared prefix (e.g. `Core/DynamicShops/fshops/Periphery.json` —
    the W7A regression class).

Both views run on every check. A drop in either view fails CI. The baseline
lives at `.github/regression-baseline.json` and is regenerated with
`--update`. Increases never fail; they're reported as INFO so legitimate
upstream additions don't break the build.

This is a CI-time check, not a runtime data validator. It assumes
validate_json.py / check_refs.py / check_schema.py already passed.

Usage:
    python snapshot_check.py                    # diff current vs. baseline
    python snapshot_check.py --update           # regenerate baseline
    python snapshot_check.py --root <path>      # override repo root
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Iterator

REPO_ROOT_DEFAULT = Path(__file__).resolve().parent.parent.parent
BASELINE_PATH_DEFAULT = REPO_ROOT_DEFAULT / ".github" / "regression-baseline.json"

# Directories we walk but don't aggregate — patches/tags/transients churn legitimately.
SKIP_DIR_NAMES = {"advancedjsonmerge", "tags"}
# Top-level entries we never descend into.
SKIP_TOPLEVEL = {".git", ".github"}


def iter_json_files(root: Path) -> Iterator[Path]:
    """Yield every .json file under root, excluding skip lists."""
    for path in root.rglob("*.json"):
        rel_parts = path.relative_to(root).parts
        if rel_parts and rel_parts[0] in SKIP_TOPLEVEL:
            continue
        if any(part in SKIP_DIR_NAMES for part in rel_parts):
            continue
        if any(part.startswith(".") for part in rel_parts):
            continue
        yield path


def collect(root: Path) -> dict:
    files_by_type: Counter[str] = Counter()
    files_by_dir: Counter[str] = Counter()
    total = 0

    for path in iter_json_files(root):
        total += 1
        stem = path.stem
        prefix = stem.split("_", 1)[0] if "_" in stem else stem
        files_by_type[prefix] += 1
        rel_parent = path.parent.relative_to(root).as_posix() or "."
        files_by_dir[rel_parent] += 1

    return {
        "version": 1,
        "total_files": total,
        "files_by_type": dict(sorted(files_by_type.items())),
        "files_by_dir": dict(sorted(files_by_dir.items())),
    }


def diff_counter(
    label: str,
    baseline: dict[str, int],
    current: dict[str, int],
) -> tuple[list[str], list[str]]:
    """Return (failures, info) lines for one view."""
    failures: list[str] = []
    info: list[str] = []

    # Keys present in baseline but missing or reduced in current
    for key, b_count in baseline.items():
        c_count = current.get(key, 0)
        if c_count < b_count:
            delta = c_count - b_count
            failures.append(f"  {label}: {key}: {b_count} → {c_count} ({delta:+d})")

    # Keys present in current but not in baseline → INFO (additions)
    new_keys = sorted(set(current) - set(baseline))
    for key in new_keys:
        info.append(f"  {label}: {key}: 0 → {current[key]} (+{current[key]})")

    # Keys with increases
    for key in sorted(set(baseline) & set(current)):
        if current[key] > baseline[key]:
            delta = current[key] - baseline[key]
            info.append(f"  {label}: {key}: {baseline[key]} → {current[key]} (+{delta})")

    return failures, info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--update", action="store_true",
                        help="Regenerate the baseline from current state")
    parser.add_argument("--root", type=Path, default=REPO_ROOT_DEFAULT,
                        help="RogueTech repo root (default: script location)")
    parser.add_argument("--baseline", type=Path, default=None,
                        help="Baseline JSON path (default: <root>/.github/regression-baseline.json)")
    args = parser.parse_args()

    root: Path = args.root.resolve()
    baseline_path: Path = (args.baseline or (root / ".github" / "regression-baseline.json")).resolve()

    current = collect(root)

    if args.update:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        with baseline_path.open("w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, sort_keys=True)
            f.write("\n")
        print(f"OK — baseline written: {baseline_path.relative_to(root)} "
              f"({current['total_files']} files, "
              f"{len(current['files_by_type'])} type buckets, "
              f"{len(current['files_by_dir'])} dir buckets)")
        return 0

    if not baseline_path.exists():
        print(f"ERROR: baseline not found at {baseline_path}")
        print(f"       Run: python {Path(__file__).name} --update")
        return 1

    with baseline_path.open(encoding="utf-8") as f:
        baseline = json.load(f)

    failures: list[str] = []
    info: list[str] = []

    if current["total_files"] < baseline["total_files"]:
        failures.append(
            f"  TOTAL: {baseline['total_files']} → {current['total_files']} "
            f"({current['total_files'] - baseline['total_files']:+d})"
        )
    elif current["total_files"] > baseline["total_files"]:
        info.append(
            f"  TOTAL: {baseline['total_files']} → {current['total_files']} "
            f"(+{current['total_files'] - baseline['total_files']})"
        )

    f1, i1 = diff_counter("type", baseline.get("files_by_type", {}), current["files_by_type"])
    f2, i2 = diff_counter("dir ", baseline.get("files_by_dir", {}), current["files_by_dir"])
    failures.extend(f1)
    failures.extend(f2)
    info.extend(i1)
    info.extend(i2)

    if info:
        print(f"INFO ({len(info)} additions vs. baseline):")
        for line in info:
            print(line)
        print()

    if failures:
        print(f"ERROR: {len(failures)} bucket(s) show file count decrease vs. baseline:")
        for line in failures:
            print(line)
        print()
        print("Likely a silent file deletion during rebase. Inspect with `git status` or")
        print("`git log` to find what dropped. If intentional, regenerate the baseline:")
        print(f"  python {Path(__file__).name} --update")
        return 1

    print(f"OK — {current['total_files']} files; "
          f"{len(current['files_by_type'])} type buckets, "
          f"{len(current['files_by_dir'])} dir buckets unchanged or grown vs. baseline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
