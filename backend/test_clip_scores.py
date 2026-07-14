"""Quick sanity-check: embed a query with CLIP and print cosine scores
against every stored frame so you can see whether the retrieval is semantically correct.

Usage (from backend/):
    python test_clip_scores.py "circle"
    python test_clip_scores.py "neural network diagram"
"""

import sys
from frame_embeddings import embed_text_clip
from qdrant_store import client, FRAME_COLLECTION

query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "circle"
print(f"\nQuery: '{query}'\n")

query_vector = embed_text_clip(query)

results = client.query_points(
    collection_name=FRAME_COLLECTION,
    query=query_vector,
    limit=20,
    with_payload=True,
)

print(f"{'Score':>7}  {'Timestamp':>10}  Frame")
print("-" * 40)
for r in results.points:
    ts = r.payload.get("timestamp")
    ts_str = f"{int(ts//60):02d}:{int(ts%60):02d}" if ts is not None else "   ?"
    print(f"{r.score:>7.4f}  {ts_str:>10}  {r.payload.get('frame')}")
