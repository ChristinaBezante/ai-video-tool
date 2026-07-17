from fastapi import FastAPI, UploadFile, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import shutil
from concurrent.futures import ThreadPoolExecutor
from fastapi.staticfiles import StaticFiles
from video_processing import extract_audio
from video_processing import extract_frames, normalize_video
from whisper import transcribe_audio_chunks
import json
import uuid
from bert import create_embeddings_from_transcript, embed_query
from frame_embeddings import create_frame_embeddings, embed_text_clip
from qdrant_store import ensure_collections, store_text_embeddings, store_frame_embeddings, clear_collections
from qdrant_store import client, TEXT_COLLECTION, FRAME_COLLECTION, search_text, search_frames

from llama import ask_llama

from pydantic import BaseModel

class Question(BaseModel):
    question: str

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

app = FastAPI()

ensure_collections()  # Create Qdrant collections if they don't exist

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

    return {"segments": segments}


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


def _run_audio_pipeline(video_path: Path, output_audio: Path):
    """Extract audio, transcribe it, and create/store text embeddings.

    Runs on its own thread inside _process_upload_job, in parallel with
    _run_frame_pipeline. Transcription/embedding failures are caught and
    returned as an error string rather than raised, so a flaky ASR call
    doesn't take down frame processing too -- frames and audio are each
    useful on their own.
    """
    transcript_error = None
    transcript_for_json = {"segments": []}
    embeddings = []

    try:
        extract_audio(video_path, output_audio)
    except RuntimeError as e:
        transcript_error = f"Could not extract audio: {e}"
        print(transcript_error)
        output_audio = None

    try:
        if output_audio and Path(output_audio).exists():
            transcript = transcribe_audio_chunks(str(output_audio))
            transcript_for_json = _compact_transcript_for_json(transcript)
            embeddings = create_embeddings_from_transcript(transcript_for_json)
            store_text_embeddings(video_path.stem, embeddings)
    except Exception as e:
        transcript_error = str(e)
        print(f"Transcription/embedding failed for {video_path.stem}, continuing without it: {e}")

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
):
    try:
        video_path = Path(video_path)

        # This app only keeps one active video's data at a time -- wipe
        # whatever was stored for the previous video before processing the
        # new one, so /ask never mixes results across uploads.
        clear_collections()
        _clear_previous_video_files(video_path.stem)
        _clear_previous_uploads(video_path.name)

        output_audio = AUDIO_DIR / f"{video_path.stem}.wav"
        output_frames_dir = FRAMES_DIR / video_path.stem

        # Audio (extract -> transcribe -> embed) and frames (extract -> CLIP
        # embed) don't depend on each other, so run them concurrently instead
        # of sequentially. This is the main lever for cutting total upload
        # processing time, since the audio pipeline is network/ASR-bound and
        # the frame pipeline is CPU/GPU-bound -- they don't compete for the
        # same resource.
        _set_job_status(job_id, status="processing", stage="processing_audio_and_frames", progress=20)

        with ThreadPoolExecutor(max_workers=2) as executor:
            audio_future = executor.submit(_run_audio_pipeline, video_path, output_audio)
            frame_future = executor.submit(
                _run_frame_pipeline,
                video_path,
                output_frames_dir,
                frame_interval_sec,
                frame_strategy,
                scene_threshold,
                keyframes_only,
                frame_max_width,
            )

            # .result() blocks until that future's thread finishes, but both
            # threads are already running concurrently by this point.
            transcript_for_json, embeddings, transcript_error = audio_future.result()
            frame_count, frame_embeddings = frame_future.result()

        _set_job_status(job_id, status="processing", stage="finalizing", progress=95)

        _update_shared_json(TRANSCRIPTS_PATH, transcript_for_json)
        _update_shared_json(EMBEDDINGS_PATH, embeddings)
        _update_shared_json(FRAME_EMBEDDINGS_PATH, frame_embeddings)

        result = {
            "filename": filename,
            "file_url": f"/uploads/{filename}",
            "audio_url": f"/audio/{video_path.stem}.wav",
            "video_id": video_path.stem,
            "transcript_url": "/audio/output.json",
            "embeddings_url": "/audio/output_embeddings.json",
            "frame_embeddings_url": "/frames/output_frame_embeddings.json",
            "transcript": transcript_for_json,
            "transcript_error": transcript_error,
            "frame_count": frame_count,
            "frames_url_prefix": f"/frames/{video_path.stem}/",
            "frame_settings": {
                "interval_seconds": frame_interval_sec,
                "strategy": frame_strategy,
                "scene_threshold": scene_threshold,
                "keyframes_only": keyframes_only,
                "max_width": frame_max_width,
            },
        }
        _set_job_status(job_id, status="completed", stage="completed", progress=100, result=result)
    except Exception as e:
        _set_job_status(job_id, status="failed", stage="failed", progress=100, error=str(e))

@app.post('/uploadfile/')
async def create_upload_file(
    background_tasks: BackgroundTasks,
    file_upload: UploadFile,
    frame_interval_sec: float = 5.0,
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

    # 1. SBERT embedding -> search text segments
    query_embedding = embed_query(question)
    text_results = search_text(query_embedding)

    for result in text_results:
        print(result.payload)

    sorted_results = sorted(text_results, key=lambda r: r.payload.get("start") or 0)
    context = "\n".join(r.payload["text"] for r in sorted_results)
    print("Context:", context)

    try:
        answer = ask_llama(question=question, context=context)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM provider error: {e}")

    print(answer)

    # 2. CLIP embedding -> search frames by visual similarity
    frame_query_embedding = embed_text_clip(question)
    frame_candidates = search_frames(frame_query_embedding, limit=20)

    for r in frame_candidates:
        print(f"CLIP score={r.score:.4f}  {r.payload.get('frame')}")

    # 3. Hybrid frame selection
    #
    #    SEMANTIC query (topic is spoken in the video -- high SBERT score):
    #      For each relevant text segment find the temporally closest frame.
    #      This gives a direct text-segment -> frame correspondence and works
    #      even when frames are sparse.
    #
    #    VISUAL query (topic not in transcript -- low SBERT scores, e.g. "circle"):
    #      Use CLIP gap detection to find visually matching frames.

    TEXT_MIN_SCORE = 0.50   # SBERT cosine threshold to consider a text hit relevant
    CLIP_MIN_SCORE = 0.18   # hard floor for CLIP-only results

    strong_text = [r for r in text_results if r.score >= TEXT_MIN_SCORE]
    print(f"Strong text hits: {len(strong_text)}  "
          f"top score={text_results[0].score:.4f}" if text_results else "")

    if strong_text and frame_candidates:
        # Map each text segment to its nearest frame (by timestamp distance)
        selected: dict = {}
        for seg in strong_text:
            mid = ((seg.payload.get("start") or 0) + (seg.payload.get("end") or 0)) / 2
            closest = min(
                frame_candidates,
                key=lambda f: abs((f.payload.get("timestamp") or 0) - mid),
            )
            selected[closest.id] = closest  # deduplicate via dict

        relevant_frames = sorted(selected.values(),
                                 key=lambda r: r.payload.get("timestamp") or 0)
    else:
        # Visual query -- use CLIP gap detection
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

    # Surface only the two most relevant text segments (text_results is already
    # sorted by Qdrant similarity score, descending), then order those
    # chronologically so the frontend shows them in the order they occur.
    top_matches = sorted(text_results, key=lambda r: r.score, reverse=True)[:2]
    answer_timestamps = sorted(
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
                "score": r.score,
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