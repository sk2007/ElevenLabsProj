# ElevenLabs Korean & Chinese Translation Pipeline — Design Spec

**Date:** 2026-07-09  
**Status:** Approved

---

## Background & Constraints

The project contains medical oncology educational video modules across 5 topics:
- General Intro
- Mucositis
- Nutrition
- Pain Management
- Skin Care Management

Each module has English `.srt` caption files and `.wav` audio files recorded by a professional voice actor. **The voice actor has refused to grant permission to clone her voice.** Therefore:

- We must NOT upload the original `.wav` files to ElevenLabs
- We must NOT clone or replicate her voice in any way
- The original audio in `VO/` is left completely untouched

The translation pipeline works exclusively from the `.srt` caption files (which contain the full English script) and produces new Korean and Chinese audio using an ElevenLabs stock female voice.

---

## Goal

Produce, for each SRT file in both Korean (`ko`) and Chinese (`zh`):
1. A translated `.srt` file with original timestamps preserved
2. A `.wav` audio file synthesized by a stock ElevenLabs voice, time-scaled to match the original SRT segment durations

---

## Architecture

### Repository Layout

```
ElevenLabsProj/
  Captions/            ← input SRT files (read-only)
  VO/                  ← original audio (never touched)
  output/
    translations/
      ko/              ← Stage 1 JSON output (Korean)
      zh/              ← Stage 1 JSON output (Chinese)
    audio_raw/
      ko/              ← Stage 2 raw TTS .wav per segment (Korean)
      zh/              ← Stage 2 raw TTS .wav per segment (Chinese)
    final/
      ko/              ← Stage 3 final .wav + .srt per module file (Korean)
      zh/              ← Stage 3 final .wav + .srt per module file (Chinese)
  pipeline.py          ← main script
  .env                 ← API keys (gitignored)
  requirements.txt
  docs/
    superpowers/
      specs/
        2026-07-09-elevenlabs-translation-pipeline-design.md
```

### Three-Stage Checkpointed Pipeline

Each stage writes outputs to disk before the next stage begins. On re-run, stages check for existing outputs and skip completed work — protecting API spend if the script is interrupted.

```
Stage 1: Translate      Stage 2: Synthesize      Stage 3: Time-scale & Assemble
─────────────────────   ──────────────────────   ──────────────────────────────
SRT files (English)  →  Translation JSONs     →  Raw segment .wavs
Claude API              ElevenLabs TTS API        ffmpeg atempo
                                              →  Final .wav + .srt per file
```

---

## Stage Details

### Stage 1 — Translation (Claude API)

**Input:** All `.srt` files under `Captions/`  
**Output:** `output/translations/{lang}/{module}/{filename}.json`

Each SRT file's segments are batched into a single Claude API call. Batching gives the model full sequence context, which improves consistency of medical terminology across a module.

Translation JSON structure per file:
```json
[
  {
    "index": 1,
    "start": "00:00:00,458",
    "end": "00:00:03,750",
    "original": "What is radiation therapy and what to expect?",
    "translated": "방사선 치료란 무엇이며 어떤 것을 예상할 수 있나요?"
  },
  ...
]
```

Claude prompt context: the model is told this is an oncology patient education script to ensure accurate medical terminology.

**Checkpointing:** If a `.json` file already exists with the correct number of segments, the file is skipped. A failed translation does not write a partial JSON, so the next run retries cleanly.

**Languages:** `ko` (Korean), `zh` (Chinese Simplified)

---

### Stage 2 — Audio Synthesis (ElevenLabs)

**Input:** Translation JSONs from Stage 1  
**Output:** `output/audio_raw/{lang}/{module}/{filename}_seg{n:03d}.wav`

For each translated segment, one ElevenLabs TTS request is made:
- **Model:** `eleven_multilingual_v2` (supports Korean and Chinese)
- **Voice:** ElevenLabs stock female voice — default `Rachel` (versatile, supports both target languages). Easily changed via a `ELEVENLABS_VOICE_ID` constant at the top of the script.
- **Output format:** `.wav`, 44.1kHz

**Checkpointing:** If a segment `.wav` already exists and is non-empty (size > 0 bytes), it is skipped.

---

### Stage 3 — Time-scale & Assembly (ffmpeg)

**Input:** Raw segment `.wav` files + original SRT timestamps  
**Output:**
- `output/final/{lang}/{module}/{filename}.wav` — full concatenated audio
- `output/final/{lang}/{module}/{filename}.srt` — translated text, original timestamps

For each segment:
1. **ffprobe** measures the actual duration of the raw TTS audio
2. **Target duration** is calculated from the SRT timestamps (`end - start`, in seconds)
3. **Tempo ratio** = `actual_duration / target_duration`
4. **ffmpeg `atempo`** stretches or compresses to match — the `atempo` filter is limited to 0.5–2.0×, so extreme ratios chain two filters:
   - ratio > 2.0: `atempo=2.0,atempo={ratio/2.0}`
   - ratio < 0.5: `atempo=0.5,atempo={ratio/0.5}`
5. All time-scaled segments are **concatenated** into a single `.wav` per SRT file
6. A new `.srt` file is written with original timestamps and translated text

---

## Error Handling

| Failure Point | Behavior |
|---|---|
| Claude translation call fails | Log error, skip file (no partial JSON written), retry on next run |
| ElevenLabs TTS call fails | Log error, skip segment (no .wav written), retry on next run |
| ffmpeg atempo fails (extreme ratio) | Log warning, copy raw audio unscaled, continue pipeline |
| Missing ffmpeg/ffprobe | Script exits immediately with clear installation instructions |

On completion, the script prints a summary:
```
Stage 1: 38 files translated, 0 skipped (errors), 0 skipped (cached)
Stage 2: 312 segments synthesized, 0 errors, 0 cached
Stage 3: 38 assemblies complete, 0 warnings
```

---

## API Keys & Setup

### .env file (gitignored)
```
ANTHROPIC_API_KEY=sk-ant-...
ELEVENLABS_API_KEY=sk_...
```

**To get your ElevenLabs API key:**
1. Log in to elevenlabs.io
2. Click your profile icon (bottom left)
3. Go to **API Keys**
4. Create a new key and copy it into `.env`

### Dependencies
```
anthropic
elevenlabs
python-dotenv
```

**System requirement:** `ffmpeg` must be installed.
```bash
brew install ffmpeg
```

### Install Python dependencies
```bash
pip install -r requirements.txt
```

---

## Running the Pipeline

```bash
# Run all three stages (skips already-completed work)
python pipeline.py

# Run only translation stage
python pipeline.py --stage translate

# Run only synthesis stage
python pipeline.py --stage synthesize

# Run only time-scale/assembly stage
python pipeline.py --stage assemble
```

---

## Constraints Summary

| Constraint | How addressed |
|---|---|
| Cannot upload voice actor audio | Pipeline never reads from `VO/` |
| Cannot clone voice actor voice | Uses ElevenLabs stock voice only |
| API cost protection | Checkpointing skips completed segments on re-run |
| Medical terminology accuracy | Claude batches full file context + oncology prompt |
| Timing must match original video | ffmpeg atempo time-scales each segment to SRT window |
