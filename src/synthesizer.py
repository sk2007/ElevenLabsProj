import json
import logging
from pathlib import Path

from elevenlabs.client import ElevenLabs

logger = logging.getLogger(__name__)

VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel — ElevenLabs stock female voice
MODEL_ID = "eleven_multilingual_v2"
OUTPUT_FORMAT = "mp3_44100_128"


def synthesize_segment(
    text: str,
    out_path: Path,
    voice_id: str,
    client: ElevenLabs,
) -> bool:
    if out_path.exists() and out_path.stat().st_size > 0:
        logger.debug("Cached: %s", out_path.name)
        return False
    try:
        chunks = client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id=MODEL_ID,
            output_format=OUTPUT_FORMAT,
        )
        audio = b"".join(chunks)
    except Exception as e:
        logger.error("ElevenLabs TTS failed (%s): %s", out_path.name, e)
        return False

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(audio)
    return True


def run_synthesize_stage(
    output_dir: Path,
    langs: list[str],
    client: ElevenLabs,
    voice_id: str = VOICE_ID,
) -> dict:
    counts = {"synthesized": 0, "cached": 0, "errors": 0}
    for lang in langs:
        trans_root = output_dir / "translations" / lang
        if not trans_root.exists():
            continue
        for json_path in sorted(trans_root.rglob("*.json")):
            module = json_path.parent.name
            try:
                segments = json.loads(json_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                logger.error("Cannot read %s: %s", json_path, e)
                counts["errors"] += 1
                continue
            for seg in segments:
                out_path = (
                    output_dir / "audio_raw" / lang / module
                    / f"{json_path.stem}_seg{seg['index']:03d}.mp3"
                )
                if out_path.exists() and out_path.stat().st_size > 0:
                    counts["cached"] += 1
                    continue
                ok = synthesize_segment(seg["translated"], out_path, voice_id, client)
                if ok:
                    counts["synthesized"] += 1
                else:
                    counts["errors"] += 1
    return counts
