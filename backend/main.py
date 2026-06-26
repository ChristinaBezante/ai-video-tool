from fastapi import FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from video_processing import extract_audio
from video_processing import extract_frames

# Runtime folder layout used by this API:
# - uploads/: original uploaded video files
# - audio/: extracted WAV audio files (same stem as video)
# - frames/: extracted image frames grouped by video stem
#
# Using Path(__file__).parent keeps paths stable regardless of where the
# process is started from (important for local dev vs container runs).
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

@app.post('/uploadfile/')
async def create_upload_file(
    file_upload: UploadFile,
    frame_interval_sec: float = 5.0,
    keyframes_only: bool = True,
    frame_max_width: int = 640,
):
    """Process one uploaded video and return URLs for all generated artifacts.

    Request flow:
    1) Save uploaded bytes under uploads/<original_filename>
    2) Extract WAV audio into audio/<video_stem>.wav
    3) Extract frames into frames/<video_stem>/frameXXXXXX.jpg
    4) Return relative URLs consumed by the frontend

    frame_interval_sec controls temporal sampling density.
    keyframes_only trades timing uniformity for speed.
    frame_max_width limits frame width to reduce CPU/disk cost.
    """

    # FastAPI UploadFile gives a file-like object; we read bytes once and store
    # the exact uploaded payload as-is inside UPLOAD_DIR.
    data = await file_upload.read()
    save_to = UPLOAD_DIR / file_upload.filename
    print("UPLOAD_DIR:", UPLOAD_DIR)
    print("Saving to:", save_to)
    with open(save_to, 'wb') as f:
        f.write(data)

    # video_path is the single source file used by both processing stages.
    video_path = save_to

    # Keep naming consistent: demo.mp4 -> audio/demo.wav.
    output_audio = AUDIO_DIR / f"{save_to.stem}.wav"
    extract_audio(video_path, output_audio)

    # Frames are grouped per upload stem to avoid collisions between videos.
    output_frames_dir = FRAMES_DIR / save_to.stem
    frame_count = extract_frames(
        video_path,
        output_frames_dir,
        interval_seconds=frame_interval_sec,
        keyframes_only=keyframes_only,
        max_width=frame_max_width,
    )

    print("File exists:", save_to.exists())
    # API returns relative URLs. Frontend prefixes with backend base URL,
    # for example: http://localhost:8000 + file_url.
    return {
        "filename": file_upload.filename,
        "file_url": f"/uploads/{file_upload.filename}",
        "audio_url": f"/audio/{save_to.stem}.wav",
        "frame_count": frame_count,
        "frames_url_prefix": f"/frames/{save_to.stem}/",
        "frame_settings": {
            "interval_seconds": frame_interval_sec,
            "keyframes_only": keyframes_only,
            "max_width": frame_max_width,
        },
    }