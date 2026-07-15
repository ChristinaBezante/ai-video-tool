import os
import re
import time
import wave
from huggingface_hub import InferenceClient
from dotenv import load_dotenv
import math
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

whisper_token = os.getenv("HF_TOKEN")

MAX_SEGMENT_SECONDS = 30.0

client = InferenceClient(provider="hf-inference", token=whisper_token)

CHUNK_SECONDS = 120  # 2 minutes

# The shared HF "hf-inference" endpoint is serverless infra: on a cold start
# (or under load) it can take longer to spin up whisper-large-v3 than the
# router's own gateway timeout allows, which surfaces as a 504 to us even
# though the request itself was fine. Retrying with backoff smooths over
# these transient failures without needing a dedicated Inference Endpoint.
ASR_MAX_RETRIES = 3
ASR_RETRY_BACKOFF_SECONDS = 8
_RETRYABLE_MARKERS = ("504", "502", "503", "gateway", "timeout", "timed out")


def _is_retryable_asr_error(exc):
    message = str(exc).lower()
    return any(marker in message for marker in _RETRYABLE_MARKERS)


def split_audio(audio_path, output_dir, chunk_seconds=CHUNK_SECONDS):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    chunk_paths = []

    with wave.open(str(audio_path), "rb") as wav:
        params = wav.getparams()

        sample_rate = wav.getframerate()
        frames_per_chunk = sample_rate * chunk_seconds

        total_frames = wav.getnframes()
        total_chunks = math.ceil(total_frames / frames_per_chunk)

        for i in range(total_chunks):
            frames = wav.readframes(frames_per_chunk)

            chunk_path = output_dir / f"chunk_{i:04d}.wav"

            with wave.open(str(chunk_path), "wb") as out:
                out.setparams(params)
                out.writeframes(frames)

            chunk_paths.append(chunk_path)

    return chunk_paths


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
    output = None
    last_exc = None

    for attempt in range(1, ASR_MAX_RETRIES + 1):
        try:
            output = client.automatic_speech_recognition(
                audio_path,
                model="openai/whisper-large-v3",
                extra_body={
                    "return_timestamps": True
                }
            )
            last_exc = None
            break
        except Exception as e:
            last_exc = e
            if attempt == ASR_MAX_RETRIES or not _is_retryable_asr_error(e):
                raise
            wait_seconds = ASR_RETRY_BACKOFF_SECONDS * attempt
            print(
                f"transcribe_audio: attempt {attempt}/{ASR_MAX_RETRIES} failed "
                f"for {audio_path} ({e}); retrying in {wait_seconds}s..."
            )
            time.sleep(wait_seconds)

    if output is None:
        raise last_exc

    data = _coerce_to_dict(output)
    segments = _refine_segments(_normalize_segments(data), audio_path, data.get("text") or "")

    return {
        "text": (data.get("text") or "").strip(),
        "segments": segments,
        "timestamps": segments,
    }

MAX_WORKERS = 4


def transcribe_audio_chunks(audio_path):
    chunks = split_audio(audio_path, "temp_chunks")

    full_text = ""
    all_segments = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:

        futures = {}

        for index, chunk in enumerate(chunks):
            futures[
                executor.submit(transcribe_audio, str(chunk))
            ] = index

        results = {}

        for future in as_completed(futures):

            index = futures[future]

            try:
                results[index] = future.result()
            except Exception as e:
                print(f"Chunk {index} failed: {e}")

    for index in sorted(results):

        result = results[index]

        offset = index * CHUNK_SECONDS

        full_text += result["text"] + " "

        for segment in result["segments"]:

            segment["start"] += offset
            segment["end"] += offset

            all_segments.append(segment)

    # Delete temporary chunks AFTER transcription is complete
    for chunk in chunks:
        chunk.unlink(missing_ok=True)

    return {
        "text": full_text.strip(),
        "segments": all_segments,
        "timestamps": all_segments,
    }