import os
import shutil
import time
from pathlib import Path
import pytest

def exec_cleanup():
    root = Path('d:/Collaborative-Multi-Agent-Travel-Planner')
    
    deleted_files = []
    
    def safe_delete(p):
        try:
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                shutil.rmtree(p)
            deleted_files.append(str(p.relative_to(root)))
        except Exception as e:
            print(f"Failed deleting {p}: {e}")

    # Calculate BEFORE stats
    all_files = list(root.rglob('*'))
    before_files = len([f for f in all_files if f.is_file() and 'venv' not in f.parts and '.git' not in f.parts])
    before_dirs = len([d for d in all_files if d.is_dir() and 'venv' not in f.parts and '.git' not in d.parts])
    
    # 1. Del Caches
    for p in root.rglob('__pycache__'):
        if 'venv' not in p.parts:
            safe_delete(p)
    for p in root.rglob('.pytest_cache'):
        if 'venv' not in p.parts:
            safe_delete(p)
            
    # 2. Del Obsolete Scripts
    s1 = root / 'scripts' / 'process_day2.py'
    if s1.exists(): safe_delete(s1)
    s2 = root / 'scripts' / 'populate_db.py'
    if s2.exists(): safe_delete(s2)
    
    # 3. Del Obsolete Hotel Dataset
    h1 = root / 'datasets' / 'raw' / 'hotels' / 'hotels.csv'
    if h1.exists(): safe_delete(h1)
    
    # Calculate AFTER stats
    all_files_after = list(root.rglob('*'))
    after_files = len([f for f in all_files_after if f.is_file() and 'venv' not in f.parts and '.git' not in f.parts])
    after_dirs = len([d for d in all_files_after if d.is_dir() and 'venv' not in f.parts and '.git' not in d.parts])
    
    report_path = 'reports/project_cleanup_audit.md'
    with open(report_path, 'a', encoding='utf-8') as f:
        f.write("\n## 14. FINAL REPORT\n\n")
        f.write("### BEFORE:\n")
        f.write(f"- total files: {before_files}\n")
        f.write(f"- total folders: {before_dirs}\n")
        
        f.write("\n### DELETED:\n")
        for df in deleted_files:
            f.write(f"- {df} (Obsolete/Cache)\n")
            
        f.write("\n### KEPT:\n")
        f.write("- Important project structure and Canonical datasets are untouched.\n")
        
        f.write("\n### AFTER:\n")
        f.write(f"- total files: {after_files}\n")
        f.write(f"- total folders: {after_dirs}\n")

if __name__ == '__main__':
    exec_cleanup()
