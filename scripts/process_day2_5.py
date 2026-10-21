"""Safely enrich the processed catalog and import it into SQLite."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.enrich_processed_datasets import prepare_processed_datasets
from scripts.populate_db_day2_5 import populate_db_idempotent
from scripts.audit_data_quality import generate_report


def run_pipeline() -> dict:
    enrichment = prepare_processed_datasets(apply=True)
    database = populate_db_idempotent()
    report = generate_report()
    return {
        "enrichment": enrichment,
        "database": database,
        "coverage_report": str(report),
    }


if __name__ == "__main__":
    print(json.dumps(run_pipeline(), ensure_ascii=True, indent=2))
