from fastapi import FastAPI, UploadFile, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from video_processing import extract_audio
from video_processing import extract_frames
# from whisper import transcribe_audio
import json
import uuid
# from bert import create_embeddings
from frame_embeddings import create_frame_embeddings
from qdrant_store import ensure_collections, store_text_embeddings, store_frame_embeddings

from qdrant_store import client, TEXT_COLLECTION, FRAME_COLLECTION


# Runtime folder layout used by this API:
# - uploads/: original uploaded video files
# - audio/: extracted WAV audio files (same stem as video)
# - frames/: extracted image frames grouped by video stem
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
        _set_job_status(job_id, status="processing", stage="extracting_audio", progress=20)

        output_audio = AUDIO_DIR / f"{video_path.stem}.wav"
        extract_audio(video_path, output_audio)

        # _set_job_status(job_id, status="processing", stage="transcribing", progress=50)
        # transcript = transcribe_audio(str(output_audio))
        #
        # transcript_path = AUDIO_DIR / f"{video_path.stem}.json"
        # transcript_for_json = _compact_transcript_for_json(transcript)
        # with open(transcript_path, "w", encoding="utf-8") as f:
        #     json.dump(transcript_for_json, f, indent=2, ensure_ascii=False)
        #
        # _set_job_status(job_id, status="processing", stage="creating_embeddings", progress=65)
        # embeddings = create_embeddings(str(transcript_path))
        #
        # store_text_embeddings(video_path.stem, embeddings)
        #
        # embedding_path = AUDIO_DIR / f"{video_path.stem}_embeddings.json"
        # with open(embedding_path, "w", encoding="utf-8") as f:
        #     json.dump(embeddings, f, indent=2, ensure_ascii=False)

        transcript = None

        # _set_job_status(job_id, status="processing", stage="extracting_frames", progress=80)
        # output_frames_dir = FRAMES_DIR / video_path.stem
        # frame_count, frame_timestamps = extract_frames(
        #     video_path,
        #     output_frames_dir,
        #     interval_seconds=frame_interval_sec,
        #     extraction_mode=frame_strategy,
        #     scene_threshold=scene_threshold,
        #     keyframes_only=keyframes_only,
        #     max_width=frame_max_width,
        # )

        # _set_job_status(job_id, status="processing", stage="creating_frame_embeddings", progress=90)
        # frame_embeddings = create_frame_embeddings(
        #     str(output_frames_dir),
        #     timestamps=frame_timestamps,
        # )

        # store_frame_embeddings(video_path.stem, frame_embeddings)

        # frame_embedding_path = output_frames_dir / f"{video_path.stem}_frame_embeddings.json"
        # with open(frame_embedding_path, "w", encoding="utf-8") as f:
        #     json.dump(frame_embeddings, f, indent=2, ensure_ascii=False)

        frame_count = 0
        frame_timestamps = []
        frame_embeddings = []

        result = {
            "filename": filename,
            "file_url": f"/uploads/{filename}",
            "audio_url": f"/audio/{video_path.stem}.wav",
            "transcript_url": f"/audio/{video_path.stem}.json",
            "embeddings_url": f"/audio/{video_path.stem}_embeddings.json",
            "frame_embeddings_url": f"/frames/{video_path.stem}/{video_path.stem}_frame_embeddings.json",
            "transcript": transcript,
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