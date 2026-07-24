"""CLI entry point — argparse wiring lives in run.py."""
from __future__ import annotations

import sys


def main() -> int:
    print("tools.seed_finance CLI not yet implemented", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
