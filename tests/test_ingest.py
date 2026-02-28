import sys
import os
import time
from pathlib import Path
import unittest

# Setup path so we can import src modules
sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from backend.ingest import ingest_file, DuplicateError
from backend import db

class TestIngest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # We assume the main database is being used or test db if configured
        db.get_connection()

    def test_1_text_ingest_and_update(self):
        import uuid
        run_id = str(uuid.uuid4())
        # Create a temp txt file
        test_file = Path("test_ingest_temp.txt")
        test_content_1 = f"Hello world testing ingest. Run ID: {run_id}"
        test_file.write_text(test_content_1, encoding="utf-8")
        
        try:
            item_id = ingest_file(str(test_file), test_content_1)
            self.assertIsNotNone(item_id, "Item ID should not be None")
            
            # Verify it exists in db
            item = db.get_item(item_id)
            self.assertIsNotNone(item)
            self.assertEqual(item["source_path"], str(test_file.resolve()))
            
            # Test duplicate ingestion
            with self.assertRaises(DuplicateError):
                ingest_file(str(test_file), test_content_1)
                
            # Test modification (should insert new because hash changes)
            test_content_2 = f"Hello world testing ingest. MODIFIED! Run ID: {run_id}"
            test_file.write_text(test_content_2, encoding="utf-8")
            item_id_2 = ingest_file(str(test_file), test_content_2)
            self.assertNotEqual(item_id, item_id_2)
            
        finally:
            if test_file.exists():
                test_file.unlink()

if __name__ == "__main__":
    unittest.main()
