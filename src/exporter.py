"""Export a distributable folder of every dubbed video with its own-language
subtitle burned in.

Layout: ``<export_dir>/<Language>/<Module>/NN <Part>.mp4`` (language then module).
Each file has the language's dubbed audio and that same language's subtitle
permanently rendered into the picture (hardsub), so it displays in any player.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from src.modules import LANG_NAMES, LANGS, MODULES, Module, Part

logger = logging.getLogger(__name__)

# libass (needed to burn subtitles) ships in the keg-only ffmpeg-full build.
FFMPEG_FULL = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"


def resolve_ffmpeg() -> str:
    """Prefer ffmpeg-full (has libass); fall back to plain ffmpeg."""
    return FFMPEG_FULL if Path(FFMPEG_FULL).exists() else "ffmpeg"


def build_burn_cmd(video_path: Path, srt_path: Path, out_path: Path,
                   ffmpeg_bin: str = "ffmpeg") -> list[str]:
    """ffmpeg command: re-encode video with the SRT burned in, copy audio, drop other streams."""
    return [
        ffmpeg_bin, "-y", "-i", str(video_path),
        "-map", "0:v:0", "-map", "0:a:0",
        "-vf", f"subtitles={srt_path}",
        "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        str(out_path),
    ]


def _burn_one(video_path: Path, srt_path: Path, out_path: Path, ffmpeg_bin: str) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Copy the SRT to a temp file with a simple ASCII name so the ffmpeg
    # subtitles filter never has to escape spaces/colons from the real path.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_srt = Path(tmp) / "sub.srt"
        shutil.copyfile(srt_path, tmp_srt)
        cmd = build_burn_cmd(video_path, tmp_srt, out_path, ffmpeg_bin)
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error("Failed %s: %s", out_path, e.stderr.decode()[-300:])
            return False


def export_all(base_dir: Path, output_dir: Path, export_dir: Path,
               module_keys: list[str] | None = None,
               langs: list[str] | None = None,
               ffmpeg_bin: str | None = None) -> dict:
    counts = {"done": 0, "cached": 0, "errors": 0}
    final_dir = output_dir / "final"
    keys = module_keys or list(MODULES)
    langs = langs or LANGS
    ffmpeg_bin = ffmpeg_bin or resolve_ffmpeg()

    for key in keys:
        module = MODULES[key]
        for i, part in enumerate(module.parts, start=1):
            for lang in langs:
                video_path = part.out_path(output_dir, module, lang)
                srt_path = part.srt_path(final_dir, module, lang)
                if not video_path.exists() or not srt_path.exists():
                    logger.warning("Missing source for %s/%s (%s)", module.label, part.label, lang)
                    counts["errors"] += 1
                    continue

                out_path = (export_dir / LANG_NAMES.get(lang, lang)
                            / module.label / f"{i:02d} {part.label}.mp4")
                if out_path.exists():
                    counts["cached"] += 1
                    continue

                logger.info("Burning %s / %s / %s", LANG_NAMES.get(lang, lang),
                            module.label, out_path.name)
                if _burn_one(video_path, srt_path, out_path, ffmpeg_bin):
                    counts["done"] += 1
                else:
                    counts["errors"] += 1
    return counts


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description="Export all dubbed videos with burned-in subtitles, by language then module")
    parser.add_argument("--modules", nargs="+", choices=list(MODULES),
                        help="Module keys to export (default: all)")
    parser.add_argument("--langs", nargs="+", choices=LANGS,
                        help="Languages to export (default: all)")
    parser.add_argument("--export-dir", default="exports",
                        help="Output folder (default: exports/)")
    parser.add_argument("--ffmpeg", help="ffmpeg binary to use (default: auto-detect ffmpeg-full)")
    args = parser.parse_args()

    base_dir = Path(__file__).parent.parent
    counts = export_all(base_dir, base_dir / "output",
                        base_dir / args.export_dir, args.modules, args.langs, args.ffmpeg)
    print(f"Export: {counts['done']} burned, {counts['cached']} cached, "
          f"{counts['errors']} errors")


if __name__ == "__main__":
    main()
