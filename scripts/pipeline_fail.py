"""Print a consistent, easy-to-spot pipeline failure message."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a clear pipeline failure summary.")
    parser.add_argument("--stage", required=True, help="Stage label, e.g. 'Stage 1'")
    parser.add_argument("--reason", required=True, help="Short failure reason")
    parser.add_argument("--details-file", help="Optional file whose contents are printed")
    parser.add_argument("--hint", action="append", default=[], help="Remediation hint line")
    args = parser.parse_args()

    title = f"{args.stage} FAILED"
    print(f"::error title={title}::{args.reason}")
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)
    print(f"Reason: {args.reason}")
    print()

    if args.details_file:
        details_path = Path(args.details_file)
        if details_path.exists():
            print("Details:")
            print("-" * 72)
            print(details_path.read_text(encoding="utf-8", errors="replace")[:8000])
            print("-" * 72)
            print()

    if args.hint:
        print("How to fix:")
        for line in args.hint:
            print(f"  - {line}")
        print()

    print("=" * 72)
    return 1


if __name__ == "__main__":
    sys.exit(main())
