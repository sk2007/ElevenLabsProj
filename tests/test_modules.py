from pathlib import Path

import pytest

from src.modules import LANGS, MODULES, Part

BASE_DIR = Path(__file__).parent.parent
FINAL_DIR = BASE_DIR / "output" / "final"
TRANS_DIR = BASE_DIR / "output" / "translations"


def test_all_new_modules_registered():
    for key in ["mucositis", "nutrition", "pain-management", "skincare"]:
        assert key in MODULES


def test_expected_part_counts():
    assert len(MODULES["mucositis"].parts) == 7
    assert len(MODULES["nutrition"].parts) == 7
    assert len(MODULES["pain-management"].parts) == 3
    assert len(MODULES["skincare"].parts) == 4
    assert len(MODULES["gen-intro"].parts) == 10


@pytest.mark.parametrize("key", list(MODULES))
def test_source_videos_exist(key):
    mod = MODULES[key]
    for part in mod.parts:
        src = part.source_video(BASE_DIR, mod)
        assert src.exists(), f"missing source video {src}"


@pytest.mark.parametrize("key", list(MODULES))
def test_assembled_assets_exist_for_all_langs(key):
    """Guards stem typos: every stem must resolve to wav+srt+json for every lang."""
    mod = MODULES[key]
    for part in mod.parts:
        for lang in LANGS:
            wav = part.wav_path(FINAL_DIR, mod, lang)
            srt = part.srt_path(FINAL_DIR, mod, lang)
            js = TRANS_DIR / lang / mod.final_dir / f"{part.stem}.json"
            assert wav.exists(), f"missing {wav}"
            assert srt.exists(), f"missing {srt}"
            assert js.exists(), f"missing {js}"


def test_out_file_naming():
    part = Part("mucositis_introduction", "01 Mucositis_Intro", "Intro")
    assert part.out_file("ko") == "mucositis_introduction_ko.mp4"
