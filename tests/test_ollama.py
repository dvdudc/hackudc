import urllib.request
import json
import traceback

def test():
    req = urllib.request.Request(
        "http://10.8.0.3:11434/api/generate",
        data=json.dumps({
            "model": "llama3.2",
            "prompt": "Devuelve siempre un JSON estricto con esta estructura, sin texto adicional: { \"titulo\": \"Hola Mundo\", \"resumen\": \"test\" }",
            "stream": False,
            "format": "json"
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    try:
        response = urllib.request.urlopen(req).read().decode("utf-8")
        data = json.loads(response)
        
        raw = data.get("response", "").strip()
        print("RAW RESPONSE:")
        print(raw)
        
        parsed = json.loads(raw)
        print("PARSED JSON DICT:")
        print(parsed)
        
    except Exception as e:
        traceback.print_exc()

if __name__ == "__main__":
    test()
