import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from src.synthesizer import VOICE_ID, synthesize_segment, run_synthesize_stage


def _fake_mp3() -> bytes:
    return b"\xff\xe3" + b"\x00" * 100


def _mock_client(audio: bytes):
    client = MagicMock()
    client.text_to_speech.convert.return_value = iter([audio])
    return client


def test_synthesize_segment_writes_mp3_file():
    client = _mock_client(_fake_mp3())
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "seg001.mp3"
        result = synthesize_segment("안녕하세요", out, VOICE_ID, client)
        assert result is True
        assert out.exists()
        assert out.stat().st_size > 0


def test_synthesize_segment_skips_nonempty_file():
    client = _mock_client(_fake_mp3())
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "seg001.mp3"
        out.write_bytes(b"FAKE" * 100)
        result = synthesize_segment("안녕하세요", out, VOICE_ID, client)
    assert result is False
    client.text_to_speech.convert.assert_not_called()


def test_synthesize_segment_returns_false_on_api_error():
    client = MagicMock()
    client.text_to_speech.convert.side_effect = Exception("TTS error")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "seg001.mp3"
        result = synthesize_segment("text", out, VOICE_ID, client)
    assert result is False
    assert not out.exists()


def test_run_synthesize_stage_counts_synthesized():
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        trans_dir = tmpdir / "translations" / "ko" / "Gen Intro"
        trans_dir.mkdir(parents=True)
        translation = [
            {"index": 1, "start": "00:00:00,000", "end": "00:00:02,000",
             "original": "Hello", "translated": "안녕하세요"},
        ]
        (trans_dir / "01_intro.json").write_text(json.dumps(translation), encoding="utf-8")
        client = _mock_client(_fake_mp3())
        counts = run_synthesize_stage(tmpdir, ["ko"], client)
    assert counts["synthesized"] == 1
    assert counts["cached"] == 0
    assert counts["errors"] == 0
