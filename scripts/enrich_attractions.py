"""Compatibility entry point for the offline, provenance-aware catalog enrichment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.enrich_processed_datasets import prepare_processed_datasets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the processed CSVs; without this flag, only report planned changes",
    )
    args = parser.parse_args()
    print(json.dumps(
        prepare_processed_datasets(apply=args.apply),
        ensure_ascii=True,
        indent=2,
    ))


if __name__ == "__main__":
    main()
