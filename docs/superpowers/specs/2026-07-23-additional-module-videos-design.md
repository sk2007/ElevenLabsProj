# Design: Add Mucositis / Nutrition / Pain Management / Skin Care videos to the viewer

**Date:** 2026-07-23
**Status:** Approved (design), pending implementation plan

## Goal

Add four new subtitled video modules to the Translation QA Viewer, behaving
exactly like the existing "Gen Intro Videos" section: each module lists its
parts in the sidebar, clicking a part plays the video, the top language button
switches the **audio** language, and subtitles automatically follow the playing
language (all five languages selectable in the player caption menu, timed to
that audio).

New modules:

| Module key       | Sidebar label          | `output/final` dir name  | Source video dir       |
|------------------|------------------------|--------------------------|------------------------|
| `mucositis`      | Mucositis              | `Mucositis`              | `mucositis_vids`       |
| `nutrition`      | Nutrition              | `Nutrition`              | `nutrition_vids`       |
| `pain-management`| Pain Management        | `Pain Management`        | `pain_management_vids` |
| `skincare`       | Skin Care Management   | `Skin Care Management`   | `skincare_vids`        |

## Background / current state

- The uploaded `*_multisub.mp4` files (in `mucositis_vids/`, etc.) contain a
  **single English audio track** plus six embedded `mov_text` subtitle tracks
  (eng + kor/zho/jpn/hye/per). They cannot switch audio on their own.
- Gen intro switches audio because a **build step** produced per-language dubbed
  videos in `output/gen_intro_dubbed/<lang>/gen_intro_vN_<lang>.mp4`, created by
  `src/gen_intro_dubber.py` (mux each language's `output/final` WAV onto the
  multisub video, re-embed all five subtitle SRTs).
- The viewer serves those per-language videos and overlays live captions as
  **WebVTT sidecar `<track>`s** via the already-generic endpoint
  `/subtitles/<audio_lang>/<sub_lang>/<module>/<stem>`, which reads timing from
  `output/final/<audio_lang>/<module>/<stem>.srt` and text from
  `output/translations/<sub_lang>/<module>/<stem>.json` (or the SRT itself when
  audio_lang == sub_lang). The embedded `mov_text` tracks are only for
  downloaded-file portability; the browser uses the WebVTT sidecars.
- All required assets already exist for the four new modules × five languages:
  `output/final/<lang>/<Module>/<stem>.wav` + `.srt`, and
  `output/translations/<lang>/<Module>/<stem>.json`.

## Part mapping (video filename → assembled stem → display label)

All stems below are the exact filenames in `output/final/<lang>/<Module>/`.
Note the pre-existing "Paint Management" typo in the Pain Management Intro stem.

**Mucositis** (`mucositis_vids/`)
| Video (`*_multisub.mp4`)   | Stem                    | Label   |
|----------------------------|-------------------------|---------|
| `mucositis_introduction`   | `01 Mucositis_Intro`    | Intro   |
| `mucositis_part1`          | `02 Mucositis_Part 1`   | Part 1  |
| `mucositis_part2`          | `03 Mucositis_Part 2`   | Part 2  |
| `mucositis_part3`          | `04 Mucositis_Part 3`   | Part 3  |
| `mucositis_part4`          | `05 Mucositis_Part 4`   | Part 4  |
| `mucositis_part5`          | `06 Mucositis_Part 5`   | Part 5  |
| `mucositis_summary`        | `07 Mucositis_Summary`  | Summary |

**Nutrition** (`nutrition_vids/`) — same pattern:
`nutrition_introduction`→`01 Nutrition_Intro` (Intro),
`nutrition_part1..5`→`02..06 Nutrition_Part 1..5`,
`nutrition_summary`→`07 Nutrition_Summary` (Summary).

**Pain Management** (`pain_management_vids/`) — irregular, confirmed with user:
| Video                      | Stem                          | Label  |
|----------------------------|-------------------------------|--------|
| `painmgmt_introduction`    | `01 Paint Management_Intro`   | Intro  |
| `painmgmt_part2`           | `02 Pain Management_Part 1`   | Part 1 |
| `painmgmt_part3`           | `03 Pain Management_Part 2`   | Part 2 |

**Skin Care Management** (`skincare_vids/`)
| Video                      | Stem                              | Label  |
|----------------------------|-----------------------------------|--------|
| `skincare_introduction`    | `01 Skin Care Management_Intro`   | Intro  |
| `skincare_part1`           | `02 Skin Care Management_Part 1`  | Part 1 |
| `skincare_part2`           | `03 Skin Care Management_Part 2`  | Part 2 |
| `skincare_part3`           | `04 Skin Care Management_Part 3`  | Part 3 |

## Architecture

### 1. Shared module registry — `src/modules.py` (new)

Single source of truth imported by both the dubber and the viewer, so the
mapping is never duplicated. Structure:

```python
MODULES = {
  "gen-intro": Module(
      label="Gen Intro",
      final_dir="Gen Intro",
      out_dir="gen_intro_dubbed",
      vids_dir="gen_intro_vids",
      parts=[Part(video="gen_intro_v1", stem="01 Gen Intro_Intro", label="Intro"), ...],
  ),
  "mucositis": Module(... parts from the mapping above ...),
  ...
}
LANGS = ["ko", "zh", "ja", "hy", "fa"]
LANG_SUB_CODE = {"ko": "kor", "zh": "zho", "ja": "jpn", "hy": "hye", "fa": "per"}
```

Each `Part` yields:
- source video: `<vids_dir>/<video>_multisub.mp4`
- dubbed output: `output/<out_dir>/<lang>/<video>_<lang>.mp4`
- assembled assets: `output/final/<lang>/<final_dir>/<stem>.{wav,srt}`,
  `output/translations/<lang>/<final_dir>/<stem>.json`

Folding gen intro into the registry means the existing gen-intro-specific code
paths get replaced by the generic ones (verified by tests to keep gen intro
working).

### 2. Build step — generalize the dubber

Rename/refactor `src/gen_intro_dubber.py` → `src/module_dubber.py` (keep a thin
re-export if anything imports the old name). Drive it from `MODULES`:

- For each module → each part → each language: mux `final` WAV audio onto the
  multisub source video, re-embed all available SRTs as `mov_text` tracks with
  correct `language=` metadata (unchanged ffmpeg command from the current
  `_process_one`).
- Idempotent: skip if the output already exists (existing "cached" behavior).
- CLI entry so it can be run standalone; also wire a `--stage gen-intro-dub`
  (or `module-dub`) into `pipeline.py`.
- Run it now to produce all four modules' dubbed videos
  (13 parts × 5 langs = 65 ffmpeg invocations).

### 3. Viewer changes — `viewer.py`

- Replace the hard-coded `GEN_INTRO_*` constants and gen-intro routes with
  generic, registry-driven equivalents:
  - `GET /api/modules` → returns, per module key: label, list of parts
    (`{video, stem, label, final_dir}`), and `by_lang` availability (built mp4
    filenames present under `output/<out_dir>/<lang>/`).
  - `GET /module-video/<module>/<lang>/<filename>` → serve the dubbed mp4.
  - `/subtitles/<audio_lang>/<sub_lang>/<module_final_dir>/<stem>` → **unchanged**
    (already generic; front-end passes the module's `final_dir` name).
- Front-end: render one sidebar section per module (reusing the existing
  `video-item` styling and section-divider), and generalize the gen-intro JS
  handlers (`selectGenIntroVideo`, `setGenIntroTracks`, availability, language
  switching) into per-module handlers keyed by module id + `final_dir`.
- "Dubbed Videos" and "Audio Review" sections stay as-is.

## Data flow (playback)

1. User clicks a part → front-end knows `{module, video, stem, final_dir}`.
2. Video src = `/module-video/<module>/<lang>/<video>_<lang>.mp4`.
3. Five `<track>`s added, each src =
   `/subtitles/<lang>/<subLang>/<final_dir>/<stem>`; the track matching the
   current audio `lang` is `default`.
4. Switching language reloads the video src at the same `currentTime` and
   rebuilds tracks so subtitle timing stays synced to the new audio.

## Error handling

- Missing WAV/SRT/video for a part+lang: dubber logs a warning and counts an
  error, continues (existing behavior). Viewer marks unavailable parts as
  greyed-out `unavailable` (existing pattern) based on `by_lang`.
- Subtitle endpoint returns 404 when the SRT or translation JSON is absent
  (existing behavior).

## Testing

- Unit test `src/modules.py` mapping: every declared source video and assembled
  stem resolves to an existing file for at least one language (guards typos like
  "Paint Management").
- Unit test the dubber's ffmpeg command construction (mapping args, subtitle
  metadata) without invoking ffmpeg.
- Test `GET /api/modules` returns the four new modules with correct parts and
  availability reflecting files on disk.
- Manual smoke test: load the viewer, play one part per module, switch language,
  confirm audio + captions change together.

## Out of scope

- The `dubbed_videos/` root dir (duplicate of `output/dubbed_elevenlabs/`,
  already in the viewer's "Dubbed Videos" section) — no change.
- Telugu (`te`) remains hidden, consistent with current behavior.
