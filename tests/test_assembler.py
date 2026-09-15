import tempfile
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.assembler import (
    srt_time_to_seconds,
    build_atempo_filter,
    get_audio_duration,
    timescale_segment,
)


def _make_wav(path: Path, seconds: float = 1.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(b"\x00\x00" * int(44100 * seconds))


def test_srt_time_to_seconds_basic():
    assert srt_time_to_seconds("00:00:03,750") == 3.75


def test_srt_time_to_seconds_minutes():
    assert srt_time_to_seconds("00:01:00,000") == 60.0


def test_srt_time_to_seconds_hours():
    assert srt_time_to_seconds("01:00:00,000") == 3600.0


def test_build_atempo_within_range():
    assert build_atempo_filter(1.5) == "atempo=1.5"


def test_build_atempo_above_range():
    # 6s audio into 2s target → ratio 3.0 → atempo=2.0,atempo=1.5
    assert build_atempo_filter(3.0) == "atempo=2.0,atempo=1.5"


def test_build_atempo_below_range():
    # 1s audio into 4s target → ratio 0.25 → atempo=0.5,atempo=0.5
    assert build_atempo_filter(0.25) == "atempo=0.5,atempo=0.5"


def test_get_audio_duration_parses_ffprobe():
    with patch("src.assembler.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="3.750000\n", returncode=0)
        with tempfile.TemporaryDirectory() as tmp:
            dummy = Path(tmp) / "audio.wav"
            dummy.write_bytes(b"fake")
            duration = get_audio_duration(dummy)
    assert duration == 3.75


def test_timescale_segment_calls_ffmpeg_with_atempo():
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw.wav"
        scaled = Path(tmp) / "scaled.wav"
        _make_wav(raw, seconds=3.0)
        with patch("src.assembler.subprocess.run") as mock_run, \
             patch("src.assembler.get_audio_duration", return_value=3.0):
            mock_run.return_value = MagicMock(returncode=0)
            result = timescale_segment(raw, scaled, target_duration=2.0)
    assert result is True
    cmd = " ".join(mock_run.call_args[0][0])
    assert "atempo" in cmd


def test_timescale_segment_copies_raw_on_ffmpeg_failure():
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw.wav"
        scaled = Path(tmp) / "scaled.wav"
        _make_wav(raw, seconds=1.0)
        with patch("src.assembler.subprocess.run") as mock_run, \
             patch("src.assembler.get_audio_duration", return_value=1.0):
            mock_run.side_effect = Exception("ffmpeg missing")
            result = timescale_segment(raw, scaled, target_duration=2.0)
        assert result is False
        assert scaled.exists()
