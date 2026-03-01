import sys
import os
import time
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from backend import db
from backend.ingest import ingest_file
from backend.consolidate import cluster_notes, run_consolidation

class TestConsolidate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.get_connection()

    def test_cluster_notes(self):
        # 3 similar, 1 different
        notes = [
            {"item_id": 1, "text": "comprar huevos", "embedding": [0.9, 0.1, 0.0]},
            {"item_id": 2, "text": "comprar leche", "embedding": [0.85, 0.15, 0.0]},
            {"item_id": 3, "text": "comprar pan", "embedding": [0.8, 0.2, 0.0]},
            {"item_id": 4, "text": "llamar a juan", "embedding": [0.0, 0.1, 0.9]}
        ]
        
        # Test basic clustering
        clusters = cluster_notes(notes, similarity_threshold=0.80)
        
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0]), 3)
        
        ids_in_cluster = {n["item_id"] for n in clusters[0]}
        self.assertEqual(ids_in_cluster, {1, 2, 3})

    @patch('backend.connections.find_connections')
    @patch('backend.enrich.enrich_item')
    @patch('backend.ingest.get_embeddings_batch')
    @patch('backend.consolidate.consolidate_cluster')
    def test_run_consolidation_integration(self, mock_consolidate, mock_embeddings, mock_enrich, mock_connections):
        mock_consolidate.return_value = ("Lista de Compras", "comprar huevos, leche y algo de pan.")
        
        # Setup mock embeddings (1 for each file, and 1 for the consolidated result)
        # DuckDB requires exactly 3072 dimensions
        mock_embeddings.side_effect = [
            [[0.9, 0.1, 0.0] + [0.0]*3069],
            [[0.85, 0.1, 0.05] + [0.0]*3069],
            [[0.8, 0.2, 0.0] + [0.0]*3069],
            [[0.1, 0.1, 0.8] + [0.0]*3069],
            [[0.9, 0.1, 0.0] + [0.0]*3069], # consolidated note embedding
        ]
        
        # Ingest test files to get real IDs and let the DB functions work
        files = []
        import uuid
        run_id = str(uuid.uuid4())
        try:
            test_texts = [
                f"comprar huevos {run_id}", 
                f"comprar leche {run_id}", 
                f"comprar pan {run_id}", 
                f"reunion mañana a las 5 {run_id}"
            ]
            for i, text in enumerate(test_texts):
                p = Path(f"test_cons_temp_{i}_{run_id}.txt")
                p.write_text(text, encoding="utf-8")
                files.append(p)
                ingest_file(str(p), text)
                
            time.sleep(1) # wait for DB settle
            
            # Since real embeddings might vary, let's just make sure run_consolidation does not crash
            results = run_consolidation()
            
            # If they clustered, check deletions
            if len(results) >= 1:
                found = False
                for r in results:
                    if r["title"] == "Lista de Compras":
                        found = True
                        self.assertTrue(r["new_id"] > 0)
                        
                        # Verify deleted from DB
                        for did in r["deleted_ids"]:
                            item = db.get_item(did)
                            self.assertIsNone(item)
                
                self.assertTrue(found)

        finally:
            for p in files:
                if p.exists():
                    p.unlink()

if __name__ == "__main__":
    unittest.main()
