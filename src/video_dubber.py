import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

VIDEO_MODULE_MAP = {
    "01_ct_simulation_planning": "Gen Intro",
    "02_radiation_dermatitis_skincare": "Skin Care Management",
    "03_pain_management_overview": "Pain Management",
    "04_mucositis_rinses": "Mucositis",
    "05_nutrition_support": "Nutrition",
}


def _concat_wavs(wav_files: list[Path], out_path: Path) -> bool:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for wav in wav_files:
            f.write(f"file '{wav.resolve()}'\n")
        list_path = Path(f.name)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path),
             "-c", "copy", str(out_path)],
            capture_output=True, check=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        logger.error("WAV concat failed: %s", e.stderr.decode())
        return False
    finally:
        list_path.unlink(missing_ok=True)


def _replace_audio(video_path: Path, audio_path: Path, out_path: Path) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["ffmpeg", "-y",
             "-i", str(video_path),
             "-i", str(audio_path),
             "-map", "0:v:0", "-map", "1:a:0",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             str(out_path)],
            capture_output=True, check=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Audio replace failed: %s", e.stderr.decode())
        return False


def run_dub_stage(dubbed_dir: Path, final_dir: Path, output_dir: Path) -> dict:
    counts = {"done": 0, "cached": 0, "errors": 0}
    out_base = output_dir / "dubbed_elevenlabs"

    for video_path in sorted(dubbed_dir.glob("*.mp4")):
        stem = video_path.stem  # e.g. "04_mucositis_rinses_ko"
        video_key, lang = stem.rsplit("_", 1)

        if video_key not in VIDEO_MODULE_MAP:
            logger.warning("No module mapping for: %s", video_key)
            counts["errors"] += 1
            continue

        module = VIDEO_MODULE_MAP[video_key]
        wav_files = sorted((final_dir / lang / module).glob("*.wav"))
        if not wav_files:
            logger.warning("No WAV files for %s / %s", lang, module)
            counts["errors"] += 1
            continue

        out_path = out_base / lang / video_path.name
        if out_path.exists():
            logger.info("Cached: %s", out_path.name)
            counts["cached"] += 1
            continue

        logger.info("Dubbing %s → %s (%d parts)", stem, module, len(wav_files))
        with tempfile.TemporaryDirectory() as tmp:
            combined = Path(tmp) / "combined.wav"
            if not _concat_wavs(wav_files, combined):
                counts["errors"] += 1
                continue
            if not _replace_audio(video_path, combined, out_path):
                counts["errors"] += 1
                continue

        logger.info("Done: %s", out_path.name)
        counts["done"] += 1

    return counts
