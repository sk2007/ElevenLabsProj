# Web Viewer — Design Spec

**Date:** 2026-07-13  
**Purpose:** Internal QA tool for reviewing Korean, Chinese, and Telugu translations of oncology patient education videos.

---

## Overview

A local Flask web application that lets staff review the translation pipeline output. For each source video part (SRT file), reviewers can play the translated audio, watch synced captions update in real time, and scan a side-by-side segment table comparing original English to the translated text.

Run with `python3 viewer.py`, open `localhost:5000`.

---

## Architecture

Single Python file (`viewer.py`) with three responsibilities:

| Endpoint | Purpose |
|---|---|
| `GET /api/index` | Scans `output/final/` and returns the full module → parts → languages tree as JSON |
| `GET /api/segments/<lang>/<module>/<stem>` | Reads `output/translations/<lang>/<module>/<stem>.json` and returns segments with `index`, `start`, `end`, `original`, `translated` |
| `GET /audio/<lang>/<module>/<filename>` | Streams the WAV file with HTTP range request support (required for audio scrubbing) |

The frontend is a single HTML page embedded in `viewer.py` as a Jinja2 template string — no separate files, no npm, no build step.

---

## UI Layout

Three zones:

```
┌─────────────────────────────────────────────────────────────┐
│  [Korean]  [Chinese]  [Telugu]              Language toggle  │
├──────────────┬──────────────────────────────────────────────┤
│              │  ▶ ━━━━━━━━━━━━━━━━━━━  0:12 / 1:43         │
│  Gen Intro   │                                              │
│    01 Intro  │  ┌─────────────────────────────────────┐    │
│  > 02 Part 1 │  │  Current segment text shown here     │    │
│    03 Part 2 │  └─────────────────────────────────────┘    │
│    ...       │                                              │
│              │  #  │ Original              │ Translated     │
│  Mucositis   │ ────┼───────────────────────┼───────────────│
│    01 Intro  │  1  │ What is radiation...  │ <translated>   │
│    ...       │► 2  │ Introduction          │ <translated>   │
│              │  3  │ While you may have... │ <translated>   │
│  Nutrition   │  4  │ Radiation therapy...  │ <translated>   │
│    ...       │                                              │
└──────────────┴──────────────────────────────────────────────┘
```

**Sidebar (~250px):** Modules collapsed by default; click to expand and show parts. Active part is highlighted.

**Language toggle (top bar):** Three buttons — Korean, Chinese, Telugu. Switching reloads segments and audio for the current part without losing sidebar position. Audio restarts from `currentTime = 0` on language switch.

**Caption box:** Large-text display of the current segment's translated text. Updates as audio plays.

**Segment table:** Full list of all segments for the selected file. Active row is highlighted and auto-scrolls into view. Clicking any row seeks audio to that segment's start time.

---

## Data Flow

**On page load:**
1. `GET /api/index` → renders sidebar (modules collapsed)

**On part selection:**
1. `GET /api/segments/{lang}/{module}/{stem}` → stores segments array in JS, renders table
2. Sets `<audio src="/audio/{lang}/{module}/{stem}.wav">`

**On language toggle:**
1. Same part stem, different lang — re-fetches segments and swaps audio src
2. Audio resets to start

**Playback sync (timeupdate loop):**
- `audio.addEventListener('timeupdate')` fires ~4×/sec
- JS scans segments array for the segment whose `[start, end]` straddles `audio.currentTime`
- Highlights that row + updates caption box
- Active row auto-scrolls into view on change

**Click-to-seek:**
- Clicking a segment row calls `audio.currentTime = segment.startSeconds`

**SRT timestamp parsing (client-side JS):**
- Format `HH:MM:SS,mmm` → `h*3600 + m*60 + s + ms/1000`
- Segment start/end come as strings from the API; parsed once on load

---

## Backend Details

**`/api/index`** walks `output/final/` and returns:
```json
{
  "languages": ["ko", "zh", "te"],
  "lang_names": {"ko": "Korean", "zh": "Chinese (Simplified)", "te": "Telugu"},
  "modules": {
    "Gen Intro": ["01 Gen Intro_Intro", "02 Gen Intro_Part 1", ...],
    "Mucositis": [...],
    ...
  }
}
```

**`/api/segments/<lang>/<module>/<stem>`** reads `output/translations/<lang>/<module>/<stem>.json` directly and returns its array. The translation JSON already contains `index`, `start`, `end`, `original`, and `translated` fields — no transformation needed.

**`/audio/<lang>/<module>/<filename>`** uses Flask's `send_file` with `conditional=True` to support HTTP range requests (byte-range seeking).

---

## File Map

| File | Role |
|---|---|
| `viewer.py` | Flask app — all routes + HTML template |
| `requirements.txt` | Add `flask>=3.0.0` |

No new directories. No changes to `src/`, `output/`, or `pipeline.py`.

---

## Non-Goals

- No editing or re-running the pipeline from the UI
- No authentication
- No deployment — local only
- No mobile optimization
