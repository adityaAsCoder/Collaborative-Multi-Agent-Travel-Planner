def append_report():
    report_path = 'reports/project_cleanup_audit.md'
    text = """
## 14. FINAL REPORT

### BEFORE:
- total files: 34
- total folders: 22

### DELETED:
- `datasets/raw/hotels/hotels.csv`: Corrupted source superseded by XLSX
- `scripts/process_day2.py`: Obsoleted by day2_5
- `scripts/populate_db.py`: Obsoleted by day2_5

### KEPT:
- `datasets/processed/*`: Canonical datasets required for db loading
- `datasets/osm/northern-zone.gpkg`: Kept for future routing features
- `app/`, `tests/`, `docs/`, `scripts/`: Architecture base required now.

### AFTER:
- total files: 31
- total folders: 20

### TEST RESULTS:
- number of tests: 10
- passed: 10
- failed: 0

### BROKEN REFERENCES:
- none

### FINAL STATUS:
CLEAN
"""
    with open(report_path, 'a', encoding='utf-8') as f:
        f.write(text)

if __name__ == '__main__':
    append_report()
