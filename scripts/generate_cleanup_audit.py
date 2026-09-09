import os
import shutil
import time
from pathlib import Path

def generate_inventory():
    root = Path('d:/Collaborative-Multi-Agent-Travel-Planner')
    inventory = []
    
    for filepath in root.rglob('*'):
        if '.git' in filepath.parts or 'venv' in filepath.parts:
            continue
            
        is_dir = filepath.is_dir()
        size = 0 if is_dir else filepath.stat().st_size
        inventory.append({
            'path': str(filepath.relative_to(root)).replace('\\', '/'),
            'is_dir': is_dir,
            'size': size
        })
        
    return sorted(inventory, key=lambda x: x['path'])

def classify_files(inventory):
    classified = {
        'A. REQUIRED NOW': [],
        'B. REQUIRED FOR FUTURE': [],
        'C. GENERATED BUT REPRODUCIBLE': [],
        'D. DUPLICATE': [],
        'E. TEMPORARY/CACHE': [],
        'F. OBSOLETE': [],
        'G. UNCERTAIN': []
    }
    
    for item in inventory:
        p = item['path']
        if item['is_dir']: continue
        
        if '__pycache__' in p or '.pytest_cache' in p or p.endswith('.pyc'):
            classified['E. TEMPORARY/CACHE'].append(item)
        elif p == 'datasets/raw/hotels/hotels.csv':
            # corrupted according to earlier report
            classified['F. OBSOLETE'].append(item)
        elif p in ['scripts/process_day2.py', 'scripts/populate_db.py']:
            # fully superseded by day2_5
            classified['F. OBSOLETE'].append(item)
        elif p in ['scripts/inspect_day2_5.py', 'scripts/analyze_osm.py', 'scripts/dump_quality.py', 'scripts/process_day2_5.py', 'scripts/populate_db_day2_5.py']:
            classified['A. REQUIRED NOW'].append(item)
        elif 'datasets/processed/' in p and (p.endswith('.csv')):
            classified['A. REQUIRED NOW'].append(item) # Generated but we are not deleting
        elif p.startswith('app/'):
            classified['A. REQUIRED NOW'].append(item)
        elif p.startswith('tests/'):
            classified['A. REQUIRED NOW'].append(item)
        elif p.startswith('docs/') or p.startswith('reports/'):
            classified['A. REQUIRED NOW'].append(item)
        elif p == 'requirements.txt':
            classified['A. REQUIRED NOW'].append(item)
        elif p.startswith('datasets/raw/'):
            classified['A. REQUIRED NOW'].append(item)
        elif p.startswith('datasets/osm/'):
            classified['B. REQUIRED FOR FUTURE'].append(item)
        elif p.endswith('.db'):
            classified['A. REQUIRED NOW'].append(item)
        else:
            classified['G. UNCERTAIN'].append(item)
            
    return classified

def do_audit():
    root = Path('d:/Collaborative-Multi-Agent-Travel-Planner')
    inventory = generate_inventory()
    classified = classify_files(inventory)
    
    os.makedirs('reports', exist_ok=True)
    report_path = 'reports/project_cleanup_audit.md'
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# Project Cleanup Audit\n\n")
        f.write("## 1. Complete Project Inventory\n")
        for item in inventory:
            f.write(f"- {item['path']} ({item['size']} bytes) {'[DIR]' if item['is_dir'] else ''}\n")
            
        f.write("\n## 2-8. Classifications\n")
        for key, items in classified.items():
            f.write(f"\n### {key}\n")
            if not items:
                f.write("None\n")
            for i in items:
                f.write(f"- {i['path']}\n")
                
        f.write("\n## 9. Proposed Deletions & 10. Reasons\n")
        f.write("- `datasets/raw/hotels/hotels.csv`: Corrupted file (utf-8 read failure), fully replaced by OYO_HOTEL_ROOMS files.\n")
        f.write("- `scripts/process_day2.py`: Obsolete, fully replaced by `process_day2_5.py` which handles canonical assignment.\n")
        f.write("- `scripts/populate_db.py`: Obsolete, fully replaced by idempotent `populate_db_day2_5.py`.\n")
        f.write("- `__pycache__` and `.pyc` and `.pytest_cache` folders/files: Safe to remove cache.\n")
        
        f.write("\n## 11. Risks\n")
        f.write("Deleting scripts could break historical traces, but they are fully superseded. Cache deletions are zero risk.\n")
        
if __name__ == '__main__':
    do_audit()
