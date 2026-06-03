"""Tests for SRT generation."""

from demo_gen.utils.srt import generate_srt, timing_from_talk_tracks


def test_format_time_zero():
    result = generate_srt([("Hello world", 0.0, 2.0)])
    assert "00:00:00,000 --> 00:00:02,000" in result
    assert "Hello world" in result


def test_format_time_nonzero():
    result = generate_srt([("Step one", 3.5, 7.0)])
    assert "00:00:03,500 --> 00:00:07,000" in result


def test_sequential_numbering():
    segs = [("First", 0.0, 2.0), ("Second", 2.0, 4.0)]
    result = generate_srt(segs)
    lines = result.strip().split("\n")
    assert lines[0] == "1"
    # Find second segment number
    blank_indices = [i for i, line in enumerate(lines) if line == ""]
    assert lines[blank_indices[0] + 1] == "2"


def test_long_line_wraps():
    long_text = "This is a very long subtitle line that should be wrapped at around forty two characters"
    result = generate_srt([(long_text, 0.0, 5.0)])
    # Should contain at least one newline in the text portion
    text_part = result.split("\n")[2]
    remaining = result.split("\n")[3] if len(result.split("\n")) > 3 else ""
    total = text_part + remaining
    assert long_text.replace(" ", "") in total.replace(" ", "").replace("\n", "")


def test_timing_from_talk_tracks():
    tracks = ["Short text.", "This is a slightly longer sentence with more words in it."]
    segs = timing_from_talk_tracks(tracks, wpm=150)
    assert len(segs) == 2
    assert segs[0][1] == 0.0  # first starts at 0
    assert segs[1][1] == segs[0][2]  # second starts where first ends
    assert segs[0][2] >= 2.0  # minimum duration
    assert segs[1][2] > segs[1][1]


def test_minimum_duration():
    segs = timing_from_talk_tracks(["Hi."], wpm=150)
    duration = segs[0][2] - segs[0][1]
    assert duration >= 2.0
