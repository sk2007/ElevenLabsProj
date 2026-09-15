# Savjani Lab: End-to-End Dubbing Pipeline Demo

This folder contains the interactive demo webpage showcasing the complete 4-stage pipeline for automated oncology patient education video translation and dubbing.

For the purpose of this demonstration, the application focuses exclusively on the **first video in the video library**:
- **Module:** General Introduction (`gen-intro`)
- **Part:** Intro (`01 Gen Intro_Intro`, source video: `gen_intro_v1_multisub.mp4`)
- **Title:** *"What is radiation therapy and what to expect?"*
- **Segment Count:** 23 subtitle segments

---

## The 4 Pipeline Stages Demonstrated

```
[ Stage 1: Captions & Translation ]
   • Source English SRT: Captions/Gen Intro/01 Gen Intro_Intro.srt
   • OpenAI GPT-4o oncology-specialized translation
   • JSON output segments: output/translations/<lang>/Gen Intro/01 Gen Intro_Intro.json
             │
             ▼
[ Stage 2: ElevenLabs TTS Synthesis ]
   • Per-segment voice generation: eleven_multilingual_v2
   • Stock voice: Rachel (21m00Tcm4TlvDq8ikWAM)
   • 23 segment MP3s: output/audio_raw/<lang>/Gen Intro/01 Gen Intro_Intro_segXXX.mp3
             │
             ▼
[ Stage 3: Audio Assembly & Retiming ]
   • Segment concatenation via FFmpeg into master WAV
   • Precise speech duration measured via ffprobe
   • SRT timestamps recalculated from scratch (output/final/<lang>/Gen Intro/01 Gen Intro_Intro.wav + .srt)
             │
             ▼
[ Stage 4: Video Orchestration & Multi-Sub Dubbing ]
   • Source video: gen_intro_vids/gen_intro_v1_multisub.mp4
   • Muxed with dubbed WAV audio and multi-language mov_text subtitle tracks
   • Smart tail-trimming to match natural narration length
   • Final output: output/gen_intro_dubbed/<lang>/gen_intro_v1_<lang>.mp4
```

---

## Running the Demo Webpage

Run the demo server using Python 3:

```bash
python3 demo/app.py --port 5050
```

Then visit **http://localhost:5050** in your browser.

### Key Interactive Features
- **Language Switcher**: Toggle instantly between Spanish (`es`), Korean (`ko`), Simplified Chinese (`zh`), Japanese (`ja`), Armenian (`hy`), and Farsi (`fa`).
- **Stage 1 (Translation)**: View the 23 source English segments alongside the target language translation and inspect the GPT-4o prompt guidelines.
- **Stage 2 (ElevenLabs TTS)**: Listen to individual audio snippets synthesized for each of the 23 segments.
- **Stage 3 (Assembly & Retiming)**: Listen to the master assembled audio track and compare the original English timing vs. recalculated spoken timing with pacing deltas.
- **Stage 4 (Dubbed Video)**: Side-by-side video player comparing the original English source video against the newly dubbed video with embedded WebVTT subtitles.
