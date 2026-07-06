
from qdrant_store import client, TEXT_COLLECTION, FRAME_COLLECTION

points, _ = client.scroll(
    collection_name=TEXT_COLLECTION,
    limit=10,
    with_payload=True,
)
for p in points:
    print(p.payload)

points, _ = client.scroll(
    collection_name=FRAME_COLLECTION,
    limit=5,
    with_payload=True,
)
for p in points:
    print(p.payload)