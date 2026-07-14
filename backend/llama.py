import os
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv()

client = InferenceClient(
    provider="auto",
    api_key=os.getenv("HF_TOKEN"),
)

def ask_llama(question: str, context: str):
    messages = [
        {
            "role": "system",
            "content": (
                "You are an assistant that answers questions using ONLY the "
                "provided video transcript excerpts. Synthesize your answer "
                "from ALL relevant parts of the transcript, not just one "
                "sentence. Combine related information into a coherent "
                "2-4 sentence answer. If the answer is not contained in the "
                "transcript, say: \"I couldn't find this information in the video.\""
            ),
        },
        {
            "role": "user",
            "content": f"Transcript:\n{context}\n\nQuestion:\n{question}",
        },
    ]

    completion = client.chat.completions.create(
        model="meta-llama/Llama-3.1-8B-Instruct",
        messages=messages,
        max_tokens=200,
        temperature=0.3,
    )

    return completion.choices[0].message.content.strip()