from qdrant_store import client, TEXT_COLLECTION, FRAME_COLLECTION

print("text points:", client.count(collection_name=TEXT_COLLECTION))
print("frame points:", client.count(collection_name=FRAME_COLLECTION))