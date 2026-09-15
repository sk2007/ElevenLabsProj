# ElevenLabs Video Dubbing Pipeline

This project automates the translation and dubbing of oncology patient education videos into multiple languages using OpenAI GPT-4o for translation and ElevenLabs for text-to-speech synthesis.

## Supported Languages

| Code | Language          |
|------|-------------------|
| ko   | Korean            |
| zh   | Chinese (Simplified) |
| ja   | Japanese          |
| hy   | Armenian          |
| fa   | Farsi (Persian)   |
| es   | Spanish           |

---

## Root-Level Files

### `pipeline.py`

The main orchestration script. This is the entry point for running the entire dubbing pipeline. It:

- Validates that `ffmpeg` and `ffprobe` are installed
- Creates OpenAI and ElevenLabs API clients from `.env`
- Runs pipeline stages in sequence (or individually via `--stage` flag)
- Handles command-line argument parsing

**Usage:**
```bash
python pipeline.py              # Runs translate → synthesize → assemble
python pipeline.py --stage translate   # Run only translation
python pipeline.py --stage synthesize  # Run only audio synthesis
python pipeline.py --stage assemble    # Run only assembly
python pipeline.py --stage dub         # Run only video dubbing
```

---

### `viewer.py`

A Flask web application that provides an interactive QA viewer for reviewing dubbed content. It serves as both the UI and API for browsing translations, audio, and dubbed videos.

**Key responsibilities:**
- Serves the main HTML interface at `/`
- Provides API endpoints for content discovery and playback
- Streams audio files, subtitle tracks, and dubbed videos

**API Endpoints:**
| Endpoint | Purpose |
|----------|---------|
| `/api/index` | Lists available languages and modules |
| `/api/videos` | Lists dubbed videos and their availability per language |
| `/api/modules` | Lists module structure with per-language video availability |
| `/api/segments/<lang>/<module>/<stem>` | Returns translation segments as JSON |
| `/audio/<lang>/<module>/` | Serves assembled WAV audio |
| `/video/<lang>/` | Serves dubbed MP4 videos |
| `/module-video/<module>/<lang>/` | Serves module-dubbed videos |
| `/subtitles/<audio_lang>/<sub_lang>/<module>/<stem>` | Generates VTT subtitles with correct timing |

**Usage:**
```bash
python viewer.py
# Opens at http://localhost:5000
```

---

### `requirements.txt`

Lists all Python dependencies:
- `openai` — OpenAI API client for translation
- `elevenlabs` — ElevenLabs API client for text-to-speech
- `python-dotenv` — Environment variable loading
- `flask` — Web framework for the QA viewer

---

### `.env` (not in git)

Configuration file for API keys:
```
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=...
```

---

## Source Files (`src/`)

### `src/translator.py`

Handles Stage 1: Translating English subtitles to target languages.

**Key components:**
- `LANG_NAMES` — Maps language codes to full names for OpenAI prompts
- `translate_file()` — Translates a single SRT file's segments
- `run_translate_stage()` — Processes all SRT files across all languages

**Process:**
1. Reads SRT file and parses segments
2. Sends batch to OpenAI GPT-4o with medical translation prompt
3. Handles missing segments by retrying or falling back to English
4. Saves JSON with original and translated text per segment

**Output:** `output/translations/<lang>/<module>/<stem>.json`

---

### `src/synthesizer.py`

Handles Stage 2: Converting translated text to audio using ElevenLabs.

**Key components:**
- `VOICE_ID` — "Rachel" (21m00Tcm4TlvDq8ikWAM), ElevenLabs stock female voice
- `MODEL_ID` — `eleven_multilingual_v2`
- `synthesize_segment()` — Generates TTS for a single text segment
- `run_synthesize_stage()` — Processes all translation JSON files

**Process:**
1. Reads translation JSON
2. Sends each segment's translated text to ElevenLabs
3. Saves individual MP3 files per segment
4. Skips existing files (caching)

**Output:** `output/audio_raw/<lang>/<module>/<stem>_seg001.mp3`

---

### `src/assembler.py`

Handles Stage 3: Assembling individual audio segments into a single file with correct timing.

**Key components:**
- `srt_time_to_seconds()` — Converts SRT timestamp format to float
- `get_audio_duration()` — Uses ffprobe to measure audio file length
- `timescale_segment()` — Adjusts audio speed to match target duration (using ffmpeg atempo filter)
- `assemble_srt_file()` — Concatenates segments and recalculates timestamps
- `run_assemble_stage()` — Processes all translation files

**Process:**
1. Reads translation JSON
2. Gets actual duration of each raw audio segment
3. Concatenates all segments using ffmpeg
4. Recalculates SRT timestamps based on actual audio durations (ElevenLabs audio may be slightly different length than original timing)
5. Writes final WAV and SRT files

**Why recalculate timestamps?** ElevenLabs may read longer/shorter than the original subtitle timing, so the script measures actual audio durations and rebuilds the SRT from scratch.

**Output:**
- `output/final/<lang>/<module>/<stem>.wav`
- `output/final/<lang>/<module>/<stem>.srt`

---

### `src/module_dubber.py`

Handles Stage 4: Building final dubbed videos with embedded subtitles.

**Key components:**
- `compute_output_duration()` — Determines if trailing video trim is needed
- `_probe_duration()` — Gets video/audio duration via ffprobe
- `_last_caption_end()` — Finds the end time from SRT
- `build_ffmpeg_cmd()` — Constructs ffmpeg command for muxing
- `_dub_part()` — Processes a single video part
- `run_module_dub_stage()` — Runs dubbing for all modules

**Process:**
1. Takes source video (`*_multisub.mp4`), assembled WAV, and SRT files
2. Muxes video track with dubbed audio track
3. Embeds all available subtitle tracks as `mov_text`
4. Trims trailing no-audio portion if the video extends beyond the audio
5. Outputs per-language MP4 files

**Output:** `output/<module>_dubbed/<lang>/<video>_<lang>.mp4`

**Usage:**
```bash
python src/module_dubber.py --modules gen-intro mucositis
```

---

### `src/modules.py`

Central registry that defines all video modules, their parts, and output paths.

**Key components:**
- `LANGS` — List of supported language codes
- `LANG_NAMES` — Human-readable names for UI display
- `LANG_SUB_CODE` — ISO 639-2/B codes for embedded subtitle metadata
- `Part` — Dataclass representing one video part within a module
- `Module` — Dataclass representing a group of related video parts
- `_numbered()` — Factory for creating standard 5-part modules (Intro, Parts 1-5, Summary)
- `MODULES` — Dictionary of all registered modules

**Registered Modules:**
| Key | Label | Source Directory | Output Directory |
|-----|-------|------------------|------------------|
| gen-intro | Gen Intro | `gen_intro_vids` | `gen_intro_dubbed` |
| mucositis | Mucositis | `mucositis_vids` | `mucositis_dubbed` |
| nutrition | Nutrition | `nutrition_vids` | `nutrition_dubbed` |
| pain-management | Pain Management | `pain_management_vids` | `pain_management_dubbed` |
| skincare | Skin Care Management | `skincare_vids` | `skincare_dubbed` |

**Part methods:**
- `source_video()` — Path to source `*_multisub.mp4`
- `wav_path()` — Path to assembled WAV in `output/final/`
- `srt_path()` — Path to assembled SRT in `output/final/`
- `out_path()` — Path to final dubbed MP4 in `output/<module>_dubbed/`

---

### `src/srt_parser.py`

Utility for parsing SRT subtitle files.

**Key components:**
- `Segment` — Dataclass: `index`, `start`, `end`, `text`
- `parse_srt()` — Reads SRT file and returns list of Segment objects
- `write_srt()` — Writes list of Segment objects to SRT format

**SRT format:**
```
1
00:00:00,000 --> 00:00:05,200
Subtitle text here

2
00:00:05,500 --> 00:00:10,000
More subtitle text
```

---

### `src/exporter.py`

Utility functions for exporting dubbed videos. Used by `viewer.py` for serving videos with proper headers.

---

### `src/video_dubber.py`

Legacy dubbing logic. Contains older implementation that may still be used for specific exports. Check recent commits for current dubbing workflow.

---

### `src/__init__.py`

Empty file that marks `src/` as a Python package.

---

## Test Files (`tests/`)

### `test_srt_parser.py`

Tests for SRT parsing and writing functionality.

---

### `test_translator.py`

Tests for translation logic, mocking OpenAI API responses.

---

### `test_synthesizer.py`

Tests for ElevenLabs TTS synthesis, mocking API responses.

---

### `test_assembler.py`

Tests for audio assembly and timestamp recalculation.

---

### `test_module_dubber.py`

Tests for video dubbing workflow.

---

### `test_modules.py`

Tests for module registry configuration.

---

### `test_exporter.py`

Tests for video export functionality.

---

### `test_viewer.py`

Tests for Flask viewer endpoints and responses.

---

## Directory Structure

```
ElevenLabsProj/
├── pipeline.py              # Main entry point, orchestrates stages
├── viewer.py                # Flask QA web app
├── requirements.txt         # Python dependencies
├── .env                     # API keys (not tracked)
│
├── Captions/                # Source English SRT files
│   └── <module>/
│       └── *.srt
│
├── <module>_vids/           # Source videos (gen_intro_vids, mucositis_vids, etc.)
│   └── *_multisub.mp4
│
├── src/
│   ├── __init__.py
│   ├── translator.py        # Stage 1: OpenAI translation
│   ├── synthesizer.py       # Stage 2: ElevenLabs TTS
│   ├── assembler.py         # Stage 3: Audio assembly
│   ├── module_dubber.py     # Stage 4: Video muxing
│   ├── modules.py           # Module registry and paths
│   ├── srt_parser.py        # SRT parsing utilities
│   ├── exporter.py          # Export utilities
│   └── video_dubber.py      # Legacy dubbing
│
├── output/
│   ├── translations/        # Stage 1 output: JSON translations
│   │   └── <lang>/<module>/*.json
│   │
│   ├── audio_raw/           # Stage 2 output: Per-segment MP3s
│   │   └── <lang>/<module>/*_seg001.mp3
│   │
│   ├── final/               # Stage 3 output: Assembled WAV + SRT
│   │   └── <lang>/<module>/*.wav, *.srt
│   │
│   ├── dubbed_elevenlabs/   # Legacy dubbed videos
│   │
│   └── *_dubbed/            # Stage 4 output: Final MP4s
│       └── <lang>/<video>_<lang>.mp4
│
└── tests/
    ├── test_*.py            # Unit tests for each module
```

---

## Data Flow

```
Captions/*.srt
       ↓
  translator.py
       ↓
  output/translations/*.json
       ↓
  synthesizer.py
       ↓
  output/audio_raw/*_seg*.mp3
       ↓
  assembler.py
       ↓
  output/final/*.wav + *.srt
       ↓
  module_dubber.py
       ↓
  output/*_dubbed/*.mp4
```

---

## Running Tests

```bash
pytest tests/
```