# UCLA Oncology Radiation Therapy Demo

This folder contains a self-contained, single-video dubbing workflow demo for [UCLA Oncology Radiation Therapy: Introduction](https://vimeo.com/1097732782), shared by Rachel Cooley on Vimeo. The local source video is downloaded from Vimeo's official download option and is attributed to the creator. The Vimeo page identifies its license as **Attribution–NoDerivatives**.

The sample contains 23 subtitle segments and demonstrates:

1. English caption review and translated segment data.
2. Per-segment ElevenLabs audio playback.
3. Assembled audio and recalculated subtitle timing.
4. Source and dubbed video playback.

## Run locally

```bash
python3 demo/app.py --port 5050
```

Visit <http://localhost:5050>.

## Deploy to Vercel

Import the repository and set **Root Directory** to `demo`. Vercel detects the Flask app from `app.py` and sends requests directly to its routes. Dependencies and the single-video media bundle are inside this folder; install requirements from `requirements.txt`.

## Source attribution

UCLA Oncology Radiation Therapy: Introduction by Rachel Cooley, via [Vimeo](https://vimeo.com/1097732782), licensed under [CC BY-ND](https://creativecommons.org/licenses/by-nd/4.0/).
