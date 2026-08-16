import os
import re
import sys
import time
import wave
import requests as _requests
from dotenv import load_dotenv
import math
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
from openai import OpenAI as _OpenAI

load_dotenv()

# Increase recursion limit for deep segment estimation in large videos
sys.setrecursionlimit(5000)

whisper_token = os.getenv("HF_TOKEN")
_openai_api_key = os.getenv("OPENAI_API_KEY")

MAX_SEGMENT_SECONDS = 30.0

_ASR_MODEL = "openai/whisper-large-v3-turbo"
_HF_ASR_FALLBACK_URL = f"https://router.huggingface.co/hf-inference/models/{_ASR_MODEL}"

# OpenAI Whisper API — fastest option (truly parallel, ~2s/chunk)
_openai_client = _OpenAI(api_key=_openai_api_key) if _openai_api_key else None

# Use dedicated Inference Endpoint when configured (always warm, no rate limits)
_endpoint_url = os.getenv("HF_WHISPER_ENDPOINT_URL")
_endpoint_token = os.getenv("HF_WHISPER_ENDPOINT_TOKEN")

if _openai_client:
    print("[Whisper] Using OpenAI Whisper API")
elif _endpoint_url and _endpoint_token:
    _asr_url = _endpoint_url
    _asr_token = _endpoint_token
    print("[Whisper] Using dedicated Inference Endpoint")
else:
    _asr_url = _HF_ASR_FALLBACK_URL
    _asr_token = whisper_token
    print("[Whisper] Using HF Inference API (direct HTTP)")

CHUNK_SECONDS = 60  # 60s chunks: halves the number of API calls vs 30s

# The shared HF "hf-inference" endpoint is serverless infra: on a cold start
# (or under load) it can take longer to spin up whisper-large-v3 than the
# router's own gateway timeout allows, which surfaces as a 504 to us even
# though the request itself was fine. A dedicated Inference Endpoint skips
# this entirely and has no rate limits. Retrying with backoff smooths over
# any transient failures on either endpoint.
ASR_MAX_RETRIES = 3
ASR_RETRY_BACKOFF_SECONDS = 2  # dedicated endpoint: no cold starts
_RETRYABLE_MARKERS = ("504", "502", "503", "429", "gateway", "timeout", "timed out", "rate limit")


def _is_retryable_asr_error(exc):
    message = str(exc).lower()
    return any(marker in message for marker in _RETRYABLE_MARKERS)


def _is_silent_wav(audio_path: str, silence_threshold: float = 0.001) -> bool:
    """Return True if the WAV file is empty or near-silent (RMS < 0.1% of full scale)."""
    import struct
    try:
        with wave.open(audio_path, "rb") as wav_file:
            raw = wav_file.readframes(wav_file.getnframes())
        if not raw or len(raw) < 2:
            return True
        sample_count = len(raw) // 2
        samples = struct.unpack(f"<{sample_count}h", raw[:sample_count * 2])
        rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
        return (rms / 32768.0) < silence_threshold
    except Exception:
        return False


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
    """
    Only estimate segments as a fallback if we have no segments or they're invalid.
    Trust Whisper's timestamps—don't try to recursively subdivide them (causes deep recursion).
    """
    if not segments:
        # No segments: estimate from full text
        duration = _wav_duration_seconds(audio_path)
        return _estimate_segments_from_text(fallback_text, 0.0, duration, max_segment_seconds=max_segment_seconds)

    # Filter segments: only keep those with valid text and timestamps
    valid_segments = []
    for item in segments:
        start = item.get("start")
        end = item.get("end")
        text = (item.get("text") or "").strip()

        if text and isinstance(start, (int, float)) and isinstance(end, (int, float)) and end > start:
            valid_segments.append({
                "start": round(float(start), 3),
                "end": round(float(end), 3),
                "text": text,
            })

    # If we got valid segments from Whisper, return them as-is
    # (don't try to recursively subdivide—that causes recursion depth errors)
    if valid_segments:
        return valid_segments

    # Fallback: estimate from full text if no valid segments
    duration = _wav_duration_seconds(audio_path)
    return _estimate_segments_from_text(fallback_text, 0.0, duration, max_segment_seconds=max_segment_seconds)


def _transcribe_via_openai(audio_path: str) -> dict:
    """Transcribe via OpenAI Whisper API — truly parallel, ~2s/chunk."""
    with open(audio_path, "rb") as f:
        response = _openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
            timeout=60,  # fail fast instead of hanging on a stalled connection
        )
    return response.model_dump()


def _transcribe_via_http(audio_path: str) -> dict:
    """POST audio directly to the configured ASR endpoint; no InferenceClient routing."""
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()
    resp = _requests.post(
        _asr_url,
        headers={
            "Authorization": f"Bearer {_asr_token}",
            "Content-Type": "audio/wav",
            "x-wait-for-model": "true",  # hold connection until model is warm instead of 503
        },
        data=audio_bytes,
        timeout=300,
    )
    if not resp.ok:
        print(f"[ASR] {resp.status_code}: {resp.text[:300]}")
    resp.raise_for_status()
    return resp.json()


def transcribe_audio(audio_path: str):
    if _is_silent_wav(audio_path):
        print(f"transcribe_audio: skipping silent chunk {audio_path}")
        return {"text": "", "segments": [], "timestamps": []}

    data = None
    last_exc = None

    for attempt in range(1, ASR_MAX_RETRIES + 1):
        try:
            data = _transcribe_via_openai(audio_path) if _openai_client else _transcribe_via_http(audio_path)
            last_exc = None
            break
        except Exception as e:
            last_exc = e
            if attempt == ASR_MAX_RETRIES:
                raise
            wait_seconds = ASR_RETRY_BACKOFF_SECONDS * attempt + random.uniform(0, 2)
            print(
                f"transcribe_audio: attempt {attempt}/{ASR_MAX_RETRIES} failed "
                f"for {audio_path} ({type(e).__name__}: {e}); retrying in {wait_seconds:.1f}s..."
            )
            time.sleep(wait_seconds)

    if data is None:
        raise last_exc

    try:
        segments = _normalize_segments(data)
        refined = _refine_segments(segments, audio_path, data.get("text") or "")
    except Exception as e:
        print(f"ERROR processing audio {audio_path}: {e}")
        import traceback
        traceback.print_exc()
        raise

    return {
        "text": (data.get("text") or "").strip(),
        "segments": refined,
        "timestamps": refined,
    }

MAX_WORKERS = 16  # OpenAI allows high concurrency; HF router: 8 is sufficient


def transcribe_audio_chunks(audio_path):
    audio_path = Path(audio_path)
    # Give each video its own chunk subfolder (named after the audio file's
    # stem) instead of a single shared "temp_chunks" folder. With one shared
    # folder, leftover chunks from a crashed/previous run, or a second
    # upload processed while this one is still running, could collide with
    # or get mixed into this video's chunk_0000.wav-style filenames.
    chunk_dir = Path("temp_chunks") / audio_path.stem
    chunks = split_audio(audio_path, chunk_dir)

    print(f"Created {len(chunks)} chunks")

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
                result = future.result()

                print(f"\nChunk {index}")
                print("Text:", result["text"][:80] if result["text"] else "[EMPTY]")
                print("Segments:", len(result["segments"]))

                results[index] = result
            except Exception as e:
                print(f"Chunk {index} failed: {type(e).__name__}: {e}")

    # --- retry any chunks that failed on the first pass ---
    failed_indices = [i for i in range(len(chunks)) if i not in results]
    if failed_indices:
        print(f"Retrying {len(failed_indices)} failed chunks...")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            retry_futures = {
                executor.submit(transcribe_audio, str(chunks[i])): i
                for i in failed_indices
            }
            for future in as_completed(retry_futures):
                index = retry_futures[future]
                try:
                    results[index] = future.result()
                    print(f"Chunk {index} succeeded on retry")
                except Exception as e:
                    print(f"Chunk {index} failed again: {e}")


    for index in sorted(results):

        result = results[index]

        offset = index * CHUNK_SECONDS

        full_text += result["text"] + " "

        for segment in result["segments"]:

            segment["start"] += offset
            segment["end"] += offset

            all_segments.append(segment)

    print("Successful chunks:", len(results))
    print("Failed chunks:", len(chunks) - len(results))

    # Add placeholder segments for permanently failed chunks
    failed_indices = [i for i in range(len(chunks)) if i not in results]
    if failed_indices:
        for index in sorted(failed_indices):
            offset = index * CHUNK_SECONDS
            all_segments.append({
                "start": round(offset, 3),
                "end": round(offset + CHUNK_SECONDS, 3),
                "text": "[TRANSCRIPTION FAILED - AUDIO UNAVAILABLE]"
            })
        print(f"Added {len(failed_indices)} placeholder segments for failed chunks")

    # Sort all segments by start time
    all_segments.sort(key=lambda s: s.get("start", 0))

    # Delete temporary chunks AFTER transcription is complete
    for chunk in chunks:
        chunk.unlink(missing_ok=True)
    try:
        chunk_dir.rmdir()
    except OSError:
        pass  # not empty (unexpected leftover file) or already removed

    print("Merged text length:", len(full_text))
    print("Merged segments:", len(all_segments))

    return {
        "text": full_text.strip(),
        "segments": all_segments,
        "timestamps": all_segments,
    }