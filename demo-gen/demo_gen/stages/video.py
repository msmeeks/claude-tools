"""Stage 5: Assemble MP4 from slides, audio, and subtitles via ffmpeg."""

from __future__ import annotations

import logging
from pathlib import Path

from demo_gen.config import DemoConfig, DemoScript
from demo_gen.utils import ffmpeg, srt

logger = logging.getLogger(__name__)

_TITLE_DURATION = 3.0
_CLOSING_DURATION = 3.0
_MIN_STEP_DURATION = 2.0


def assemble(
    script: DemoScript,
    slide_paths: list[Path],
    wav_paths: list[Path],
    durations: list[float],
    config: DemoConfig,
    tmp_dir: Path,
    output_path: Path,
) -> Path:
    """Compose final MP4. slide_paths = [title, step_0, ..., step_n, closing]."""
    clips: list[Path] = []

    # Title slide (no audio)
    silence_title = _make_silence(tmp_dir / "silence_title.wav", _TITLE_DURATION)
    title_clip = tmp_dir / "clip_000_title.mp4"
    raw = ffmpeg.image_to_video(slide_paths[0], _TITLE_DURATION, tmp_dir / "raw_title.mp4")
    ffmpeg.add_audio_to_video(raw, silence_title, title_clip)
    clips.append(title_clip)

    # Step slides
    for i, (wav, dur) in enumerate(zip(wav_paths, durations, strict=True)):
        step_dur = max(dur, _MIN_STEP_DURATION)
        raw_slide = tmp_dir / f"raw_step_{i:03d}.mp4"
        slide_with_audio = tmp_dir / f"clip_step_{i:03d}.mp4"
        raw = ffmpeg.image_to_video(slide_paths[i + 1], step_dur, raw_slide)
        # Pad audio if shorter than slide duration
        padded_audio = _pad_audio(wav, step_dur, tmp_dir / f"audio_padded_{i:03d}.wav")
        ffmpeg.add_audio_to_video(raw, padded_audio, slide_with_audio)
        clips.append(slide_with_audio)

    # Closing slide
    silence_closing = _make_silence(tmp_dir / "silence_closing.wav", _CLOSING_DURATION)
    closing_clip = tmp_dir / "clip_closing.mp4"
    raw = ffmpeg.image_to_video(slide_paths[-1], _CLOSING_DURATION, tmp_dir / "raw_closing.mp4")
    ffmpeg.add_audio_to_video(raw, silence_closing, closing_clip)
    clips.append(closing_clip)

    # Concatenate
    pre_subs = tmp_dir / "pre_subs.mp4"
    ffmpeg.concat_videos(clips, pre_subs, tmp_dir)

    # Generate and burn subtitles
    talk_tracks = [step.talk_track or step.caption for step in script.steps]
    offset = _TITLE_DURATION
    segments: list[tuple[str, float, float]] = []
    for text, dur in zip(talk_tracks, durations, strict=True):
        segments.append((text, offset, offset + dur))
        offset += dur
    srt_content = srt.generate_srt(segments)
    srt_path = tmp_dir / "subtitles.srt"
    srt_path.write_text(srt_content, encoding="utf-8")

    ffmpeg.burn_subtitles(pre_subs, srt_path, output_path)
    return output_path


def _make_silence(path: Path, duration: float) -> Path:
    """Generate a silent WAV file of given duration via ffmpeg."""
    import subprocess  # noqa: PLC0415
    subprocess.run(  # noqa: S603
        [ffmpeg.ffmpeg_binary(), "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
         "-t", str(duration), "-ar", "24000", str(path)],
        check=True, capture_output=True, shell=False,
    )
    return path


def _pad_audio(wav_path: Path, target_duration: float, output_path: Path) -> Path:
    """Pad or trim audio to exactly target_duration seconds."""
    import subprocess  # noqa: PLC0415
    safe_dur = ffmpeg._safe_float(target_duration, "target_duration")
    subprocess.run(  # noqa: S603
        [ffmpeg.ffmpeg_binary(), "-y", "-i", str(wav_path),
         "-af", f"apad=whole_dur={safe_dur}",
         "-t", str(safe_dur),
         str(output_path)],
        check=True, capture_output=True, shell=False,
    )
    return output_path
