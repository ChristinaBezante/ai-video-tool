import json
import os
import time

from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError

load_dotenv()

client = InferenceClient(
    provider="hf-inference",
    api_key=os.getenv("HF_TOKEN"),
)

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Text embedding calls are I/O-bound (waiting on the HF API), so running
# several concurrently in threads gives a near-linear speedup instead of
# embedding one transcript segment at a time.
MAX_WORKERS = 8


def _feature_extraction_with_retry(text: str, max_attempts: int = 3, backoff_seconds: float = 1.5):
    """Call the HF feature-extraction endpoint, retrying on transient 5xx errors.

    The hosted HF Inference API occasionally returns a 500 for this model even
    when the request is valid; a short retry with backoff resolves it almost
    every time without surfacing an error to the user.
    """
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            return client.feature_extraction(text, model=EMBEDDING_MODEL)
        except HfHubHTTPError as e:
            last_error = e
            status_code = getattr(e.response, "status_code", None)
            if status_code and status_code < 500:
                raise  # client error (bad request/auth) -- retrying won't help
            if attempt < max_attempts:
                time.sleep(backoff_seconds * attempt)
    raise last_error


def create_embeddings(transcript_json_path: str):
    # Read Whisper JSON
    with open(transcript_json_path, "r", encoding="utf-8") as f:
        transcript = json.load(f)

    return create_embeddings_from_transcript(transcript)


def create_embeddings_from_transcript(transcript: dict):
    chunks = transcript.get("segments") or transcript.get("chunks") or []

    # Filter down to segments that actually have text first, so the thread
    # pool only ever does useful work and stays index-aligned with `texts`.
    valid_chunks = [c for c in chunks if (c.get("text") or "").strip()]
    texts = [c["text"].strip() for c in valid_chunks]

    if not texts:
        return []

    # executor.map preserves input order in its output, so embeddings[i]
    # always corresponds to texts[i] / valid_chunks[i] -- no re-matching
    # needed after the concurrent calls finish.
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        embeddings = list(executor.map(_feature_extraction_with_retry, texts))

    results = []
    for chunk, text, embedding in zip(valid_chunks, texts, embeddings):
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

    embedding = _feature_extraction_with_retry(question)

    if hasattr(embedding, "tolist"):
        embedding = embedding.tolist()

    return embedding