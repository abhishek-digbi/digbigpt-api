import urllib.request
import urllib.parse
import json

def ask_digbigpt():
    url = "http://127.0.0.1:9000/api/digbigpt/ask"
    
    data = {
        "question": "Which customers spent the most on omeprazole in 2023?",
        "user_id": "python_user"
    }
    
    # Convert data to JSON
    json_data = json.dumps(data).encode('utf-8')
    
    # Create request
    req = urllib.request.Request(
        url,
        data=json_data,
        headers={'Content-Type': 'application/json'}
    )
    
    # Make request
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
        return result

# Run it
result = ask_digbigpt()
print(json.dumps(result, indent=2))