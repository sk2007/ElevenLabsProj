import tempfile
from pathlib import Path

from src.srt_parser import Segment, parse_srt, write_srt

SAMPLE_SRT = """\
1
00:00:00,458 --> 00:00:03,750
What is radiation therapy
and what to expect?

2
00:00:03,750 --> 00:00:05,625
Introduction

3
00:00:05,625 --> 00:00:09,708
While you may have heard of chemotherapy
and surgery to treat cancer,

"""


def _write_tmp(content: str) -> Path:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".srt", delete=False, encoding="utf-8") as f:
        f.write(content)
        return Path(f.name)


def test_parse_srt_returns_correct_count():
    segments = parse_srt(_write_tmp(SAMPLE_SRT))
    assert len(segments) == 3


def test_parse_srt_segment_fields():
    segments = parse_srt(_write_tmp(SAMPLE_SRT))
    assert segments[0].index == 1
    assert segments[0].start == "00:00:00,458"
    assert segments[0].end == "00:00:03,750"
    assert segments[0].text == "What is radiation therapy and what to expect?"


def test_parse_srt_multiline_joined_with_space():
    segments = parse_srt(_write_tmp(SAMPLE_SRT))
    assert segments[2].text == "While you may have heard of chemotherapy and surgery to treat cancer,"


def test_write_srt_round_trips_timestamps():
    segments = parse_srt(_write_tmp(SAMPLE_SRT))
    for s in segments:
        s.text = f"TRANSLATED_{s.index}"
    with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as f:
        out = Path(f.name)
    write_srt(segments, out)
    result = parse_srt(out)
    assert result[0].start == "00:00:00,458"
    assert result[0].end == "00:00:03,750"
    assert result[0].text == "TRANSLATED_1"
    assert result[1].start == "00:00:03,750"
    assert result[2].text == "TRANSLATED_3"
