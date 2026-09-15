import json
import logging
from pathlib import Path

from openai import OpenAI

from src.srt_parser import Segment, parse_srt

logger = logging.getLogger(__name__)

OPENAI_MODEL = "gpt-4o"
LANG_NAMES = {
    "ko": "Korean",
    "zh": "Chinese (Simplified)",
    "te": "Telugu",
    "ja": "Japanese",
    "hy": "Armenian",
    "fa": "Farsi (Persian)",
    "es": "Spanish",
}


def _call_api(client: OpenAI, prompt: str) -> list[dict] | None:
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_tokens=16384,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = (response.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]
        return json.loads(raw)
    except Exception as e:
        logger.error("API call failed: %s", e)
        return None


def translate_file(
    segments: list[Segment],
    lang: str,
    out_path: Path,
    client: OpenAI,
) -> list[dict] | None:
    if out_path.exists():
        try:
            cached = json.loads(out_path.read_text(encoding="utf-8"))
            if len(cached) == len(segments):
                logger.info("Cached: %s", out_path.name)
                return cached
        except (json.JSONDecodeError, KeyError):
            pass

    lang_name = LANG_NAMES[lang]
    segments_json = json.dumps(
        [{"index": s.index, "text": s.text} for s in segments],
        ensure_ascii=False,
    )
    prompt = (
        f"You are a medical translator specializing in oncology patient education.\n\n"
        f"Translate ALL of the following English segments from an oncology patient education video into {lang_name}. "
        f"Preserve medical terminology accuracy. Keep translations concise — they will be spoken aloud.\n\n"
        f"Return ONLY a JSON array containing one entry per segment (same count as input), with no other text:\n"
        f'[{{"index": 1, "translated": "..."}}, {{"index": 2, "translated": "..."}}, ...]\n\n'
        f"Segments to translate ({len(segments)} total):\n{segments_json}"
    )

    trans_map: dict[int, str] = {}

    for attempt in range(2):
        trans_list = _call_api(client, prompt)
        if trans_list is None:
            return None
        trans_map.update({int(item["index"]): item["translated"] for item in trans_list})
        missing = [s.index for s in segments if s.index not in trans_map]
        if not missing:
            break
        if attempt == 0:
            logger.warning("%s: %d missing segment(s) %s — retrying", out_path.name, len(missing), missing)
            # Retry prompt asks only for the missing segments
            missing_segs = [s for s in segments if s.index in missing]
            missing_json = json.dumps(
                [{"index": s.index, "text": s.text} for s in missing_segs],
                ensure_ascii=False,
            )
            prompt = (
                f"You are a medical translator. Translate ALL of the following English segments into {lang_name}. "
                f"Return ONLY a JSON array:\n"
                f'[{{"index": N, "translated": "..."}}]\n\n'
                f"Segments ({len(missing_segs)} total):\n{missing_json}"
            )

    # Fall back to original English for any still-missing segments
    for s in segments:
        if s.index not in trans_map:
            logger.warning("%s: segment %d still missing — using original English", out_path.name, s.index)
            trans_map[s.index] = s.text

    result = [
        {
            "index": s.index,
            "start": s.start,
            "end": s.end,
            "original": s.text,
            "translated": trans_map[s.index],
        }
        for s in segments
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def run_translate_stage(
    captions_dir: Path,
    output_dir: Path,
    langs: list[str],
    client: OpenAI,
) -> dict:
    counts = {"translated": 0, "cached": 0, "errors": 0}
    for srt_path in sorted(captions_dir.rglob("*.srt")):
        module = srt_path.parent.name
        segments = parse_srt(srt_path)
        for lang in langs:
            out_path = output_dir / "translations" / lang / module / (srt_path.stem + ".json")
            if out_path.exists():
                try:
                    cached = json.loads(out_path.read_text(encoding="utf-8"))
                    if len(cached) == len(segments):
                        counts["cached"] += 1
                        continue
                except Exception:
                    pass
            result = translate_file(segments, lang, out_path, client)
            if result is None:
                counts["errors"] += 1
            else:
                counts["translated"] += 1
    return counts
