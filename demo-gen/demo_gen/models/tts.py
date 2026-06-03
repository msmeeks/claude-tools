"""TTS backends: Kokoro ONNX (primary) and Piper (fast fallback)."""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)


class TTSBackend(Protocol):
    def synthesize(self, text: str, speed: float = 1.0) -> np.ndarray:
        """Return audio samples as float32 numpy array at 24000 Hz."""
        ...

    @property
    def sample_rate(self) -> int: ...


class NullBackend:
    """Produces 0.5s of silence — for draft mode or when no TTS is available."""

    @property
    def sample_rate(self) -> int:
        return 24000

    def synthesize(self, text: str, speed: float = 1.0) -> np.ndarray:
        words = len(text.split())
        duration = max(0.5, words / (150 / 60))
        return np.zeros(int(self.sample_rate * duration), dtype=np.float32)


class KokoroBackend:
    def __init__(self, voice: str = "af_heart") -> None:
        self._voice = voice
        self._pipeline = None

    def _load(self) -> None:
        if self._pipeline is not None:
            return
        try:
            from kokoro_onnx import Kokoro  # noqa: PLC0415
        except ImportError as e:
            raise RuntimeError("kokoro-onnx not installed. Run: pip install kokoro-onnx") from e
        from demo_gen.models import downloader  # noqa: PLC0415
        model_path = downloader.download("kokoro")
        voices_path = downloader.download("kokoro_voices")
        logger.info("Loading Kokoro model from %s", model_path)
        self._pipeline = Kokoro(str(model_path), str(voices_path))

    @property
    def sample_rate(self) -> int:
        return 24000

    def synthesize(self, text: str, speed: float = 1.0) -> np.ndarray:
        self._load()
        samples, sr = self._pipeline.create(text, voice=self._voice, speed=speed, lang="en-us")
        if sr != self.sample_rate:
            samples = _resample(samples, sr, self.sample_rate)
        return samples.astype(np.float32)


class PiperBackend:
    """Piper TTS via subprocess (GPL-3.0 — note license before distributing)."""

    def __init__(self, model_path: Path, piper_bin: str = "piper") -> None:
        self._model_path = model_path
        self._piper_bin = piper_bin

    @property
    def sample_rate(self) -> int:
        return 22050

    def synthesize(self, text: str, speed: float = 1.0) -> np.ndarray:
        import soundfile as sf  # noqa: PLC0415
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            subprocess.run(  # noqa: S603
                [self._piper_bin, "--model", str(self._model_path), "--output_file", str(tmp_path)],
                input=text,
                text=True,
                check=True,
                capture_output=True,
                shell=False,
            )
            samples, sr = sf.read(str(tmp_path), dtype="float32")
            if sr != self.sample_rate:
                samples = _resample(samples, sr, self.sample_rate)
            return samples
        finally:
            tmp_path.unlink(missing_ok=True)


def _resample(samples: np.ndarray, from_sr: int, to_sr: int) -> np.ndarray:
    if from_sr == to_sr:
        return samples
    try:
        import resampy  # noqa: PLC0415
        return resampy.resample(samples, from_sr, to_sr)
    except ImportError:
        # Simple linear interpolation fallback (quality is acceptable for demos)
        ratio = to_sr / from_sr
        new_len = int(len(samples) * ratio)
        indices = np.linspace(0, len(samples) - 1, new_len)
        return np.interp(indices, np.arange(len(samples)), samples).astype(np.float32)


def build_backend(voice: str, polish_level: str) -> TTSBackend:
    if polish_level == "draft":
        try:
            return PiperBackend(model_path=_find_piper_model())
        except Exception:
            logger.info("Piper not available for draft mode, using NullBackend")
            return NullBackend()
    try:
        return KokoroBackend(voice=voice)
    except Exception:
        logger.warning("Kokoro not available, falling back to NullBackend")
        return NullBackend()


def _find_piper_model() -> Path:
    default = Path.home() / ".demo-gen" / "models" / "piper" / "en_US-lessac-medium.onnx"
    if default.exists():
        return default
    raise FileNotFoundError("Piper model not found. Run: demo-gen download-models --tts-only")
