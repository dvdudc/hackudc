import sys
sys.path.append('src')
from backend import db
con = db.get_connection()
rows = con.execute("SELECT i.id, i.title, i.source_path, i.source_type, length(c.body) as len FROM items i JOIN content c ON i.id = c.item_id").fetchall()
for r in rows:
    print(r)
