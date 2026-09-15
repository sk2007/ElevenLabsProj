import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

BASE_DIR = Path(__file__).parent
CAPTIONS_DIR = BASE_DIR / "Captions"
OUTPUT_DIR = BASE_DIR / "output"
LANGS = ["ko", "zh", "te", "ja", "hy", "fa"]


def _check_ffmpeg() -> None:
    import subprocess
    for tool in ("ffmpeg", "ffprobe"):
        try:
            subprocess.run([tool, "-version"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            sys.exit(f"ERROR: {tool} not found. Install with: brew install ffmpeg")


def _openai_client():
    from openai import OpenAI
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        sys.exit("ERROR: OPENAI_API_KEY not set in .env")
    return OpenAI(api_key=key)


def _elevenlabs_client():
    from elevenlabs.client import ElevenLabs
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("ERROR: ELEVENLABS_API_KEY not set in .env")
    return ElevenLabs(api_key=key)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Translate SRT captions to Korean and Chinese with ElevenLabs audio"
    )
    parser.add_argument(
        "--stage",
        choices=["translate", "synthesize", "assemble", "dub"],
        help="Run only one stage (default: run translate/synthesize/assemble in order; "
             "'dub' builds per-language module videos and is not part of the default run)",
    )
    args = parser.parse_args()

    _check_ffmpeg()

    run_all = args.stage is None

    if run_all or args.stage == "translate":
        from src.translator import run_translate_stage
        print("=== Stage 1: Translation ===")
        counts = run_translate_stage(CAPTIONS_DIR, OUTPUT_DIR, LANGS, _openai_client())
        print(f"Stage 1: {counts['translated']} files translated, "
              f"{counts['cached']} cached, {counts['errors']} errors\n")

    if run_all or args.stage == "synthesize":
        from src.synthesizer import run_synthesize_stage
        print("=== Stage 2: Audio Synthesis ===")
        counts = run_synthesize_stage(OUTPUT_DIR, LANGS, _elevenlabs_client())
        print(f"Stage 2: {counts['synthesized']} segments synthesized, "
              f"{counts['cached']} cached, {counts['errors']} errors\n")

    if run_all or args.stage == "assemble":
        from src.assembler import run_assemble_stage
        print("=== Stage 3: Time-scale & Assembly ===")
        counts = run_assemble_stage(OUTPUT_DIR, LANGS)
        print(f"Stage 3: {counts['assembled']} files assembled, "
              f"{counts['warnings']} warnings, {counts['errors']} errors\n")

    if args.stage == "dub":
        from src.module_dubber import run_module_dub_stage
        print("=== Stage: Module Video Dubbing ===")
        counts = run_module_dub_stage(BASE_DIR, OUTPUT_DIR)
        print(f"Dubbing: {counts['done']} built, {counts['cached']} cached, "
              f"{counts['errors']} errors\n")


if __name__ == "__main__":
    main()
