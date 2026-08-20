from pathlib import Path
import threading
# Model name — loaded lazily on first call so server starts instantly.
_MODEL_NAME = "openai/clip-vit-base-patch32"
_model = None
_processor = None

_model_lock = threading.Lock()
def _get_model():
    global _model, _processor
    if _model is None:
        with _model_lock:
            if _model is None: # noqa: PLC0415
                from transformers import CLIPModel, CLIPProcessor  # noqa: PLC0415
                _processor = CLIPProcessor.from_pretrained(_MODEL_NAME)
                _model = CLIPModel.from_pretrained(_MODEL_NAME)
                _model.eval()
    return _model, _processor


def _format_timestamp(seconds: float | None) -> str | None:
    """Convert seconds to MM:SS format (e.g. 125.43 -> '02:05')."""
    if seconds is None:
        return None
    total_seconds = int(seconds)
    minutes, secs = divmod(total_seconds, 60)
    return f"{minutes:02d}:{secs:02d}"


def create_frame_embeddings(
    frames_dir: str,
    batch_size: int = 8,
    frame_interval_sec: float | None = None,
    timestamps: dict[str, float] | None = None,
) -> list[dict]:
    """Embed all JPEG frames in frames_dir using CLIP (batched for speed).

    Args:
        frames_dir: directory containing frame*.jpg files.
        batch_size: batch size for CLIP inference.
        frame_interval_sec: if provided (and `timestamps` is not), timestamp
            for frame N is computed as N * frame_interval_sec. Use this for
            fixed-interval extraction.
        timestamps: optional explicit mapping of frame filename -> timestamp
            (seconds). Use this for scene-detection / keyframe extraction,
            where spacing isn't uniform. Takes precedence over
            frame_interval_sec.

    Returns a list of dicts:
        { "frame": "frame000001.jpg", "timestamp": 12.0,
          "timestamp_formatted": "00:12", "embedding": [...] }
    """
    import torch  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    frame_paths = sorted(Path(frames_dir).glob("frame*.jpg"))
    if not frame_paths:
        return []

    model, processor = _get_model()
    results = []

    for batch_start in range(0, len(frame_paths), batch_size):
        batch_paths = frame_paths[batch_start : batch_start + batch_size]
        images = [Image.open(p).convert("RGB") for p in batch_paths]
        inputs = processor(images=images, return_tensors="pt", padding=True)

        with torch.no_grad():
            # transformers 5.x: get_image_features returns BaseModelOutputWithPooling.
            # Extract CLS pooler_output then project to the shared embedding space.
            vision_out = model.vision_model(**{k: v for k, v in inputs.items() if k == "pixel_values"})
            pooled = vision_out.pooler_output          # (N, hidden_dim)
            embeddings = model.visual_projection(pooled)  # (N, projection_dim=512)
            embeddings = embeddings / embeddings.norm(dim=-1, keepdim=True)

        for i, (path, emb) in enumerate(zip(batch_paths, embeddings)):
            frame_index = batch_start + i

            if timestamps is not None:
                ts = timestamps.get(path.name)
            elif frame_interval_sec is not None:
                ts = round(frame_index * frame_interval_sec, 3)
            else:
                ts = None

            # Ensure embedding is always a flat 1-D list, never [[...]].
            flat = emb.cpu().flatten().tolist()
            results.append(
                {
                    "frame": path.name,
                    "timestamp": ts,
                    "timestamp_formatted": _format_timestamp(ts),
                    "embedding": flat,
                }
            )

    return results


def embed_text_clip(text: str) -> list[float]:
    """Encode a text query into the 512-dim CLIP embedding space.

    CLIP aligns text and image representations, so this vector can be
    compared directly against frame embeddings stored in Qdrant.
    """
    import torch  # noqa: PLC0415

    model, processor = _get_model()
    # CLIP's text tower has a fixed 77-token context window; longer queries
    # raise ValueError in model.text_model without truncation.
    inputs = processor(
        text=[text],
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=77,
    )
    with torch.no_grad():
        # Call text sub-model and projection explicitly to avoid version
        # differences in get_text_features() return type.
        text_outputs = model.text_model(
            input_ids=inputs["input_ids"],
            attention_mask=inputs.get("attention_mask"),
        )
        text_features = model.text_projection(text_outputs.pooler_output)
    # L2-normalise to unit sphere so cosine similarity == dot product.
    text_features = text_features / text_features.norm(dim=-1, keepdim=True)
    return text_features[0].tolist()