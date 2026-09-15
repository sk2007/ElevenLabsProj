# ElevenLabs Korean & Chinese Translation Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a three-stage checkpointed Python pipeline that translates English SRT caption files into Korean and Chinese, synthesizes audio with an ElevenLabs stock female voice, and time-scales each segment to match the original video timestamps — without ever touching the original voice actor's audio files.

**Architecture:** Stage 1 batches each SRT file's segments into a single Claude API call to translate, saving a JSON checkpoint per file. Stage 2 calls ElevenLabs TTS per segment (eleven_multilingual_v2, Rachel voice) and saves raw PCM WAV files. Stage 3 uses ffmpeg atempo to time-scale each segment to match original SRT durations, concatenates them, and writes final WAV + translated SRT files. All three stages skip already-completed outputs on re-run.

**Tech Stack:** Python 3.11+, `anthropic`, `elevenlabs`, `python-dotenv`, `pytest`, `pytest-mock`, `ffmpeg` (system via brew)

## Global Constraints

- **Never read from or reference `VO/`** — original voice actor audio must not be touched under any circumstance
- **Never upload original audio to ElevenLabs** — stock voice only
- ElevenLabs model: `eleven_multilingual_v2`
- ElevenLabs default voice: Rachel (`21m00Tcm4TlvDq8ikWAM`) — configurable via `VOICE_ID` constant at top of `src/synthesizer.py`
- ElevenLabs output format: `pcm_44100` → saved as 44100 Hz 16-bit mono WAV
- Target languages: `ko` (Korean), `zh` (Chinese Simplified)
- All output under `output/` directory (gitignored)
- Claude model: `claude-sonnet-4-6`
- SRT timestamp format: `HH:MM:SS,mmm` (comma as decimal separator)
- ffmpeg `atempo` range: 0.5–2.0; chain two filters for ratios outside this range
- Checkpointing: skip translation JSON if it exists with correct segment count; skip raw WAV if it exists and is non-empty

---

## File Map

| File | Responsibility |
|---|---|
| `requirements.txt` | Python dependencies |
| `.env.example` | API key template |
| `.gitignore` | Exclude `.env`, `output/`, caches |
| `src/__init__.py` | Package marker |
| `src/srt_parser.py` | Parse SRT files; write translated SRT files |
| `src/translator.py` | Stage 1: Claude API translation with checkpointing |
| `src/synthesizer.py` | Stage 2: ElevenLabs TTS with checkpointing |
| `src/assembler.py` | Stage 3: ffmpeg atempo time-scaling + concatenation |
| `pipeline.py` | CLI entry point; orchestrates all three stages |
| `tests/test_srt_parser.py` | Unit tests for SRT parsing/writing |
| `tests/test_translator.py` | Unit tests for translation (mocked Anthropic client) |
| `tests/test_synthesizer.py` | Unit tests for synthesis (mocked ElevenLabs client) |
| `tests/test_assembler.py` | Unit tests for assembly helpers (mocked subprocess) |

---

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `src/__init__.py`
- Create: `tests/__init__.py`

**Interfaces:**
- Produces: installable Python environment; `src/` and `tests/` importable as packages

- [ ] **Step 1: Create `requirements.txt`**

```
anthropic>=0.34.0
elevenlabs>=1.9.0
python-dotenv>=1.0.0
pytest>=8.0.0
pytest-mock>=3.14.0
```

- [ ] **Step 2: Create `.env.example`**

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
ELEVENLABS_API_KEY=sk_your-key-here
```

- [ ] **Step 3: Create `.gitignore`**

```
.env
__pycache__/
*.pyc
.pytest_cache/
output/
.DS_Store
```

- [ ] **Step 4: Create empty package markers**

Create `src/__init__.py` and `tests/__init__.py` as empty files.

- [ ] **Step 5: Install Python dependencies**

```bash
pip install -r requirements.txt
```

Expected: all packages install without errors.

- [ ] **Step 6: Verify ffmpeg is installed**

```bash
ffmpeg -version && ffprobe -version
```

If either command fails, install with:
```bash
brew install ffmpeg
```

- [ ] **Step 7: Commit**

```bash
git add requirements.txt .env.example .gitignore src/__init__.py tests/__init__.py
git commit -m "feat: project scaffolding for translation pipeline"
```

---

### Task 2: SRT Parser Module

**Files:**
- Create: `src/srt_parser.py`
- Create: `tests/test_srt_parser.py`

**Interfaces:**
- Produces:
  - `Segment` dataclass: `index: int`, `start: str`, `end: str`, `text: str`
  - `parse_srt(path: Path) -> list[Segment]` — parses an SRT file; multi-line text blocks are joined with a single space
  - `write_srt(segments: list[Segment], path: Path) -> None` — writes segments as valid SRT; creates parent dirs

- [ ] **Step 1: Write the failing tests**

Create `tests/test_srt_parser.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_srt_parser.py -v
```

Expected: `ImportError: cannot import name 'Segment' from 'src.srt_parser'`

- [ ] **Step 3: Implement `src/srt_parser.py`**

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Segment:
    index: int
    start: str
    end: str
    text: str


def parse_srt(path: Path) -> list[Segment]:
    raw = path.read_text(encoding="utf-8")
    blocks = [b.strip() for b in raw.strip().split("\n\n") if b.strip()]
    segments = []
    for block in blocks:
        lines = block.splitlines()
        if len(lines) < 3:
            continue
        index = int(lines[0].strip())
        start, end = [t.strip() for t in lines[1].split("-->")]
        text = " ".join(line.strip() for line in lines[2:] if line.strip())
        segments.append(Segment(index=index, start=start, end=end, text=text))
    return segments


def write_srt(segments: list[Segment], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for s in segments:
        lines.append(str(s.index))
        lines.append(f"{s.start} --> {s.end}")
        lines.append(s.text)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_srt_parser.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/srt_parser.py tests/test_srt_parser.py
git commit -m "feat: SRT parser with parse and write functions"
```

---

### Task 3: Translation Stage

**Files:**
- Create: `src/translator.py`
- Create: `tests/test_translator.py`

**Interfaces:**
- Consumes: `Segment`, `parse_srt` from `src.srt_parser`
- Produces:
  - `translate_file(segments: list[Segment], lang: str, out_path: Path, client: anthropic.Anthropic) -> list[dict] | None`
    — returns `[{"index": int, "start": str, "end": str, "original": str, "translated": str}]` or `None` on API failure
  - `run_translate_stage(captions_dir: Path, output_dir: Path, langs: list[str], client: anthropic.Anthropic) -> dict`
    — returns `{"translated": int, "cached": int, "errors": int}`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_translator.py`:

```python
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
    msg.content = [MagicMock(text=response_text)]
    client.messages.create.return_value = msg
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
    client.messages.create.assert_not_called()
    assert result[0]["translated"] == "캐시됨"


def test_translate_file_returns_none_on_api_error():
    client = MagicMock()
    client.messages.create.side_effect = Exception("API error")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "fail.json"
        result = translate_file(SEGMENTS, "ko", out, client)
        assert result is None
        assert not out.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_translator.py -v
```

Expected: `ImportError: cannot import name 'translate_file' from 'src.translator'`

- [ ] **Step 3: Implement `src/translator.py`**

```python
import json
import logging
from pathlib import Path

import anthropic

from src.srt_parser import Segment, parse_srt

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-6"
LANG_NAMES = {"ko": "Korean", "zh": "Chinese (Simplified)"}


def translate_file(
    segments: list[Segment],
    lang: str,
    out_path: Path,
    client: anthropic.Anthropic,
) -> list[dict] | None:
    if out_path.exists():
        try:
            cached = json.loads(out_path.read_text(encoding="utf-8"))
            if len(cached) == len(segments):
                logger.info("Cached: %s", out_path.name)
                return cached
        except (json.JSONDecodeError, KeyError):
            pass

    lang_name = LANG_NAMES[lang]
    segments_json = json.dumps(
        [{"index": s.index, "text": s.text} for s in segments],
        ensure_ascii=False,
    )
    prompt = (
        f"You are a medical translator specializing in oncology patient education.\n\n"
        f"Translate the following English segments from an oncology patient education video into {lang_name}. "
        f"Preserve medical terminology accuracy. Keep translations concise — they will be spoken aloud.\n\n"
        f"Return ONLY a JSON array with this exact structure (no other text):\n"
        f'[{{"index": 1, "translated": "..."}}]\n\n'
        f"Segments:\n{segments_json}"
    )
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        trans_list = json.loads(response.content[0].text)
    except Exception as e:
        logger.error("Translation failed (%s): %s", out_path.name, e)
        return None

    trans_map = {item["index"]: item["translated"] for item in trans_list}
    result = [
        {
            "index": s.index,
            "start": s.start,
            "end": s.end,
            "original": s.text,
            "translated": trans_map[s.index],
        }
        for s in segments
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def run_translate_stage(
    captions_dir: Path,
    output_dir: Path,
    langs: list[str],
    client: anthropic.Anthropic,
) -> dict:
    counts = {"translated": 0, "cached": 0, "errors": 0}
    for srt_path in sorted(captions_dir.rglob("*.srt")):
        module = srt_path.parent.name
        segments = parse_srt(srt_path)
        for lang in langs:
            out_path = output_dir / "translations" / lang / module / (srt_path.stem + ".json")
            if out_path.exists():
                try:
                    cached = json.loads(out_path.read_text(encoding="utf-8"))
                    if len(cached) == len(segments):
                        counts["cached"] += 1
                        continue
                except Exception:
                    pass
            result = translate_file(segments, lang, out_path, client)
            if result is None:
                counts["errors"] += 1
            else:
                counts["translated"] += 1
    return counts
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_translator.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/translator.py tests/test_translator.py
git commit -m "feat: Stage 1 translation with Claude API and checkpointing"
```

---

### Task 4: Synthesis Stage

**Files:**
- Create: `src/synthesizer.py`
- Create: `tests/test_synthesizer.py`

**Interfaces:**
- Consumes: translation JSON files at `output/translations/{lang}/{module}/*.json`
- Produces:
  - `VOICE_ID: str = "21m00Tcm4TlvDq8ikWAM"` — Rachel (ElevenLabs stock female, eleven_multilingual_v2)
  - `synthesize_segment(text: str, out_path: Path, voice_id: str, client: ElevenLabs) -> bool`
    — writes 44100 Hz 16-bit mono WAV; returns `True` if synthesized, `False` if cached or failed
  - `run_synthesize_stage(output_dir: Path, langs: list[str], client: ElevenLabs, voice_id: str = VOICE_ID) -> dict`
    — returns `{"synthesized": int, "cached": int, "errors": int}`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_synthesizer.py`:

```python
import json
import tempfile
import wave
from pathlib import Path
from unittest.mock import MagicMock

from src.synthesizer import VOICE_ID, synthesize_segment, run_synthesize_stage


def _pcm_silence(seconds: float = 0.1) -> bytes:
    return b"\x00\x00" * int(44100 * seconds)


def _mock_client(pcm: bytes):
    client = MagicMock()
    client.text_to_speech.convert.return_value = iter([pcm])
    return client


def test_synthesize_segment_writes_valid_wav():
    client = _mock_client(_pcm_silence())
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "seg001.wav"
        result = synthesize_segment("안녕하세요", out, VOICE_ID, client)
    assert result is True
    assert out.exists()
    with wave.open(str(out), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 44100


def test_synthesize_segment_skips_nonempty_file():
    client = _mock_client(_pcm_silence())
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "seg001.wav"
        out.write_bytes(b"FAKE" * 100)
        result = synthesize_segment("안녕하세요", out, VOICE_ID, client)
    assert result is False
    client.text_to_speech.convert.assert_not_called()


def test_synthesize_segment_returns_false_on_api_error():
    client = MagicMock()
    client.text_to_speech.convert.side_effect = Exception("TTS error")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "seg001.wav"
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
        client = _mock_client(_pcm_silence())
        counts = run_synthesize_stage(tmpdir, ["ko"], client)
    assert counts["synthesized"] == 1
    assert counts["cached"] == 0
    assert counts["errors"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_synthesizer.py -v
```

Expected: `ImportError: cannot import name 'VOICE_ID' from 'src.synthesizer'`

- [ ] **Step 3: Implement `src/synthesizer.py`**

```python
import json
import logging
import wave
from pathlib import Path

from elevenlabs.client import ElevenLabs

logger = logging.getLogger(__name__)

VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel — ElevenLabs stock female voice
MODEL_ID = "eleven_multilingual_v2"
SAMPLE_RATE = 44100


def synthesize_segment(
    text: str,
    out_path: Path,
    voice_id: str,
    client: ElevenLabs,
) -> bool:
    if out_path.exists() and out_path.stat().st_size > 0:
        logger.debug("Cached: %s", out_path.name)
        return False
    try:
        chunks = client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id=MODEL_ID,
            output_format="pcm_44100",
        )
        pcm = b"".join(chunks)
    except Exception as e:
        logger.error("ElevenLabs TTS failed (%s): %s", out_path.name, e)
        return False

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)
    return True


def run_synthesize_stage(
    output_dir: Path,
    langs: list[str],
    client: ElevenLabs,
    voice_id: str = VOICE_ID,
) -> dict:
    counts = {"synthesized": 0, "cached": 0, "errors": 0}
    for lang in langs:
        trans_root = output_dir / "translations" / lang
        if not trans_root.exists():
            continue
        for json_path in sorted(trans_root.rglob("*.json")):
            module = json_path.parent.name
            try:
                segments = json.loads(json_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                logger.error("Cannot read %s: %s", json_path, e)
                counts["errors"] += 1
                continue
            for seg in segments:
                out_path = (
                    output_dir / "audio_raw" / lang / module
                    / f"{json_path.stem}_seg{seg['index']:03d}.wav"
                )
                if out_path.exists() and out_path.stat().st_size > 0:
                    counts["cached"] += 1
                    continue
                ok = synthesize_segment(seg["translated"], out_path, voice_id, client)
                if ok:
                    counts["synthesized"] += 1
                else:
                    counts["errors"] += 1
    return counts
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_synthesizer.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/synthesizer.py tests/test_synthesizer.py
git commit -m "feat: Stage 2 synthesis with ElevenLabs TTS and WAV checkpointing"
```

---

### Task 5: Assembly Stage

**Files:**
- Create: `src/assembler.py`
- Create: `tests/test_assembler.py`

**Interfaces:**
- Consumes: `Segment`, `write_srt` from `src.srt_parser`; translation JSONs; raw WAVs from Stage 2
- Produces:
  - `srt_time_to_seconds(t: str) -> float` — `"00:00:03,750"` → `3.75`
  - `build_atempo_filter(ratio: float) -> str` — returns chained atempo filter string safe for ffmpeg `-filter:a`
  - `get_audio_duration(path: Path) -> float` — ffprobe; raises on failure
  - `timescale_segment(raw_path: Path, scaled_path: Path, target_duration: float) -> bool` — `True` = scaled with ffmpeg, `False` = raw copied as fallback
  - `assemble_srt_file(translation: list[dict], raw_dir: Path, final_wav: Path, final_srt: Path) -> dict` — `{"warnings": int}`
  - `run_assemble_stage(output_dir: Path, langs: list[str]) -> dict` — `{"assembled": int, "warnings": int, "errors": int}`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_assembler.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_assembler.py -v
```

Expected: `ImportError: cannot import name 'srt_time_to_seconds' from 'src.assembler'`

- [ ] **Step 3: Implement `src/assembler.py`**

```python
import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from src.srt_parser import Segment, write_srt

logger = logging.getLogger(__name__)


def srt_time_to_seconds(t: str) -> float:
    time_part, ms = t.split(",")
    h, m, s = time_part.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def build_atempo_filter(ratio: float) -> str:
    if 0.5 <= ratio <= 2.0:
        return f"atempo={ratio:g}"
    if ratio > 2.0:
        return f"atempo=2.0,atempo={ratio / 2.0:g}"
    return f"atempo=0.5,atempo={ratio / 0.5:g}"


def get_audio_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def timescale_segment(raw_path: Path, scaled_path: Path, target_duration: float) -> bool:
    scaled_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        actual = get_audio_duration(raw_path)
        ratio = actual / target_duration
        atempo = build_atempo_filter(ratio)
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(raw_path), "-filter:a", atempo, str(scaled_path)],
            capture_output=True,
            check=True,
        )
        return True
    except Exception as e:
        logger.warning("ffmpeg atempo failed for %s: %s — copying raw", raw_path.name, e)
        shutil.copy2(raw_path, scaled_path)
        return False


def assemble_srt_file(
    translation: list[dict],
    raw_dir: Path,
    final_wav: Path,
    final_srt: Path,
) -> dict:
    warnings = 0
    final_wav.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        scaled_paths = []

        for seg in translation:
            raw_path = raw_dir / f"{final_wav.stem}_seg{seg['index']:03d}.wav"
            scaled_path = tmp_path / f"seg{seg['index']:03d}.wav"
            target = srt_time_to_seconds(seg["end"]) - srt_time_to_seconds(seg["start"])
            if not raw_path.exists():
                logger.warning("Missing raw segment: %s", raw_path)
                warnings += 1
                continue
            ok = timescale_segment(raw_path, scaled_path, target)
            if not ok:
                warnings += 1
            scaled_paths.append(scaled_path)

        if not scaled_paths:
            logger.error("No segments available for %s", final_wav.name)
            return {"warnings": warnings}

        concat_list = tmp_path / "concat.txt"
        concat_list.write_text(
            "\n".join(f"file '{p}'" for p in scaled_paths),
            encoding="utf-8",
        )
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", str(concat_list),
                "-ar", "44100", "-ac", "1",
                str(final_wav),
            ],
            capture_output=True,
            check=True,
        )

    segments = [
        Segment(index=seg["index"], start=seg["start"], end=seg["end"], text=seg["translated"])
        for seg in translation
    ]
    write_srt(segments, final_srt)
    return {"warnings": warnings}


def run_assemble_stage(output_dir: Path, langs: list[str]) -> dict:
    counts = {"assembled": 0, "warnings": 0, "errors": 0}
    for lang in langs:
        trans_root = output_dir / "translations" / lang
        if not trans_root.exists():
            continue
        for json_path in sorted(trans_root.rglob("*.json")):
            module = json_path.parent.name
            try:
                translation = json.loads(json_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                logger.error("Cannot read %s: %s", json_path, e)
                counts["errors"] += 1
                continue
            raw_dir = output_dir / "audio_raw" / lang / module
            final_wav = output_dir / "final" / lang / module / (json_path.stem + ".wav")
            final_srt = output_dir / "final" / lang / module / (json_path.stem + ".srt")
            try:
                result = assemble_srt_file(translation, raw_dir, final_wav, final_srt)
                counts["assembled"] += 1
                counts["warnings"] += result["warnings"]
            except Exception as e:
                logger.error("Assembly failed for %s: %s", json_path.name, e)
                counts["errors"] += 1
    return counts
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_assembler.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/assembler.py tests/test_assembler.py
git commit -m "feat: Stage 3 assembly with ffmpeg atempo time-scaling and SRT output"
```

---

### Task 6: Pipeline Entry Point

**Files:**
- Create: `pipeline.py`

**Interfaces:**
- Consumes: `run_translate_stage`, `run_synthesize_stage`, `run_assemble_stage`
- Produces: runnable CLI `python pipeline.py [--stage translate|synthesize|assemble]`

- [ ] **Step 1: Set up your `.env` file**

```bash
cp .env.example .env
```

Edit `.env` and fill in both keys:
```
ANTHROPIC_API_KEY=sk-ant-...
ELEVENLABS_API_KEY=sk_...
```

To get your ElevenLabs API key: log in at elevenlabs.io → profile icon (bottom left) → **API Keys** → create new key.

- [ ] **Step 2: Implement `pipeline.py`**

```python
import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

BASE_DIR = Path(__file__).parent
CAPTIONS_DIR = BASE_DIR / "Captions"
OUTPUT_DIR = BASE_DIR / "output"
LANGS = ["ko", "zh"]


def _check_ffmpeg() -> None:
    import subprocess
    for tool in ("ffmpeg", "ffprobe"):
        try:
            subprocess.run([tool, "-version"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            sys.exit(f"ERROR: {tool} not found. Install with: brew install ffmpeg")


def _anthropic_client():
    import anthropic
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("ERROR: ANTHROPIC_API_KEY not set in .env")
    return anthropic.Anthropic(api_key=key)


def _elevenlabs_client():
    from elevenlabs.client import ElevenLabs
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("ERROR: ELEVENLABS_API_KEY not set in .env")
    return ElevenLabs(api_key=key)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Translate SRT captions to Korean and Chinese with ElevenLabs audio"
    )
    parser.add_argument(
        "--stage",
        choices=["translate", "synthesize", "assemble"],
        help="Run only one stage (default: run all three in order)",
    )
    args = parser.parse_args()

    _check_ffmpeg()

    run_all = args.stage is None

    if run_all or args.stage == "translate":
        from src.translator import run_translate_stage
        print("=== Stage 1: Translation ===")
        counts = run_translate_stage(CAPTIONS_DIR, OUTPUT_DIR, LANGS, _anthropic_client())
        print(f"Stage 1: {counts['translated']} files translated, "
              f"{counts['cached']} cached, {counts['errors']} errors\n")

    if run_all or args.stage == "synthesize":
        from src.synthesizer import run_synthesize_stage
        print("=== Stage 2: Audio Synthesis ===")
        counts = run_synthesize_stage(OUTPUT_DIR, LANGS, _elevenlabs_client())
        print(f"Stage 2: {counts['synthesized']} segments synthesized, "
              f"{counts['cached']} cached, {counts['errors']} errors\n")

    if run_all or args.stage == "assemble":
        from src.assembler import run_assemble_stage
        print("=== Stage 3: Time-scale & Assembly ===")
        counts = run_assemble_stage(OUTPUT_DIR, LANGS)
        print(f"Stage 3: {counts['assembled']} files assembled, "
              f"{counts['warnings']} warnings, {counts['errors']} errors\n")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all 20 tests PASS (4 in srt_parser, 4 in translator, 4 in synthesizer, 8 in assembler).

- [ ] **Step 4: Run Stage 1 on real files (uses Claude API credits)**

```bash
python pipeline.py --stage translate
```

Expected output:
```
=== Stage 1: Translation ===
Stage 1: 62 files translated, 0 cached, 0 errors
```
(31 SRT files × 2 languages = 62 translation jobs)

Open `output/translations/ko/Gen Intro/01 Gen Intro_Intro.json` and verify the translated text looks like correct Korean oncology terminology.

- [ ] **Step 5: Run Stage 2 (uses ElevenLabs API credits)**

```bash
python pipeline.py --stage synthesize
```

Expected output:
```
=== Stage 2: Audio Synthesis ===
Stage 2: NNN segments synthesized, 0 cached, 0 errors
```

Play one of the generated files in `output/audio_raw/ko/` to confirm it sounds like Korean speech.

- [ ] **Step 6: Run Stage 3**

```bash
python pipeline.py --stage assemble
```

Expected output:
```
=== Stage 3: Time-scale & Assembly ===
Stage 3: 62 files assembled, 0 warnings, 0 errors
```

Check `output/final/ko/` and `output/final/zh/` — each module directory should have one `.wav` and one `.srt` per SRT source file.

- [ ] **Step 7: Full pipeline re-run to verify checkpointing**

```bash
python pipeline.py
```

Expected: all three stages report `0 translated / NNN cached / 0 errors` — nothing is reprocessed.

- [ ] **Step 8: Commit**

```bash
git add pipeline.py
git commit -m "feat: pipeline CLI with three-stage orchestration and summary output"
```
