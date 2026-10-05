from fastapi import FastAPI, UploadFile, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import re
import shutil
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from fastapi.staticfiles import StaticFiles
from video_processing import extract_audio
from video_processing import extract_frames, normalize_video
from whisper import transcribe_audio_chunks
import json
import uuid
from bert import create_embeddings_from_transcript, embed_query, warm_up as warm_text_model
from frame_embeddings import create_frame_embeddings, embed_text_clip, warm_up as warm_clip_model
from qdrant_store import ensure_collections, store_text_embeddings, store_frame_embeddings, clear_collections
from qdrant_store import client, TEXT_COLLECTION, FRAME_COLLECTION, search_text, search_frames, scroll_all_text

from llama import ask_llama

from pydantic import BaseModel
import sys

# Progress output uses ✓ / ✗ / ↻ / ⏱. A non-interactive Windows process gets a
# cp1252 stdout, where printing any of those raises UnicodeEncodeError -- and
# since those prints sit inside the pipeline's try blocks, the encoding error
# was being reported as a processing failure. Reconfigure once, here, so a
# progress line can never fail a job.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

class Question(BaseModel):
    question: str
    video_id: str | None = None
    # Prior conversation turns as [{"role": "user"|"assistant", "content": str}, ...],
    # oldest first. Optional -- lets the LLM handle follow-up questions
    # ("what about that?") instead of treating every question in isolation.
    history: list[dict] | None = None


def _detect_question_language(text: str) -> str:
    """Return the answer language expected by the user.

    Greek-script input gets a Greek answer; everything else defaults to English.
    """
    if any("\u0370" <= char <= "\u03ff" or "\u1f00" <= char <= "\u1fff" for char in text):
        return "Greek"
    return "English"


def _detect_transcript_language(text: str) -> str:
    """Prefer Greek when the transcript contains Greek script."""
    if any("\u0370" <= char <= "\u03ff" or "\u1f00" <= char <= "\u1fff" for char in text):
        return "Greek"
    return "English"


def _is_summary_request(text: str) -> bool:
    lowered = text.lower()
    return any(
        phrase in lowered
        for phrase in (
            "summarize",
            "summary",
            "overview",
            "what is this video about",
            "τι δείχνει",
            "περίληψη",
            "σύνοψη",
        )
    )


def _summary_query_for_language(language: str) -> str:
    if language == "Greek":
        return "δώσε μια περίληψη του βίντεο με τα βασικά σημεία"
    return "give a summary of the video with the main points"


def _clip_query_for_summary() -> str:
    return "video summary"


def _expand_with_neighbors(candidates, all_segments, window=1):
    """Pull in each matched segment's immediate chronological neighbors.

    Semantic search scores each transcript segment independently, but a
    coherent explanation (e.g. walking through an automaton's states, or a
    data structure's operations) is often spread across several consecutive
    segments where only one or two individually score high enough to be
    retrieved. Without their neighbors, the LLM only sees isolated sentences
    and has to guess at the missing states/transitions -- expanding the
    context to include what comes immediately before/after each match keeps
    the example grounded in what the video actually says.
    """
    if not all_segments:
        return candidates

    id_to_index = {seg.id: i for i, seg in enumerate(all_segments)}
    selected_indices = set()

    for cand in candidates:
        idx = id_to_index.get(cand.id)
        if idx is None:
            continue
        for offset in range(-window, window + 1):
            neighbor_idx = idx + offset
            if 0 <= neighbor_idx < len(all_segments):
                selected_indices.add(neighbor_idx)

    if not selected_indices:
        return candidates

    return [all_segments[i] for i in sorted(selected_indices)]


_INLINE_TIMESTAMP_RE = re.compile(r"`(\d{1,2}):(\d{2})`")


def _snap_inline_timestamps(answer: str, segments) -> str:
    """Replace every inline `mm:ss` marker (the LLM writes one above each code
    snippet, see llama.py's system prompt) with the nearest REAL transcript
    segment start time from `segments` -- the LLM only paraphrases the
    "[mm:ss-mm:ss]" tags it was given and can drift to a plausible-looking
    time that isn't an actual moment in the video.
    """
    starts = sorted(
        start for start in (seg.payload.get("start") for seg in segments)
        if isinstance(start, (int, float))
    )
    if not starts:
        return answer

    def _replace(match):
        requested = int(match.group(1)) * 60 + int(match.group(2))
        nearest = min(starts, key=lambda s: abs(s - requested))
        minutes, secs = divmod(int(nearest), 60)
        return f"`{minutes}:{secs:02d}`"

    return _INLINE_TIMESTAMP_RE.sub(_replace, answer)


def _initialize_current_video_id() -> str | None:
    uploads = [path for path in UPLOAD_DIR.iterdir() if path.is_file()]
    if not uploads:
        return None
    latest_upload = max(uploads, key=lambda path: path.stat().st_mtime)
    return latest_upload.stem


def _load_transcript_text(video_id: str | None) -> str:
    if not video_id or not TRANSCRIPTS_PATH.exists():
        return ""

    try:
        with open(TRANSCRIPTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return ""

    transcript_data = data.get(video_id) if isinstance(data, dict) else None
    if transcript_data is None and isinstance(data, dict) and "segments" in data:
        transcript_data = data

    if not isinstance(transcript_data, dict):
        return ""

    segments = transcript_data.get("segments") or []
    texts = []
    for segment in segments:
        if isinstance(segment, dict):
            text = segment.get("text")
            if text:
                texts.append(text)

    return " ".join(texts)


def _load_transcript_record(video_id: str | None):
    if not TRANSCRIPTS_PATH.exists():
        return None

    try:
        with open(TRANSCRIPTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    if isinstance(data, dict):
        if video_id and isinstance(data.get(video_id), dict):
            return data[video_id]
        if "segments" in data:
            return data

    return None


def _find_uploaded_video(video_id: str | None):
    if not video_id:
        return None

    matches = [path for path in UPLOAD_DIR.iterdir() if path.is_file() and path.stem == video_id]
    if not matches:
        return None

    return max(matches, key=lambda path: path.stat().st_mtime)


def _ensure_text_artifacts(video_id: str | None):
    transcript_data = _load_transcript_record(video_id)
    transcript_has_text = bool(
        transcript_data
        and any(
            isinstance(segment, dict) and (segment.get("text") or "").strip()
            for segment in (transcript_data.get("segments") or [])
        )
    )

    embeddings_present = False
    if EMBEDDINGS_PATH.exists():
        try:
            with open(EMBEDDINGS_PATH, "r", encoding="utf-8") as f:
                embeddings_present = bool(json.load(f))
        except Exception:
            embeddings_present = False

    if transcript_has_text and not embeddings_present:
        embeddings = create_embeddings_from_transcript(transcript_data)
        _update_shared_json(EMBEDDINGS_PATH, embeddings)
        store_text_embeddings(video_id or "current", embeddings)
        return transcript_data, embeddings

    if transcript_has_text:
        return transcript_data, None

    uploaded_video = _find_uploaded_video(video_id)
    if not uploaded_video:
        return None, None

    output_audio = AUDIO_DIR / f"{uploaded_video.stem}.wav"
    transcript_for_json, embeddings, _ = _run_audio_pipeline(uploaded_video, output_audio)

    if transcript_for_json.get("segments"):
        _update_shared_json(TRANSCRIPTS_PATH, transcript_for_json)
    if embeddings:
        _update_shared_json(EMBEDDINGS_PATH, embeddings)

    return transcript_for_json, embeddings

# Runtime folder layout used by this API:
# - uploads/: original uploaded video files
# - audio/: extracted WAV audio files (same stem as video)
# - frames/: extracted image frames grouped by video stem
# - normalized/: re-encoded MP4s produced when a video needs format
#   normalization or its audio stream turns out to be corrupted
#   (see normalize_video's `force` fallback in _process_upload_job)
#
# Using Path(__file__).parent keeps paths stable regardless of where the
# process is started from.
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

print("UPLOAD_DIR EXISTS:", UPLOAD_DIR.exists())

AUDIO_DIR = Path(__file__).resolve().parent
AUDIO_DIR = BASE_DIR / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

FRAMES_DIR = Path(__file__).resolve().parent
FRAMES_DIR = BASE_DIR / "frames"
FRAMES_DIR.mkdir(parents=True, exist_ok=True)

NORMALIZED_DIR = BASE_DIR / "normalized"
NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)

# Shared JSON stores: every uploaded video's data is merged into these single
# fixed files (keyed by video stem) instead of writing a new JSON file named
# after each video's title.
TRANSCRIPTS_PATH = AUDIO_DIR / "output.json"
EMBEDDINGS_PATH = AUDIO_DIR / "output_embeddings.json"
FRAME_EMBEDDINGS_PATH = FRAMES_DIR / "output_frame_embeddings.json"

CURRENT_VIDEO_ID = _initialize_current_video_id()

app = FastAPI()

ensure_collections()  # Create Qdrant collections if they don't exist


def _warm_models():
    """Load the embedding models on a background thread at boot.

    Both load lazily on first use, so without this the first upload after every
    restart pays the text model inside the request. Measured on this machine:
    39.3s to load MiniLM against 0.29s to actually embed 52 segments. CLIP is
    the larger model and was landing inside the first /ask the same way.

    Sequential, not parallel: they are memory-heavy and running them at once
    just makes both slower.
    """
    try:
        warm_text_model()
        print("[Warmup] text embedding model ready")
    except Exception as exc:
        print(f"[Warmup] text embedding model failed: {exc}")

    try:
        warm_clip_model()
        print("[Warmup] CLIP model ready")
    except Exception as exc:
        print(f"[Warmup] CLIP model failed: {exc}")


threading.Thread(target=_warm_models, daemon=True).start()

# CORS is open here to simplify local frontend/backend integration.
# In production this should be restricted to known frontend origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Static mounts expose generated files directly over HTTP, so the frontend can
# render videos and access derived assets without a separate download endpoint.
# Example: /uploads/demo.mp4 maps to backend/uploads/demo.mp4 on disk.
app.mount(
    "/uploads",
    StaticFiles(directory=str(UPLOAD_DIR)),
    name="uploads"
) 

# Example: /audio/demo.wav maps to backend/audio/demo.wav.
app.mount(
    "/audio",
    StaticFiles(directory=str(AUDIO_DIR)),
    name="audio"
) 

# Example: /frames/demo/frame000001.jpg maps to backend/frames/demo/frame000001.jpg.
app.mount(
     "/frames",
     StaticFiles(directory=str(FRAMES_DIR)),
     name="frames"
) 

@app.get('/debug/qdrant-counts')
async def debug_qdrant_counts():
    return {
        "text_points": client.count(collection_name=TEXT_COLLECTION).count,
        "frame_points": client.count(collection_name=FRAME_COLLECTION).count,
    }

JOBS = {}


def _compact_transcript_for_json(transcript):
    """Persist only timestamped text segments instead of raw chunk metadata."""
    if isinstance(transcript, dict):
        data = transcript
    elif hasattr(transcript, "model_dump"):
        data = transcript.model_dump()
    elif hasattr(transcript, "dict"):
        data = transcript.dict()
    elif hasattr(transcript, "__dict__"):
        data = vars(transcript)
    else:
        data = {}

    def to_dict(item):
        if isinstance(item, dict):
            return item
        if hasattr(item, "model_dump"):
            return item.model_dump()
        if hasattr(item, "dict"):
            return item.dict()
        if hasattr(item, "__dict__"):
            return vars(item)
        return None

    raw_chunks = data.get("segments") or data.get("chunks") or []
    segments = []

    for item in raw_chunks:
        item_dict = to_dict(item)
        if not isinstance(item_dict, dict):
            continue

        start = item_dict.get("start")
        end = item_dict.get("end")
        timestamp = item_dict.get("timestamp")

        if isinstance(timestamp, (list, tuple)) and len(timestamp) == 2:
            if start is None:
                start = timestamp[0]
            if end is None:
                end = timestamp[1]

        segments.append(
            {
                "start": start,
                "end": end,
                "text": (item_dict.get("text") or "").strip(),
            }
        )

    compact = {"segments": segments}

    # Keep the language Whisper was pinned to, so answers don't have to re-derive
    # it from the transcript's script on every question.
    language = data.get("language")
    if language:
        compact["language"] = language

    return compact


def _update_shared_json(path: Path, data):
    """Overwrite the shared JSON file's contents with just this video's data.

    The frontend only supports one active video at a time, so each new
    upload should fully replace whatever was previously stored here (the
    raw segments/embeddings themselves, no video_id wrapper) rather than
    accumulating every video ever uploaded.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def _clear_previous_uploads(current_video):
    for file in UPLOAD_DIR.iterdir():
        if file.is_file() and file.name != current_video:
            file.unlink(missing_ok=True)


def _clear_previous_video_files(current_stem: str):
    """Remove on-disk audio/frame/normalized artifacts left behind by any
    video other than the one currently being processed.

    This app only keeps one active video's data at a time (same reasoning as
    clear_collections() and _update_shared_json() above), but audio/*.wav,
    frames/<stem>/, and normalized/*.mp4 were never being cleaned up, so old
    uploads just accumulated on disk indefinitely even though the JSON
    stores looked "current". This brings the filesystem in line with that
    same rule.
    """
    for wav_file in AUDIO_DIR.glob("*.wav"):
        if wav_file.stem != current_stem:
            wav_file.unlink(missing_ok=True)

    for frame_dir in FRAMES_DIR.iterdir():
        if frame_dir.is_dir() and frame_dir.name != current_stem:
            shutil.rmtree(frame_dir, ignore_errors=True)

    for normalized_file in NORMALIZED_DIR.glob("*.mp4"):
        if normalized_file.stem != f"{current_stem}_normalized":
            normalized_file.unlink(missing_ok=True)



def _set_job_status(job_id, status=None, stage=None, progress=None, error=None, result=None):
    job = JOBS.get(job_id, {})
    if status is not None:
        job["status"] = status
    if stage is not None:
        job["stage"] = stage
    if progress is not None:
        job["progress"] = int(max(0, min(100, progress)))
    if error is not None:
        job["error"] = error
    if result is not None:
        job["result"] = result
    JOBS[job_id] = job


def _run_audio_pipeline(video_path: Path, output_audio: Path, job_id=None):
    """Extract audio, transcribe it, and create/store text embeddings.

    Runs with detailed progress tracking. When job_id is given, pushes
    granular stage/progress updates as each step advances -- without this,
    the frontend's progress bar sat frozen at "extracting_audio" for the
    entire (often multi-minute) transcription pass, since that was the only
    status update between the start and the final "finalizing" jump.
    """
    transcript_error = None
    transcript_for_json = {"segments": []}
    embeddings = []

    try:
        t_audio = time.perf_counter()
        extract_audio(video_path, output_audio)
        print(f"✓ Audio extraction complete for {video_path.stem}  [{time.perf_counter()-t_audio:.1f}s]")
    except RuntimeError as e:
        print(f"✗ Direct audio extraction failed for {video_path.stem}: {e}")
        try:
            normalized_video = normalize_video(video_path, NORMALIZED_DIR, force=True)
            print(f"↻ Retrying audio extraction from normalized video: {normalized_video}")
            extract_audio(normalized_video, output_audio)
        except Exception as normalize_error:
            transcript_error = f"Could not extract audio: {normalize_error}"
            print(transcript_error)
            output_audio = None

    try:
        if output_audio and Path(output_audio).exists():
            import time as _time
            t0 = _time.perf_counter()
            print(f"✓ Starting transcription for {video_path.stem}...")

            if job_id:
                _set_job_status(job_id, stage="transcribing_audio", progress=30)

            def _on_transcribe_progress(completed, total):
                if job_id and total:
                    _set_job_status(
                        job_id,
                        stage="transcribing_audio",
                        progress=30 + int(45 * completed / total),
                    )

            transcript = transcribe_audio_chunks(str(output_audio), on_progress=_on_transcribe_progress)
            transcript_for_json = _compact_transcript_for_json(transcript)
            print(f"✓ Transcription complete: {len(transcript_for_json.get('segments', []))} segments  [{_time.perf_counter()-t0:.1f}s]")

            if job_id:
                _set_job_status(job_id, stage="embedding_text", progress=80)

            t1 = _time.perf_counter()
            print(f"↻ Creating text embeddings...")
            embeddings = create_embeddings_from_transcript(transcript_for_json)
            store_text_embeddings(video_path.stem, embeddings)
            print(f"✓ Embeddings stored: {len(embeddings)} vectors  [{_time.perf_counter()-t1:.1f}s]")

            if job_id:
                _set_job_status(job_id, stage="embedding_text", progress=90)
    except Exception as e:
        transcript_error = str(e)
        print(f"✗ Transcription/embedding failed for {video_path.stem}: {e}")

    return transcript_for_json, embeddings, transcript_error


def _run_frame_pipeline(
    video_path: Path,
    output_frames_dir: Path,
    frame_interval_sec,
    frame_strategy,
    scene_threshold,
    keyframes_only,
    frame_max_width,
):
    """Extract frames and create/store CLIP embeddings.

    Runs on its own thread inside _process_upload_job, in parallel with
    _run_audio_pipeline. Nothing here depends on the transcript, so it can
    run fully concurrently with the audio/text pipeline.
    """
    frame_count, frame_timestamps = extract_frames(
        video_path,
        output_frames_dir,
        interval_seconds=frame_interval_sec,
        extraction_mode=frame_strategy,
        scene_threshold=scene_threshold,
        keyframes_only=keyframes_only,
        max_width=frame_max_width,
    )

    frame_embeddings = create_frame_embeddings(
        str(output_frames_dir),
        timestamps=frame_timestamps,
    )

    store_frame_embeddings(video_path.stem, frame_embeddings)

    return frame_count, frame_embeddings


def _process_upload_job(
    job_id,
    filename,
    video_path,
    frame_interval_sec,
    frame_strategy,
    scene_threshold,
    keyframes_only,
    frame_max_width,
    start_time=None,
):
    if start_time is None:
        start_time = time.perf_counter()
    try:
        video_path = Path(video_path)
        global CURRENT_VIDEO_ID
        CURRENT_VIDEO_ID = video_path.stem

        # This app only keeps one active video's data at a time -- wipe
        # whatever was stored for the previous video before processing the
        # new one, so /ask never mixes results across uploads.
        clear_collections()
        _clear_previous_video_files(video_path.stem)
        _clear_previous_uploads(video_path.name)

        # Ensure the file the frontend actually plays is seek-friendly
        # (faststart MP4 / H.264 / AAC). Otherwise the browser's seek bar
        # can land on the wrong timestamp when dragged, since the moov atom
        # (the index mapping time -> byte offset) may sit at the end of the
        # raw upload.
        t_normalize = time.perf_counter()
        try:
            playable_video = Path(normalize_video(video_path, NORMALIZED_DIR))
            print(f"✓ Faststart prep done  [{time.perf_counter()-t_normalize:.1f}s]")
            if playable_video != video_path:
                served_filename = f"{video_path.stem}.mp4"
                served_path = UPLOAD_DIR / served_filename
                shutil.copyfile(playable_video, served_path)
                if video_path.suffix.lower() != ".mp4":
                    video_path.unlink(missing_ok=True)
                filename = served_filename
                video_path = served_path
        except Exception as prep_error:
            print(f"⚠ Could not prepare video for playback  [{time.perf_counter()-t_normalize:.1f}s], serving original file: {prep_error}")

        output_audio = AUDIO_DIR / f"{video_path.stem}.wav"

        # Only extract and process audio (no frame extraction for speed)
        _set_job_status(job_id, status="processing", stage="extracting_audio", progress=25)

        transcript_for_json, embeddings, transcript_error = _run_audio_pipeline(video_path, output_audio, job_id=job_id)

        _set_job_status(job_id, status="processing", stage="finalizing", progress=95)

        _update_shared_json(TRANSCRIPTS_PATH, transcript_for_json)
        _update_shared_json(EMBEDDINGS_PATH, embeddings)

        total_time_sec = time.perf_counter() - start_time

        result = {
            "filename": filename,
            "file_url": f"/uploads/{filename}",
            "audio_url": f"/audio/{video_path.stem}.wav",
            "video_id": video_path.stem,
            "transcript_url": "/audio/output.json",
            "embeddings_url": "/audio/output_embeddings.json",
            "transcript": transcript_for_json,
            "transcript_error": transcript_error,
            "frame_count": 0,
            "total_time_sec": round(total_time_sec, 1),
        }
        _set_job_status(job_id, status="completed", stage="completed", progress=100, result=result)

        # Logged last, on purpose: if the console cannot encode this line, a
        # successful job must not be turned into a failed one.
        print(f"[Pipeline] Upload-to-embeddings finished for {video_path.stem} in {total_time_sec:.1f}s")
    except Exception as e:
        total_time_sec = time.perf_counter() - start_time
        # Recorded before logging, for the same reason. Logging first meant a
        # failing print skipped this call, so the job reported the print's
        # encoding error instead of the actual cause.
        _set_job_status(job_id, status="failed", stage="failed", progress=100, error=str(e))
        print(f"[Pipeline] Upload pipeline failed after {total_time_sec:.1f}s: {e}")


class YoutubeRequest(BaseModel):
    url: str
    frame_interval_sec: float = 5.0
    frame_strategy: str = "scene"
    scene_threshold: float = 0.35
    keyframes_only: bool = True
    frame_max_width: int = 640


@app.post('/download-youtube/')
async def download_youtube(req: YoutubeRequest, background_tasks: BackgroundTasks):
    """Download a YouTube video via yt-dlp, save it to uploads/, then process
    it through the same background pipeline as a regular file upload."""
    import re as _re
    import subprocess
    import sys

    start_time = time.perf_counter()

    url = (req.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="No URL provided")

    if not _re.search(r"(youtube\.com|youtu\.be)", url):
        raise HTTPException(status_code=400, detail="URL does not look like a YouTube link")

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "job_id": job_id,
        "status": "processing",
        "stage": "downloading",
        "progress": 3,
        "error": None,
        "result": None,
    }

    def _download_and_process():
        import subprocess
        import sys

        # Resolve yt-dlp from the same Python env so it works regardless of
        # whether the venv Scripts/ folder is on the system PATH.
        scripts_dir = Path(sys.executable).parent
        yt_dlp_exe = scripts_dir / "yt-dlp.exe"
        if not yt_dlp_exe.exists():
            yt_dlp_exe = scripts_dir / "yt-dlp"          # Linux / macOS
        if not yt_dlp_exe.exists():
            _set_job_status(job_id, status="failed", stage="failed", progress=100,
                            error="yt-dlp not found in the Python environment")
            return

        try:
            _set_job_status(job_id, stage="downloading", progress=5)

            # Use a fixed UUID-based filename so we always know exactly where
            # the file lands — no stdout parsing, no fallback to "newest file".
            file_stem = f"yt_{uuid.uuid4().hex[:12]}"
            out_path = UPLOAD_DIR / f"{file_stem}.mp4"

            # YouTube is rotating client/format availability frequently.
            # Hard-coding a narrow stream selector (like "bv*[height<=480]+ba")
            # makes the downloader brittle and triggers the 403s you are seeing.
            # Prefer generic best formats first, then fall back to a more general
            # combined-video/audio selector, instead of forcing a single client.
            format_attempts = [
                "best[ext=mp4]/best",
                "bestvideo+bestaudio/best",
                "bv*+ba/b",
            ]

            result = None
            for idx, fmt in enumerate(format_attempts):
                _set_job_status(job_id, stage="downloading", progress=5 + (idx * 3),
                                error=f"Trying format {idx + 1}/{len(format_attempts)}")

                print(f"[YouTube] Attempting format={fmt}")

                result = subprocess.run(
                    [
                        str(yt_dlp_exe),
                        "--no-playlist",
                        "--no-warnings",
                        "--extractor-args", "youtube:player_client=android,web,ios",
                        "-f", fmt,
                        "--merge-output-format", "mp4",
                        "--retries", "10",
                        "--fragment-retries", "10",
                        "--socket-timeout", "30",
                        "--concurrent-fragments", "4",
                        "-o", str(out_path),
                        url,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=180,
                )

                if result.returncode == 0 and out_path.exists():
                    file_size_mb = out_path.stat().st_size / 1024 / 1024
                    print(f"[YouTube] Downloaded successfully ({fmt}): {file_size_mb:.1f} MB")
                    break
                else:
                    stderr_snippet = (result.stderr or "")[-150:] if result.stderr else "Unknown"
                    print(f"[YouTube] {fmt} failed: {stderr_snippet}")

            if result is None or result.returncode != 0:
                stderr = (result.stderr or "").strip() if result else "Unknown error"
                _set_job_status(job_id, status="failed", stage="failed", progress=100,
                                error=f"Download failed (all formats): {stderr[-200:]}")
                return

            if not out_path.exists() or out_path.stat().st_size == 0:
                _set_job_status(job_id, status="failed", stage="failed", progress=100,
                                error="Download succeeded but output file is missing or empty")
                return

            _set_job_status(job_id, stage="processing_audio_and_frames", progress=15)
            _process_upload_job(
                job_id,
                out_path.name,
                str(out_path),
                req.frame_interval_sec,
                req.frame_strategy,
                req.scene_threshold,
                req.keyframes_only,
                req.frame_max_width,
                start_time,
            )
        except subprocess.TimeoutExpired:
            _set_job_status(job_id, status="failed", stage="failed", progress=100,
                            error="Download timed out (tried 720p → 480p → any MP4)")
        except Exception as exc:
            _set_job_status(job_id, status="failed", stage="failed", progress=100, error=str(exc))

    background_tasks.add_task(_download_and_process)

    return {
        "job_id": job_id,
        "status": "processing",
        "stage": "downloading",
        "progress": 3,
        "status_url": f"/upload-status/{job_id}",
    }


@app.post('/uploadfile/')
async def create_upload_file(
    background_tasks: BackgroundTasks,
    file_upload: UploadFile,
    frame_interval_sec: float = 10.0,
    frame_strategy: str = "scene",
    scene_threshold: float = 0.35,
    keyframes_only: bool = True,
    frame_max_width: int = 640,
):
    """Process one uploaded video and return URLs for all generated artifacts.

    Request flow:
    1) Save uploaded bytes under uploads/<original_filename>
    2) Extract WAV audio into audio/<video_stem>.wav
    3) Extract frames into frames/<video_stem>/frameXXXXXX.jpg
    4) Return relative URLs consumed by the frontend

    frame_interval_sec controls temporal sampling density in interval mode.
    frame_strategy selects extraction style: "scene" or "interval".
    scene_threshold controls FFmpeg scene sensitivity in scene mode.
    keyframes_only trades timing uniformity for speed.
    frame_max_width limits frame width to reduce CPU/disk cost.
    """

    start_time = time.perf_counter()

    if not file_upload.filename:
        raise HTTPException(status_code=400, detail="Missing uploaded filename")

    # Stream upload to disk to avoid reading very large files into memory.
    save_to = UPLOAD_DIR / file_upload.filename
    print("UPLOAD_DIR:", UPLOAD_DIR)
    print("Saving to:", save_to)
    with open(save_to, 'wb') as f:
        while True:
            chunk = await file_upload.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "job_id": job_id,
        "status": "processing",
        "stage": "queued",
        "progress": 5,
        "error": None,
        "result": None,
    }

    background_tasks.add_task(
        _process_upload_job,
        job_id,
        file_upload.filename,
        str(save_to),
        frame_interval_sec,
        frame_strategy,
        scene_threshold,
        keyframes_only,
        frame_max_width,
        start_time,
    )

    return {
        "job_id": job_id,
        "status": "processing",
        "stage": "queued",
        "progress": 5,
        "status_url": f"/upload-status/{job_id}",
    }


@app.get('/upload-status/{job_id}')
async def get_upload_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "stage": job.get("stage"),
        "progress": job.get("progress", 0),
        "error": job.get("error"),
        "result": job.get("result"),
    }


@app.post("/ask")
async def ask(req: Question):
    try:
        question = req.question
        requested_video_id = req.video_id
        history = (req.history or [])[-6:]

        current_video_id = requested_video_id or CURRENT_VIDEO_ID

        _ensure_text_artifacts(current_video_id)

        summary_mode = _is_summary_request(question)
        answer_language = _detect_question_language(question)

        if summary_mode:
            # For summaries, fetch ALL stored segments in chronological order
            # instead of doing a single semantic search — that way the LLM
            # sees the whole video, not just segments close to the word
            # "summary" in embedding space.
            all_segments = scroll_all_text(video_id=current_video_id)
            transcript_text = " ".join(
                (p.payload.get("text") or "").strip()
                for p in all_segments
                if (p.payload.get("text") or "").strip()
            )
            if transcript_text:
                answer_language = _detect_transcript_language(transcript_text)

            # Cap at 120 segments so we stay within context window; they are
            # already sorted chronologically so even-spacing gives coverage.
            if len(all_segments) > 120:
                step = len(all_segments) / 120
                all_segments = [all_segments[int(i * step)] for i in range(120)]

            text_results = all_segments
            sorted_results = all_segments
            context_candidates = all_segments
        else:
            query_embedding = embed_query(question)
            text_results = search_text(query_embedding, limit=12, video_id=current_video_id)
            CONTEXT_MIN_SCORE = 0.15
            context_candidates = [
                r for r in text_results if r.score >= CONTEXT_MIN_SCORE
            ] or text_results[:4]

            # Include each match's immediate chronological neighbors so the
            # LLM sees full, continuous explanations (e.g. an automaton's
            # states, a data structure's operations) instead of isolated
            # sentences that happened to score highest individually.
            all_video_segments = scroll_all_text(video_id=current_video_id)
            expanded_candidates = _expand_with_neighbors(context_candidates, all_video_segments, window=1)
            sorted_results = sorted(expanded_candidates, key=lambda r: r.payload.get("start") or 0)

        def _format_ts(seconds):
            if seconds is None:
                return "?"
            minutes, secs = divmod(int(seconds), 60)
            return f"{minutes}:{secs:02d}"

        context = "\n".join(
            f"[{_format_ts(r.payload.get('start'))}-{_format_ts(r.payload.get('end'))}] {r.payload.get('text', '').strip()}"
            for r in sorted_results
            if r.payload.get("text")
        )
        print("Context:", context)

        if summary_mode and context:
            answer_language = _detect_transcript_language(context)

        transcript_available = bool(context.strip())

        try:
            answer = ask_llama(
                question=question,
                context=context,
                history=history,
                answer_language=answer_language,
                summary_mode=summary_mode,
                transcript_available=transcript_available,
            )
        except Exception as e:
            print(f"LLM error: {e}")
            raise HTTPException(status_code=502, detail=f"LLM provider error: {e}")

        # The LLM writes an inline `mm:ss` marker (in backticks) above any code
        # snippet, but it's just paraphrasing the excerpt tags in `context` --
        # it can drift to a nearby-sounding time that isn't an actual segment.
        # Snap every such marker to the closest REAL segment start from the
        # same excerpts the answer was grounded in, so the jump link it
        # produces always lands on an actual transcript moment.
        answer = _snap_inline_timestamps(answer, sorted_results)

        print(answer)

        frame_query_text = _clip_query_for_summary() if summary_mode else question
        frame_query_embedding = embed_text_clip(frame_query_text)
        frame_candidates = search_frames(frame_query_embedding, limit=20, video_id=current_video_id)

        for r in frame_candidates:
            print(f"CLIP score={r.score:.4f}  {r.payload.get('frame')}")

        TEXT_MIN_SCORE = 0.50
        CLIP_MIN_SCORE = 0.18

        # scroll results (summary mode) have no .score attribute
        strong_text = [r for r in text_results if getattr(r, 'score', 1.0) >= TEXT_MIN_SCORE]
        if text_results:
            top_score = getattr(text_results[0], 'score', None)
            score_str = f"top score={top_score:.4f}" if top_score is not None else "(no scores)"
            print(f"Strong text hits: {len(strong_text)}  {score_str}")

        if strong_text and frame_candidates:
            selected: dict = {}
            for seg in strong_text:
                mid = ((seg.payload.get("start") or 0) + (seg.payload.get("end") or 0)) / 2
                closest = min(
                    frame_candidates,
                    key=lambda f: abs((f.payload.get("timestamp") or 0) - mid),
                )
                selected[closest.id] = closest

            relevant_frames = sorted(selected.values(), key=lambda r: r.payload.get("timestamp") or 0)
        else:
            if len(frame_candidates) >= 2:
                scores = [r.score for r in frame_candidates]
                gaps = [scores[i] - scores[i + 1] for i in range(len(scores) - 1)]
                largest_gap_pos = gaps.index(max(gaps))
                cutoff = scores[largest_gap_pos + 1]
                relevant_frames = [
                    r for r in frame_candidates
                    if r.score > cutoff and r.score >= CLIP_MIN_SCORE
                ]
                if not relevant_frames and frame_candidates[0].score >= CLIP_MIN_SCORE:
                    relevant_frames = [frame_candidates[0]]
            else:
                relevant_frames = [r for r in frame_candidates if r.score >= CLIP_MIN_SCORE]

        for r in relevant_frames:
            ts = r.payload.get("timestamp")
            ts_str = f"{ts:.2f}" if ts is not None else "N/A"
            print(f"-> frame: {r.payload.get('frame')}  ts={ts_str}")

        max_response_timestamps = 8  # hard cap so a very long tail of similar scores can't return everything

        if summary_mode:
            # Summaries intentionally cover the whole video; just cap count.
            top_matches = sorted_results[:max_response_timestamps]
        else:
            # Same score-filtered set used to build the LLM's context, so
            # badges always match what the answer was actually grounded in.
            RELEVANT_TS_MIN_SCORE = 0.30
            relevant_for_timestamps = [
                r for r in context_candidates if getattr(r, "score", 0) >= RELEVANT_TS_MIN_SCORE
            ]
            if not relevant_for_timestamps:
                # Nothing cleared the bar -- fall back to the single best match
                # instead of showing no timestamps at all.
                best = max(context_candidates, key=lambda r: getattr(r, "score", 0), default=None)
                relevant_for_timestamps = [best] if best is not None else []

            # Adaptive cutoff instead of a fixed top-N: keep every match whose
            # score is within a relative band of the single best score. A pure
            # "largest gap" cutoff was too fragile -- one standout top match
            # (e.g. a near word-for-word segment) creates a huge first gap and
            # wrongly discards a whole cluster of other equally relevant hits
            # sitting just below it.
            by_score = sorted(relevant_for_timestamps, key=lambda r: getattr(r, "score", 0), reverse=True)
            RELATIVE_SCORE_BAND = 0.85  # keep anything scoring >= 85% of the top score
            top_score = getattr(by_score[0], "score", 0) if by_score else 0
            by_score = [r for r in by_score if getattr(r, "score", 0) >= top_score * RELATIVE_SCORE_BAND]
            top_matches = sorted(by_score[:max_response_timestamps], key=lambda r: r.payload.get("start") or 0)

        answer_timestamps = [] if summary_mode else sorted(
            [
                {"start": r.payload.get("start"), "end": r.payload.get("end")}
                for r in top_matches
                if r.payload.get("start") is not None
            ],
            key=lambda t: t["start"],
        )
        return {
            "answer": answer,
            "timestamps": answer_timestamps,
            "text_results": [
                {
                    "text": r.payload.get("text"),
                    "start": r.payload.get("start"),
                    "end": r.payload.get("end"),
                    "score": getattr(r, 'score', None),
                }
                for r in text_results
            ],
            "frame_results": [
                {
                    "frame": r.payload.get("frame"),
                    "timestamp": r.payload.get("timestamp"),
                    "score": r.score,
                }
                for r in relevant_frames
            ],
        }
    except HTTPException:
        raise
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))