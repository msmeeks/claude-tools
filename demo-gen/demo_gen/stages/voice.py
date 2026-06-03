"""Stage 3: Generate per-step voiceover WAV files from the demo script."""

from __future__ import annotations

import logging
from pathlib import Path

import soundfile as sf

from demo_gen.config import DemoConfig, DemoScript
from demo_gen.models.tts import TTSBackend, build_backend

logger = logging.getLogger(__name__)


def generate_voiceovers(
    script: DemoScript,
    config: DemoConfig,
    tmp_dir: Path,
) -> tuple[list[Path], list[float]]:
    """Synthesize per-step audio. Returns (wav_paths, durations_seconds)."""
    backend: TTSBackend = build_backend(config.voice.value, config.polish.value)
    wav_paths: list[Path] = []
    durations: list[float] = []

    for i, step in enumerate(script.steps):
        text = step.talk_track or step.caption
        logger.info("Synthesizing step %d/%d", i + 1, len(script.steps))
        samples = backend.synthesize(text)
        duration = len(samples) / backend.sample_rate
        out_path = tmp_dir / f"step_{i:03d}.wav"
        sf.write(str(out_path), samples, backend.sample_rate, subtype="PCM_16")
        wav_paths.append(out_path)
        durations.append(duration)

    return wav_paths, durations
