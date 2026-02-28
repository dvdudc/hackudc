import sys
import time
from pathlib import Path

# Add src to python path for imports
sys.path.append(str(Path(__file__).parent.parent))

from backend.search import search as baseline_search
from backend import db

def run_benchmark():
    queries = [
        "ideas sobre productividad",
        "documentos de python",
        "archivos de configuracion"
    ]
    
    print("=== BASELINE SEARCH BENCHMARK ===")
    for q in queries:
        start = time.time()
        results = baseline_search(q, limit=3, use_enrichment=False)
        duration = time.time() - start
        
        print(f"\nQuery: '{q}' (took {duration:.4f}s)")
        if not results:
            print("  No results found.")
        for i, r in enumerate(results, 1):
            print(f"  {i}. [ID:{r['item_id']}] {r.get('title', 'Unknown')} (Score: {r['score']:.4f})")

    print("\n\n=== ENRICHED SEARCH BENCHMARK ===")
    from unittest.mock import patch
    import json
    import io
    
    # Mock responses for Ollama
    mock_responses = {
        "ideas sobre productividad": json.dumps({"response": '{"expanded_query": "mejorar productividad eficiente metodos trabajo gestion tiempo", "sql_filter": "i.source_type = \\\'text\\\'"}'}),
        "documentos de python": json.dumps({"response": '{"expanded_query": "tutoriales codigo scripts python programacion desarrollo", "sql_filter": "i.source_type = \\\'markdown\\\' OR i.tags LIKE \\\'%python%\\\'"}'}),
        "archivos de configuracion": json.dumps({"response": '{"expanded_query": "configurar variables entorno sysadmin parametros", "sql_filter": "i.title LIKE \\\'%.env%\\\' OR i.title LIKE \\\'%config%\\\'"}'})
    }

    def mock_urlopen(req, *args, **kwargs):
        # Extremely simple mock: parse the prompt to find the original query and return the matched response.
        # This works because our prompt literally contains 'User Query: "..."'
        req_data = req.data.decode("utf-8")
        body = json.loads(req_data)
        prompt = body.get("prompt", "")
        
        # Find which query is in the prompt
        matched_q = "ideas sobre productividad" # default
        for q in queries:
            if q in prompt:
                matched_q = q
                break
                
        # Create a mock response object
        response = mock_responses[matched_q].encode("utf-8")
        
        class MockResponse:
            def __init__(self, content):
                self.content = content
            def read(self):
                return self.content
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass
                
        return MockResponse(response)

    with patch('urllib.request.urlopen', side_effect=mock_urlopen):
        for q in queries:
            start = time.time()
            results = baseline_search(q, limit=3, use_enrichment=True)
            duration = time.time() - start
            
            print(f"\nQuery: '{q}' (took {duration:.4f}s)")
            if not results:
                print("  No results found.")
            for i, r in enumerate(results, 1):
                print(f"  {i}. [ID:{r['item_id']}] {r.get('title', 'Unknown')} (Score: {r['score']:.4f})")

if __name__ == "__main__":
    run_benchmark()
