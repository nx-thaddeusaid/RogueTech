#!/usr/bin/env python3
"""
Profile validate_json.py and print the top-20 cumulative-time entries.

Usage:
    python .github/scripts/profile_validator.py
    python .github/scripts/profile_validator.py --output validator.prof  # save raw profile
"""
import argparse
import cProfile
import io
import pstats
import runpy
import sys
from pathlib import Path

SCRIPT = str(Path(__file__).parent / "validate_json.py")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Path to write raw .prof file (optional)")
    args = parser.parse_args()

    pr = cProfile.Profile()
    pr.enable()
    try:
        runpy.run_path(SCRIPT, run_name="__main__")
    except SystemExit:
        pass
    finally:
        pr.disable()

    if args.output:
        pr.dump_stats(args.output)
        print(f"Profile written to {args.output}")

    stream = io.StringIO()
    ps = pstats.Stats(pr, stream=stream).sort_stats(pstats.SortKey.CUMULATIVE)
    ps.print_stats(20)
    print(stream.getvalue())


if __name__ == "__main__":
    main()
