import duckdb
import os
from pathlib import Path

con = duckdb.connect('blackvault_data/vault.db')
rows = con.execute('SELECT id, source_path, title FROM items').fetchall()
print(f'Total items in DB: {len(rows)}\n')

for r in rows:
    item_id, path_str, title = r
    if not path_str:
        print(f'[{item_id}] (No path) - {title}')
        continue
        
    p = Path(path_str)
    exists = p.exists()
    status = 'OK' if exists else 'MISSING'
    print(f'[{item_id}] {status} | Path: {path_str} | Title: {title}')
