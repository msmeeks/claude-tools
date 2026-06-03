"""SRT subtitle file generation from timed talk track segments."""

from __future__ import annotations

import math


def _format_time(seconds: float) -> str:
    """Format seconds as SRT timestamp HH:MM:SS,mmm."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - math.floor(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_srt(segments: list[tuple[str, float, float]]) -> str:
    """Generate SRT content from (text, start_seconds, end_seconds) tuples."""
    lines = []
    for i, (text, start, end) in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{_format_time(start)} --> {_format_time(end)}")
        # wrap at ~42 chars per line, max 2 lines
        words = text.split()
        line1_words: list[str] = []
        line2_words: list[str] = []
        current = line1_words
        length = 0
        for word in words:
            if length + len(word) + 1 > 42 and current is line1_words:
                current = line2_words
                length = 0
            current.append(word)
            length += len(word) + 1
        sub_text = " ".join(line1_words)
        if line2_words:
            sub_text += "\n" + " ".join(line2_words)
        lines.append(sub_text)
        lines.append("")
    return "\n".join(lines)


def timing_from_talk_tracks(talk_tracks: list[str], wpm: int = 150) -> list[tuple[str, float, float]]:
    """Compute (text, start, end) from talk tracks using wpm for duration estimation."""
    segments: list[tuple[str, float, float]] = []
    cursor = 0.0
    for text in talk_tracks:
        word_count = len(text.split())
        duration = max(2.0, (word_count / wpm) * 60.0)
        segments.append((text, cursor, cursor + duration))
        cursor += duration
    return segments
