"""Pydantic models for demo-gen configuration and data structures."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class PolishLevel(str, Enum):
    draft = "draft"
    standard = "standard"
    production = "production"


class TonePreset(str, Enum):
    professional = "professional"
    casual = "casual"
    energetic = "energetic"


class VoicePreset(str, Enum):
    # Kokoro — American female (top picks: sky, kore, heart)
    af_sky = "af_sky"
    af_kore = "af_kore"
    af_heart = "af_heart"
    # Kokoro — American male (top picks: puck, michael, echo, santa)
    am_puck = "am_puck"
    am_michael = "am_michael"
    am_echo = "am_echo"
    am_santa = "am_santa"
    # Piper fallback sentinel
    piper = "piper"


class OutputFormat(str, Enum):
    html = "html"
    mp4 = "mp4"
    both = "both"


class Resolution(str, Enum):
    hd = "1280x720"
    fhd = "1920x1080"

    @property
    def width(self) -> int:
        return int(self.value.split("x")[0])

    @property
    def height(self) -> int:
        return int(self.value.split("x")[1])


class DemoConfig(BaseModel):
    product: str = Field(description="Product name shown in demos")
    feature: str = Field(description="Feature or demo name (used as output filename slug)")
    brand_voice_path: Path | None = Field(default=None)
    include_docs: list[Path] = Field(default_factory=list, description="Docs files to include in scripting context")
    screenshots: list[Path] = Field(default_factory=list)
    recordings: list[Path] = Field(default_factory=list)
    tokens_path: Path | None = Field(default=None, description="design_tokens.json override")
    output_dir: Path = Field(default=Path("./output"))
    format: OutputFormat = OutputFormat.both
    polish: PolishLevel = PolishLevel.standard
    tone: TonePreset = TonePreset.professional
    voice: VoicePreset = VoicePreset.af_heart
    resolution: Resolution = Resolution.hd
    wpm: int = Field(default=150, ge=80, le=300)
    local: bool = Field(default=False, description="Use local LLM (Ollama). Default is cloud (Claude API).")
    local_model: str = Field(default="llama3.2")
    cloud_model: str = Field(default="claude-sonnet-4-6")
    scope: str = Field(default="feature", pattern="^(feature|whole)$")
    title: str | None = None

    @field_validator("screenshots", "recordings", "include_docs", mode="before")
    @classmethod
    def coerce_paths(cls, v: list) -> list[Path]:
        return [Path(p) for p in v]


class Step(BaseModel):
    heading: str = Field(description="Action verb + outcome, ≤12 words")
    caption: str = Field(description="1-2 sentences, active voice, benefit-first")
    talk_track: str = Field(description="Full narration sentence(s) for this step")
    screenshot_index: int | None = Field(default=None, description="Index into screenshots list, or None for placeholder")
    callout_label: str | None = Field(default=None, description="Short label for the callout annotation")
    callout_region: tuple[int, int, int, int] | None = Field(
        default=None, description="(x, y, w, h) pixel region to highlight in screenshot"
    )


class DemoScript(BaseModel):
    title: str
    tagline: str
    executive_summary: str = Field(description="2-3 sentences: what this feature does and why it matters")
    steps: list[Step]
    takeaways: list[str] = Field(description="3-5 key takeaways")
    cta: str = Field(description="Call to action text")
