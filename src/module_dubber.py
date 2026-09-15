"""Build per-language dubbed videos for every registered module.

For each part × language, mux the language's assembled ``output/final`` WAV
audio onto the module's ``*_multisub.mp4`` source video and re-embed all
available subtitle SRTs as ``mov_text`` tracks. Output goes to
``output/<module.out_dir>/<lang>/<video>_<lang>.mp4``.
"""

from __future__ import annotations

import argparse
import logging
import re
import subprocess
from pathlib import Path

from src.modules import LANG_SUB_CODE, LANGS, MODULES, Module, Part

logger = logging.getLogger(__name__)

# Don't bother re-cutting a tail shorter than this (keyframe-copy trims are
# only rough anyway).
TRIM_EPS = 1.0


def compute_output_duration(
    video_dur: float, audio_dur: float, caption_end: float | None
) -> float | None:
    """Duration to cap the output at, or None to leave the video untrimmed.

    Trim target is the later of the dubbed audio end and the original English
    caption end, so we never cut speech or originally-narrated visuals. Only
    trim when that target is meaningfully shorter than the source video (i.e.
    there is a trailing no-audio tail to remove).
    """
    target = max(audio_dur, caption_end or 0.0)
    if target < video_dur - TRIM_EPS:
        return target
    return None


def _probe_duration(path: Path) -> float | None:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return float(out)
    except (subprocess.CalledProcessError, ValueError):
        return None


def _last_caption_end(srt_path: Path) -> float | None:
    if not srt_path.exists():
        return None
    text = srt_path.read_text(encoding="utf-8-sig")
    ends = re.findall(r"-->\s*(\d\d):(\d\d):(\d\d),(\d\d\d)", text)
    if not ends:
        return None
    h, m, s, ms = ends[-1]
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def build_ffmpeg_cmd(
    video_path: Path, wav_path: Path,
    srt_paths: list[tuple[str, Path]], out_path: Path,
    duration: float | None = None,
) -> list[str]:
    """Construct the ffmpeg command: video from source, audio from WAV, subs from SRTs.

    When ``duration`` is given, the output is capped to that length (``-t``),
    trimming the trailing no-audio portion of the video.
    """
    cmd = ["ffmpeg", "-y", "-i", str(video_path), "-i", str(wav_path)]
    for _, srt_path in srt_paths:
        cmd += ["-i", str(srt_path)]

    cmd += ["-map", "0:v:0", "-map", "1:a:0"]
    for i in range(len(srt_paths)):
        cmd += ["-map", f"{i + 2}:s:0"]

    cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-c:s", "mov_text"]
    for i, (lang, _) in enumerate(srt_paths):
        cmd += [f"-metadata:s:s:{i}", f"language={LANG_SUB_CODE[lang]}"]

    if duration is not None:
        cmd += ["-t", f"{duration:.3f}"]

    cmd.append(str(out_path))
    return cmd


def _process_one(video_path: Path, wav_path: Path,
                 srt_paths: list[tuple[str, Path]], out_path: Path,
                 duration: float | None = None) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_ffmpeg_cmd(video_path, wav_path, srt_paths, out_path, duration)
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Failed %s: %s", out_path.name, e.stderr.decode()[-300:])
        return False


def _dub_part(module: Module, part: Part, base_dir: Path, final_dir: Path,
              captions_dir: Path, output_dir: Path, counts: dict) -> None:
    video_path = part.source_video(base_dir, module)
    if not video_path.exists():
        logger.warning("Missing video: %s", video_path)
        counts["errors"] += len(LANGS)
        return

    video_dur = _probe_duration(video_path)
    caption_end = _last_caption_end(captions_dir / module.final_dir / f"{part.stem}.srt")

    # All available subtitle SRTs for this part (same set embedded in every language video).
    srt_paths: list[tuple[str, Path]] = []
    for sub_lang in LANGS:
        srt_path = part.srt_path(final_dir, module, sub_lang)
        if srt_path.exists():
            srt_paths.append((sub_lang, srt_path))

    for lang in LANGS:
        wav_path = part.wav_path(final_dir, module, lang)
        if not wav_path.exists():
            logger.warning("Missing WAV for %s/%s", lang, part.stem)
            counts["errors"] += 1
            continue

        out_path = part.out_path(output_dir, module, lang)
        if out_path.exists():
            logger.info("Cached: %s", out_path.name)
            counts["cached"] += 1
            continue

        # Trim trailing no-audio video to the later of caption end / audio end.
        duration = None
        audio_dur = _probe_duration(wav_path)
        if video_dur is not None and audio_dur is not None:
            duration = compute_output_duration(video_dur, audio_dur, caption_end)

        trim_note = f" (trim → {duration:.1f}s)" if duration is not None else ""
        logger.info("Dubbing %s (%d subtitle tracks)%s", out_path.name, len(srt_paths), trim_note)
        if _process_one(video_path, wav_path, srt_paths, out_path, duration):
            counts["done"] += 1
        else:
            counts["errors"] += 1


def run_module_dub_stage(base_dir: Path, output_dir: Path,
                         module_keys: list[str] | None = None,
                         captions_dir: Path | None = None) -> dict:
    counts = {"done": 0, "cached": 0, "errors": 0}
    final_dir = output_dir / "final"
    captions_dir = captions_dir or (base_dir / "Captions")
    keys = module_keys or list(MODULES)
    for key in keys:
        module = MODULES[key]
        logger.info("=== Module: %s ===", module.label)
        for part in module.parts:
            _dub_part(module, part, base_dir, final_dir, captions_dir, output_dir, counts)
    return counts


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Build per-language dubbed module videos")
    parser.add_argument(
        "--modules", nargs="+", choices=list(MODULES),
        help="Module keys to build (default: all)",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).parent.parent
    output_dir = base_dir / "output"
    counts = run_module_dub_stage(base_dir, output_dir, args.modules)
    print(f"Dubbing: {counts['done']} built, {counts['cached']} cached, "
          f"{counts['errors']} errors")


if __name__ == "__main__":
    main()
