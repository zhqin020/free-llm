import requests
import json

def chat_via_requests():
    url = "http://localhost:8000/v1/chat/completions"
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "adaptive",
        "messages": [
            {"role": "user", "content": "Write a short poem about coding."}
        ],
        "task_type": "text",
        "temperature": 0.8
    }

    print("Calling FreeLLM Router via Direct HTTP Request...")
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        print("\nResponse:")
        print(result['choices'][0]['message']['content'])
    except requests.exceptions.HTTPError as e:
        print(f"Error: {e}")
        if e.response is not None:
            print(f"Server Response: {e.response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    chat_via_requests()
