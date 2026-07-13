import json
import os

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv()

client = InferenceClient(
    provider="hf-inference",
    api_key=os.getenv("HF_TOKEN"),
)

def create_embeddings(transcript_json_path: str):
    # Read Whisper JSON
    with open(transcript_json_path, "r", encoding="utf-8") as f:
        transcript = json.load(f)

    results = []

    chunks = transcript.get("segments") or transcript.get("chunks") or []

    for chunk in chunks:
        text = (chunk.get("text") or "").strip()
        if not text:
            continue

        embedding = client.feature_extraction(
            text,
            model="sentence-transformers/all-MiniLM-L6-v2",
        )

        # Convert NumPy array to a regular Python list
        if hasattr(embedding, "tolist"):
            embedding = embedding.tolist()

        timestamp = chunk.get("timestamp")
        if not timestamp:
            timestamp = [chunk.get("start"), chunk.get("end")]

        results.append({
            "text": text,
            "timestamp": timestamp,
            "embedding": embedding,
        })

    return results


def embed_query(question: str):
    print("Using HF Inference API")

    embedding = client.feature_extraction(
        question,
        model="sentence-transformers/all-MiniLM-L6-v2",
    )

    if hasattr(embedding, "tolist"):
        embedding = embedding.tolist()

    return embedding