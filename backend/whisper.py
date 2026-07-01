import os
import re
import wave
from huggingface_hub import InferenceClient
from dotenv import load_dotenv

load_dotenv()

whisper_token = os.getenv("HF_TOKEN")

MAX_SEGMENT_SECONDS = 30.0

client = InferenceClient(provider="hf-inference", token=whisper_token)


def _coerce_to_dict(output):
    if isinstance(output, dict):
        return output
    if hasattr(output, "model_dump"):
        return output.model_dump()
    if hasattr(output, "dict"):
        return output.dict()
    if hasattr(output, "__dict__"):
        return vars(output)
    return {"text": str(output)}


def _normalize_segments(data):
    raw_chunks = data.get("chunks") or data.get("segments") or []
    segments = []

    for item in raw_chunks:
        if isinstance(item, dict):
            chunk = item
        elif hasattr(item, "model_dump"):
            chunk = item.model_dump()
        elif hasattr(item, "dict"):
            chunk = item.dict()
        elif hasattr(item, "__dict__"):
            chunk = vars(item)
        else:
            continue

        timestamp = chunk.get("timestamp")
        start = chunk.get("start")
        end = chunk.get("end")

        if isinstance(timestamp, (list, tuple)) and len(timestamp) == 2:
            if start is None:
                start = timestamp[0]
            if end is None:
                end = timestamp[1]

        segments.append(
            {
                "start": start,
                "end": end,
                "text": (chunk.get("text") or "").strip(),
            }
        )

    return segments


def _wav_duration_seconds(audio_path):
    try:
        with wave.open(audio_path, "rb") as wav_file:
            frame_count = wav_file.getnframes()
            sample_rate = wav_file.getframerate()
            if sample_rate <= 0:
                return None
            return frame_count / float(sample_rate)
    except Exception:
        return None


def _split_text_units(text):
    units = [part.strip() for part in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if part.strip()]
    if units:
        return units
    fallback = (text or "").strip().split()
    if not fallback:
        return []
    group_size = 12
    return [" ".join(fallback[index:index + group_size]) for index in range(0, len(fallback), group_size)]


def _estimate_segments_from_text(text, start, end, max_segment_seconds=MAX_SEGMENT_SECONDS):
    clean_text = (text or "").strip()
    if not clean_text:
        return []

    if start is None:
        start = 0.0
    if end is None or end <= start:
        end = start + max_segment_seconds

    total_duration = max(float(end) - float(start), 0.0)
    units = _split_text_units(clean_text)
    if not units:
        return []

    total_chars = sum(max(len(unit), 1) for unit in units)
    cursor = float(start)
    estimated = []

    for index, unit in enumerate(units):
        proportional_duration = total_duration * (max(len(unit), 1) / total_chars) if total_chars else 0.0
        chunk_end = float(end) if index == len(units) - 1 else cursor + proportional_duration
        estimated.append(
            {
                "start": round(cursor, 3),
                "end": round(chunk_end, 3),
                "text": unit,
            }
        )
        cursor = chunk_end

    if total_duration > max_segment_seconds:
        refined = []
        for item in estimated:
            duration = (item["end"] or 0.0) - (item["start"] or 0.0)
            if duration <= max_segment_seconds:
                refined.append(item)
                continue
            refined.extend(
                _estimate_segments_from_text(
                    item.get("text", ""),
                    item.get("start"),
                    item.get("end"),
                    max_segment_seconds=max_segment_seconds,
                )
            )
        return refined

    return estimated


def _refine_segments(segments, audio_path, fallback_text, max_segment_seconds=MAX_SEGMENT_SECONDS):
    if not segments:
        duration = _wav_duration_seconds(audio_path)
        return _estimate_segments_from_text(fallback_text, 0.0, duration, max_segment_seconds=max_segment_seconds)

    refined = []
    for item in segments:
        start = item.get("start")
        end = item.get("end")
        text = (item.get("text") or "").strip()

        if text and isinstance(start, (int, float)) and isinstance(end, (int, float)) and end > start:
            if end - start > max_segment_seconds:
                refined.extend(
                    _estimate_segments_from_text(
                        text,
                        float(start),
                        float(end),
                        max_segment_seconds=max_segment_seconds,
                    )
                )
            else:
                refined.append({
                    "start": round(float(start), 3),
                    "end": round(float(end), 3),
                    "text": text,
                })
            continue

        refined.extend(
            _estimate_segments_from_text(
                text,
                start,
                end,
                max_segment_seconds=max_segment_seconds,
            )
        )

    return refined

def transcribe_audio(audio_path: str):
    output = client.automatic_speech_recognition(
        audio_path,
        model="openai/whisper-large-v3",
        extra_body={
            "return_timestamps": True
        }
    )

    data = _coerce_to_dict(output)
    segments = _refine_segments(_normalize_segments(data), audio_path, data.get("text") or "")

    return {
        "text": (data.get("text") or "").strip(),
        "segments": segments,
        "timestamps": segments,
    }