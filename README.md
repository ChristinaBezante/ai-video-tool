# AI Video Tool

Upload a video (or paste a YouTube link) and chat with it. The backend transcribes the audio, embeds the transcript (and key frames) into a vector store, and answers natural-language questions about the video — with timestamps, code snippets, and Mermaid diagrams when relevant.

## Features

- **Video upload or YouTube import** — drop a file or paste a link; processing runs as a background job with live progress polling.
- **Automatic transcription** — audio is chunked and transcribed in parallel (OpenAI Whisper API, with Hugging Face fallback).
- **Semantic search over transcript + frames** — transcript segments are embedded locally (`sentence-transformers`) and stored in Qdrant; keyframes are embedded with CLIP for visual search.
- **Conversational Q&A (`/ask`)** — retrieval-augmented answers that cite the exact `[mm:ss–mm:ss]` moments in the video the answer is grounded in, with multi-turn conversation history.
- **Greek + English support** — detects the question/transcript language and answers accordingly.
- **Rich answers** — inline timestamp badges you can click to seek, fenced code snippets for coding tutorials, and auto-generated Mermaid diagrams for data-structure questions.
- **Custom video player** — video.js-based player with a themed overlay UI and accurate seeking (faststart/moov-atom normalization on upload).

## Tech Stack

**Backend** — FastAPI, Qdrant (local, file-based), ffmpeg, OpenAI Whisper API, `sentence-transformers`, CLIP (`transformers`/`torch`), `yt-dlp`.

**Frontend** — React 19 + Vite, video.js, `react-markdown`, Mermaid, Framer Motion / GSAP / three.js for visual effects.

## Project Structure

```
backend/
  main.py              FastAPI app, upload/ask endpoints, pipeline orchestration
  video_processing.py  ffmpeg audio extraction, frame extraction, video normalization
  whisper.py           Chunked/parallel audio transcription
  bert.py              Transcript text embeddings (sentence-transformers)
  frame_embeddings.py  Frame/CLIP embeddings
  qdrant_store.py       Qdrant collections, storage, and search
  llama.py             LLM prompt + answer generation
  uploads/             Saved/normalized video files (served at /uploads)
  audio/               Extracted audio + transcript/embedding JSON
  frames/              Extracted keyframes + embeddings
  qdrant_data/         Local Qdrant storage

frontend/
  src/components/      React UI (video player, chatbot, upload flow, etc.)
  src/styles/          Component CSS
```

## Prerequisites

- Python 3.11+ (a project virtual environment is recommended)
- Node.js 18+
- [ffmpeg](https://ffmpeg.org/) available on your `PATH`
- An OpenAI API key (for transcription + chat completions)

## Setup

### Backend

```powershell
cd backend
python -m venv ../.venv
..\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create a `.env` file in `backend/` with:

```
OPENAI_API_KEY=sk-...
# Optional fallbacks / overrides
HF_TOKEN=
OPENAI_TRANSCRIPTION_MODEL=whisper-1
WHISPER_LANGUAGE=
```

Run the API:

```powershell
uvicorn main:app --reload --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

By default the frontend talks to `http://localhost:8000`. To point it elsewhere (e.g. a tunnel/remote backend), create `frontend/.env.local`:

```
VITE_API_URL=https://your-backend-url
```

## Usage

1. Start the backend (`uvicorn main:app --reload --port 8000`) and frontend (`npm run dev`).
2. Open the frontend (default `http://localhost:5173`), upload a video or paste a YouTube URL.
3. Wait for processing to complete (progress bar shows extraction/transcription/embedding stages).
4. Ask questions in the chat — answers reference specific moments in the video, with clickable timestamps to seek the player.

## Key API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/uploadfile/` | POST | Upload a video file; returns a `job_id` to poll |
| `/download-youtube/` | POST | Process a YouTube URL the same way as an upload |
| `/upload-status/{job_id}` | GET | Poll processing stage/progress/result |
| `/ask` | POST | Ask a question about the current video (supports `history` for follow-ups) |
| `/uploads/*`, `/audio/*` | GET | Static files for the processed video/audio |

## Notes

- Qdrant runs locally (file-backed at `backend/qdrant_data/`), so no external vector DB is required.
- Only one video is "active" at a time — uploading a new video clears the previous one's vectors and transcript/embedding JSON.
