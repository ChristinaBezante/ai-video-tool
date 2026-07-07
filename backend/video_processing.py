import re
import ffmpeg
from pathlib import Path


def extract_audio(video_path, output_audio):
    """Extract speech-friendly WAV audio from a video file.

    Output format is PCM 16-bit, mono, 16 kHz. This is a common baseline for
    ASR/transcription pipelines and keeps file handling simple downstream.
    """
    try:
        (
            ffmpeg.input(str(video_path))
            .output(str(output_audio), acodec="pcm_s16le", ac=1, ar="16000")
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        print(f"Audio extracted successfully to {output_audio}")
    except ffmpeg.Error as e:
        stderr = e.stderr.decode(errors="replace") if e.stderr else str(e)
        raise RuntimeError(f"Audio extraction failed: {stderr}") from e


_PTS_TIME_RE = re.compile(r"pts_time:([0-9.]+)")


def extract_frames(
    video_path,
    output_dir,
    interval_seconds=5.0,
    extraction_mode="scene",
    scene_threshold=0.35,
    keyframes_only=True,
    max_width=0,
    quality=5,
):
    """Extract sampled JPEG frames from video_path into output_dir.

    Processing model:
    1) Clean existing frame files in output_dir
    2) Build ffmpeg input (optionally keyframe-only decoding)
    3) Apply frame-selection filter:
       - scene mode: keep frames where FFmpeg scene score exceeds threshold
       - interval mode: fps sampling based on interval_seconds
    4) Log each selected frame's true PTS timestamp via showinfo (stderr)
    5) Optionally resize frames to max_width
    6) Save sequential images: frame000001.jpg, frame000002.jpg, ...

    extraction_mode: "scene" or "interval".
    scene_threshold: FFmpeg scene-change threshold (0.0..1.0), used in scene mode.
    interval_seconds: seconds between sampled frames.
    keyframes_only: if True, decode keyframes only. Faster on long videos but
        timestamps are less uniform than full decode.
    max_width: if > 0, constrain output width while preserving aspect ratio.
    quality: JPEG q:v quality (2 best quality/larger files .. 31 lowest quality).

    Returns:
        (frame_count, timestamps) where timestamps is a dict mapping
        "frame000001.jpg" -> seconds (float), in extraction order.
    """
    try:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Remove old frames so repeated processing of the same video stem does
        # not mix previous and current outputs.
        for old_frame in output_dir.glob("frame*.jpg"):
            old_frame.unlink(missing_ok=True)

        input_kwargs = {}
        if keyframes_only:
            input_kwargs["skip_frame"] = "nokey"

        stream = ffmpeg.input(str(video_path), **input_kwargs)

        safe_mode = str(extraction_mode or "scene").strip().lower()
        if safe_mode not in {"scene", "interval"}:
            raise ValueError("extraction_mode must be either 'scene' or 'interval'")

        vf_parts = []
        if safe_mode == "scene":
            safe_scene_threshold = min(max(float(scene_threshold), 0.0), 1.0)
            vf_parts.append(f"select='gt(scene\\,{safe_scene_threshold:.3f})'")
        else:
            safe_interval = max(float(interval_seconds), 0.1)
            vf_parts.append(f"fps=1/{safe_interval}")

        # showinfo logs pts_time for every frame that survives selection,
        # in output order — this is how we recover true timestamps below.
        vf_parts.append("showinfo")

        if max_width and int(max_width) > 0:
            vf_parts.append(f"scale='min({int(max_width)},iw)':-2")

        output_pattern = output_dir / "frame%06d.jpg"

        process = (
            stream.output(
                str(output_pattern),
                vf=",".join(vf_parts),
                format="image2",
                vsync="vfr",
                **{"q:v": max(2, min(int(quality), 31))},
                start_number=1,
            )
            .overwrite_output()
            # loglevel must be "info" (not "error") or showinfo's pts_time
            # lines get suppressed and we lose the timestamp data entirely.
            .global_args("-threads", "0", "-loglevel", "info")
        )

        result = process.run(capture_stdout=True, capture_stderr=True)
        stderr_text = result[1].decode(errors="replace") if result[1] else ""

        pts_times = [float(m) for m in _PTS_TIME_RE.findall(stderr_text)]

        frame_files = sorted(output_dir.glob("frame*.jpg"))
        frame_count = len(frame_files)

        if len(pts_times) != frame_count:
            # Mismatch shouldn't normally happen, but don't silently produce
            # wrong pairings — fall back to None rather than misalign frames.
            print(
                f"Warning: showinfo timestamp count ({len(pts_times)}) != "
                f"frame count ({frame_count}); timestamps may be incomplete."
            )

        timestamps = {}
        for i, frame_file in enumerate(frame_files):
            timestamps[frame_file.name] = pts_times[i] if i < len(pts_times) else None

        print(f"Frames extracted successfully to {output_dir} (count={frame_count})")
        return frame_count, timestamps
    except ValueError as e:
        raise RuntimeError(f"Frame extraction failed: {e}") from e
    except ffmpeg.Error as e:
        stderr = e.stderr.decode(errors="replace") if e.stderr else str(e)
        raise RuntimeError(f"Frame extraction failed: {stderr}") from e