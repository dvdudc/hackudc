import sys
sys.path.append('.')
from backend import db
from backend.consolidate import fetch_small_notes, cosine_similarity, cluster_notes

notes = fetch_small_notes()
print(f"Found {len(notes)} small notes")
for n in notes:
    print(f"Item {n['item_id']}: len={len(n['text'])}")
    print(f"  Text: {n['text']}")

clusters = cluster_notes(notes)
print(f"Clusters found: {len(clusters)}")
if len(notes) >= 2:
    for i in range(len(notes)):
        for j in range(i+1, len(notes)):
            sim = cosine_similarity(notes[i]['embedding'], notes[j]['embedding'])
            print(f"Sim between {notes[i]['item_id']} and {notes[j]['item_id']} = {sim}")
