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


def seconds_to_srt_time(t: float) -> str:
    ms = int(round((t % 1) * 1000))
    s = int(t)
    h = s // 3600
    m = (s % 3600) // 60
    s = s % 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def assemble_srt_file(
    translation: list[dict],
    raw_dir: Path,
    final_wav: Path,
    final_srt: Path,
) -> dict:
    """Concatenate segments at natural speed; recalculate SRT timestamps from actual durations."""
    warnings = 0
    final_wav.parent.mkdir(parents=True, exist_ok=True)

    segment_info = []
    for seg in translation:
        raw_path = raw_dir / f"{final_wav.stem}_seg{seg['index']:03d}.mp3"
        if not raw_path.exists():
            logger.warning("Missing raw segment: %s", raw_path)
            warnings += 1
            continue
        try:
            duration = get_audio_duration(raw_path)
        except Exception as e:
            logger.warning("Could not measure %s: %s — skipping", raw_path.name, e)
            warnings += 1
            continue
        segment_info.append((raw_path, duration, seg))

    if not segment_info:
        logger.error("No segments available for %s", final_wav.name)
        return {"warnings": warnings}

    with tempfile.TemporaryDirectory() as tmp:
        concat_list = Path(tmp) / "concat.txt"
        concat_list.write_text(
            "\n".join(f"file '{p}'" for p, _, _ in segment_info),
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

    cursor = 0.0
    srt_segments = []
    for _, duration, seg in segment_info:
        start = seconds_to_srt_time(cursor)
        cursor += duration
        end = seconds_to_srt_time(cursor)
        srt_segments.append(Segment(index=seg["index"], start=start, end=end, text=seg["translated"]))

    write_srt(srt_segments, final_srt)
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
