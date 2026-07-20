# import uuid

# from qdrant_client import QdrantClient, models

# # Embedded local mode: stores data on disk, no server/URL needed.
# client = QdrantClient(path="./qdrant_data")

# # QDRANT_URL = os.getenv("QDRANT_URL", "[localhost](http://localhost:6333)")
# # QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None

# # client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# TEXT_COLLECTION = "video_text_segments"
# FRAME_COLLECTION = "video_frames"

import uuid

from qdrant_client import QdrantClient, models

# Embedded local mode: stores data on disk, no server/URL needed.
client = QdrantClient(path="./qdrant_data")

TEXT_COLLECTION = "video_text_segments"
FRAME_COLLECTION = "video_frames"


def ensure_collections():
    if not client.collection_exists(TEXT_COLLECTION):
        client.create_collection(
            collection_name=TEXT_COLLECTION,
            vectors_config=models.VectorParams(
                size=384,
                distance=models.Distance.COSINE,
            ),
        )

    if not client.collection_exists(FRAME_COLLECTION):
        client.create_collection(
            collection_name=FRAME_COLLECTION,
            vectors_config=models.VectorParams(
                size=512,
                distance=models.Distance.COSINE,
            ),
        )


def clear_collections():
    """Wipe all stored points so only the most recently uploaded video's data
    is searchable. The frontend only supports one active video at a time, so
    leftover points from a previous upload would otherwise pollute /ask
    results with segments/frames from a video that's no longer displayed.
    """
    if client.collection_exists(TEXT_COLLECTION):
        client.delete_collection(TEXT_COLLECTION)
    if client.collection_exists(FRAME_COLLECTION):
        client.delete_collection(FRAME_COLLECTION)
    ensure_collections()


def store_text_embeddings(video_id: str, segments: list[dict]):
    points = []

    for i, seg in enumerate(segments):
        timestamp = seg.get("timestamp") or [None, None]
        start = timestamp[0]
        end = timestamp[1]

        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{video_id}_text_{i}"))

        points.append(
            models.PointStruct(
                id=point_id,
                vector=seg["embedding"],
                payload={
                    "video_id": video_id,
                    "type": "text",
                    "text": seg.get("text"),
                    "start": start,
                    "end": end,
                },
            )
        )

    if points:
        client.upsert(
            collection_name=TEXT_COLLECTION,
            points=points,
        )


def store_frame_embeddings(video_id: str, frame_results: list[dict]):
    points = []

    for item in frame_results:
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{video_id}_frame_{item['frame']}"))

        points.append(
            models.PointStruct(
                id=point_id,
                vector=item["embedding"],
                payload={
                    "video_id": video_id,
                    "type": "frame",
                    "frame": item["frame"],
                    "timestamp": item.get("timestamp"),
                },
            )
        )

    if points:
        client.upsert(
            collection_name=FRAME_COLLECTION,
            points=points,
        )


def search_text(query_embedding: list[float], limit: int = 5, video_id: str | None = None):
    query_filter = None
    if video_id:
        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="video_id",
                    match=models.MatchValue(value=video_id),
                )
            ]
        )

    results = client.query_points(
        collection_name=TEXT_COLLECTION,
        query=query_embedding,
        limit=limit,
        with_payload=True,
        query_filter=query_filter,
    )

    return results.points


def search_frames(query_embedding: list[float], limit: int = 5, video_id: str | None = None):
    """Search the frame collection using a 512-dim CLIP text embedding."""

    query_filter = None
    if video_id:
        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="video_id",
                    match=models.MatchValue(value=video_id),
                )
            ]
        )

    results = client.query_points(
        collection_name=FRAME_COLLECTION,
        query=query_embedding,
        limit=limit,
        with_payload=True,
        query_filter=query_filter,
    )

    return results.points