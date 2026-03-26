import openai

# Configure the client to point to the FreeLLM Router
client = openai.OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="none"  # Not required for local router, but client needs a value
)

def chat_example():
    print("Calling FreeLLM Router via OpenAI Client...")
    try:
        response = client.chat.completions.create(
            model="adaptive",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Explain quantum entanglement in one sentence."}
            ],
            extra_body={"task_type": "analysis"} # Optional: hint for specialized routing
        )
        print("\nResponse:")
        print(response.choices[0].message.content)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    chat_example()
