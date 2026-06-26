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
            # acodec: PCM signed 16-bit little-endian
            # ac: mono channel
            # ar: sample rate (Hz)
            .output(str(output_audio), acodec="pcm_s16le", ac=1, ar="16000")
            # overwrite_output avoids interactive ffmpeg prompts on re-uploads.
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        print(f"Audio extracted successfully to {output_audio}")
    except ffmpeg.Error as e:
        stderr = e.stderr.decode(errors="replace") if e.stderr else str(e)
        raise RuntimeError(f"Audio extraction failed: {stderr}") from e


def extract_frames(
    video_path,
    output_dir,
    interval_seconds=5.0,
    keyframes_only=True,
    max_width=0,
    quality=5,
):
    """Extract sampled JPEG frames from video_path into output_dir.

    Processing model:
    1) Clean existing frame files in output_dir
    2) Build ffmpeg input (optionally keyframe-only decoding)
    3) Apply fps sampling filter based on interval_seconds
    4) Optionally resize frames to max_width
    5) Save sequential images: frame000001.jpg, frame000002.jpg, ...

    interval_seconds: seconds between sampled frames.
    keyframes_only: if True, decode keyframes only. Faster on long videos but
        timestamps are less uniform than full decode.
    max_width: if > 0, constrain output width while preserving aspect ratio.
    quality: JPEG q:v quality (2 best quality/larger files .. 31 lowest quality).
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
            # skip_frame=nokey tells decoder to skip non-key frames early.
            # This usually gives a major speed-up for long GOP videos.
            input_kwargs["skip_frame"] = "nokey"

        # Build ffmpeg input stream from the on-disk video path.
        stream = ffmpeg.input(str(video_path), **input_kwargs)

        # Prevent invalid/zero fps math when interval is <= 0.
        safe_interval = max(float(interval_seconds), 0.1)
        vf_parts = [f"fps=1/{safe_interval}"]

        if max_width and int(max_width) > 0:
            # scale=min(max_width, iw):-2 => do not upscale, preserve aspect,
            # and force an even height value required by many codecs/pipelines.
            vf_parts.append(f"scale='min({int(max_width)},iw)':-2")

        output_pattern = output_dir / "frame%06d.jpg"

        (
            stream.output(
                str(output_pattern),
                vf=",".join(vf_parts),
                format="image2",
                # vfr writes frames at selected timestamps without duplicating
                # frames to match a fixed output frame rate.
                vsync="vfr",
                **{"q:v": max(2, min(int(quality), 31))},
                start_number=1,
            )
            .overwrite_output()
            # threads=0 lets ffmpeg auto-select thread count for this machine.
            # loglevel=error keeps logs concise while preserving failures.
            .global_args("-threads", "0", "-loglevel", "error")
            .run(capture_stdout=True, capture_stderr=True)
        )

        # Count generated files so caller can report extraction volume.
        frame_count = len(list(output_dir.glob("frame*.jpg")))
        print(f"Frames extracted successfully to {output_dir} (count={frame_count})")
        return frame_count
    except ffmpeg.Error as e:
        stderr = e.stderr.decode(errors="replace") if e.stderr else str(e)
        raise RuntimeError(f"Frame extraction failed: {stderr}") from e
