import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from src.srt_parser import Segment
from src.translator import translate_file, run_translate_stage

SEGMENTS = [
    Segment(index=1, start="00:00:00,000", end="00:00:02,000", text="What is radiation therapy?"),
    Segment(index=2, start="00:00:02,000", end="00:00:04,000", text="Introduction"),
]
MOCK_KO = '[{"index": 1, "translated": "방사선 치료란 무엇입니까?"}, {"index": 2, "translated": "소개"}]'


def _mock_client(response_text: str):
    client = MagicMock()
    msg = MagicMock()
    msg.choices = [MagicMock(message=MagicMock(content=response_text))]
    client.chat.completions.create.return_value = msg
    return client


def test_translate_file_returns_correct_structure():
    client = _mock_client(MOCK_KO)
    with tempfile.TemporaryDirectory() as tmp:
        result = translate_file(SEGMENTS, "ko", Path(tmp) / "out.json", client)
    assert len(result) == 2
    assert result[0] == {
        "index": 1, "start": "00:00:00,000", "end": "00:00:02,000",
        "original": "What is radiation therapy?", "translated": "방사선 치료란 무엇입니까?",
    }


def test_translate_file_writes_json_to_disk():
    client = _mock_client(MOCK_KO)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "sub" / "out.json"
        translate_file(SEGMENTS, "ko", out, client)
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
    assert data[1]["translated"] == "소개"


def test_translate_file_skips_when_cached():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "cached.json"
        cached = [
            {"index": 1, "start": "00:00:00,000", "end": "00:00:02,000",
             "original": "x", "translated": "캐시됨"},
            {"index": 2, "start": "00:00:02,000", "end": "00:00:04,000",
             "original": "y", "translated": "소개"},
        ]
        out.write_text(json.dumps(cached), encoding="utf-8")
        client = _mock_client(MOCK_KO)
        result = translate_file(SEGMENTS, "ko", out, client)
    client.chat.completions.create.assert_not_called()
    assert result[0]["translated"] == "캐시됨"


def test_translate_file_returns_none_on_api_error():
    client = MagicMock()
    client.chat.completions.create.side_effect = Exception("API error")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "fail.json"
        result = translate_file(SEGMENTS, "ko", out, client)
        assert result is None
        assert not out.exists()
