# AI Video Tool

Upload a video (or paste a YouTube link) and chat with it. The backend transcribes the audio, embeds the transcript and keyframes into a vector store, and answers questions about the video in natural language, citing the exact moments the answer came from.

## What it does

You drop in a video or a YouTube URL and it gets transcribed (OpenAI Whisper, chunked and parallelized so long videos don't take forever), with the transcript embedded locally via `sentence-transformers` and keyframes embedded with CLIP, both stored in a local Qdrant instance. From there you can ask questions in a chat interface and get answers grounded in the transcript, with clickable `[mm:ss–mm:ss]` timestamps so you can jump straight to the part of the video being referenced. It handles both Greek and English depending on what you ask. For coding tutorials it'll pull out code snippets with their timestamps, and for data-structure questions it'll draw a Mermaid diagram if that helps explain things. The video player itself is a themed video.js setup with proper seeking (the usual "raw upload can't be scrubbed accurately" problem is fixed via faststart remuxing on upload).

## Stack

Backend is FastAPI, with Qdrant running locally (file-based, no external service needed), ffmpeg for audio/video processing, the OpenAI Whisper API for transcription, `sentence-transformers` for text embeddings, CLIP for frame embeddings, and `yt-dlp` for YouTube downloads.

Frontend is React 19 on Vite, with video.js for playback, `react-markdown` + Mermaid for rendering answers, and Framer Motion / GSAP / three.js for the visual effects around the UI.

## Project layout

```
backend/
  main.py              FastAPI app, upload/ask endpoints, pipeline orchestration
  video_processing.py  ffmpeg audio extraction, frame extraction, video normalization
  whisper.py           Chunked/parallel audio transcription
  bert.py              Transcript text embeddings (sentence-transformers)
  frame_embeddings.py  Frame/CLIP embeddings
  qdrant_store.py      Qdrant collections, storage, and search
  llama.py             LLM prompt + answer generation
  uploads/             Saved/normalized video files (served at /uploads)
  audio/               Extracted audio + transcript/embedding JSON
  frames/              Extracted keyframes + embeddings
  qdrant_data/          Local Qdrant storage

frontend/
  src/components/      React UI (video player, chatbot, upload flow, etc.)
  src/styles/          Component CSS
```

## Getting it running

You'll need Python 3.11+, Node 18+, [ffmpeg](https://ffmpeg.org/) on your `PATH`, and an OpenAI API key for transcription and chat.

For the backend:

```powershell
cd backend
python -m venv ../.venv
..\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Drop a `.env` file in `backend/`:

```
OPENAI_API_KEY=sk-...
# optional
HF_TOKEN=
OPENAI_TRANSCRIPTION_MODEL=whisper-1
WHISPER_LANGUAGE=
```

Then run it with `uvicorn main:app --reload --port 8000`.

For the frontend, it's the usual `cd frontend && npm install && npm run dev`. It talks to `http://localhost:8000` by default; if your backend lives somewhere else (a tunnel, for example), set `VITE_API_URL` in `frontend/.env.local`.

## Using it

Start both servers, open the frontend (defaults to `http://localhost:5173`), and upload a video or paste a YouTube URL. A progress bar tracks extraction/transcription/embedding while it processes. Once it's done, just ask questions in the chat — answers will point back to specific moments in the video, and clicking a timestamp seeks the player there.

## API endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/uploadfile/` | POST | Upload a video file; returns a `job_id` to poll |
| `/download-youtube/` | POST | Process a YouTube URL the same way as an upload |
| `/upload-status/{job_id}` | GET | Poll processing stage/progress/result |
| `/ask` | POST | Ask a question about the current video (supports `history` for follow-ups) |
| `/uploads/*`, `/audio/*` | GET | Static files for the processed video/audio |

## A couple of things worth knowing

Qdrant runs locally out of `backend/qdrant_data/`, so there's nothing external to stand up. Also, the app only keeps one video "active" at a time — uploading a new one clears out the previous video's vectors and transcript data, so it's not meant for juggling multiple videos simultaneously yet.
