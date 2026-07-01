from pathlib import Path

# Model name — loaded lazily on first call so server starts instantly.
_MODEL_NAME = "openai/clip-vit-base-patch32"
_model = None
_processor = None


def _get_model():
    global _model, _processor
    if _model is None:
        from transformers import CLIPModel, CLIPProcessor  # noqa: PLC0415
        _processor = CLIPProcessor.from_pretrained(_MODEL_NAME)
        _model = CLIPModel.from_pretrained(_MODEL_NAME)
        _model.eval()
    return _model, _processor


def create_frame_embeddings(frames_dir: str, batch_size: int = 8) -> list[dict]:
    """Embed all JPEG frames in frames_dir using CLIP (batched for speed).

    Returns a list of dicts:
        { "frame": "frame000001.jpg", "embedding": [...] }
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

        for path, emb in zip(batch_paths, embeddings):
            # Ensure embedding is always a flat 1-D list, never [[...]].
            flat = emb.cpu().flatten().tolist()
            results.append(
                {
                    "frame": path.name,
                    "embedding": flat,
                }
            )

    return results
