"""Shared registry of subtitled video modules.

Single source of truth for the viewer and the dubber. Each module maps a
directory of ``*_multisub.mp4`` source videos (English audio + embedded
subtitle tracks) to the assembled per-language audio/subtitle assets under
``output/final`` and ``output/translations``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

LANGS = ["ko", "zh", "ja", "hy", "fa", "es"]

LANG_NAMES = {
    "ko": "Korean",
    "zh": "Chinese (Simplified)",
    "ja": "Japanese",
    "hy": "Armenian",
    "fa": "Farsi (Persian)",
    "es": "Spanish",
}

# ISO 639-2/B codes used for embedded mov_text subtitle metadata.
LANG_SUB_CODE = {
    "ko": "kor",
    "zh": "zho",
    "ja": "jpn",
    "hy": "hye",
    "fa": "per",
    "es": "spa",
}


@dataclass(frozen=True)
class Part:
    """One video part within a module."""

    video: str  # source basename, without the "_multisub.mp4" suffix
    stem: str   # assembled stem under output/final/<lang>/<final_dir>/
    label: str  # sidebar display label

    def source_video(self, base_dir: Path, module: "Module") -> Path:
        return base_dir / module.vids_dir / f"{self.video}_multisub.mp4"

    def out_file(self, lang: str) -> str:
        return f"{self.video}_{lang}.mp4"

    def out_path(self, output_dir: Path, module: "Module", lang: str) -> Path:
        return output_dir / module.out_dir / lang / self.out_file(lang)

    def wav_path(self, final_dir: Path, module: "Module", lang: str) -> Path:
        return final_dir / lang / module.final_dir / f"{self.stem}.wav"

    def srt_path(self, final_dir: Path, module: "Module", lang: str) -> Path:
        return final_dir / lang / module.final_dir / f"{self.stem}.srt"


@dataclass(frozen=True)
class Module:
    """A group of related video parts."""

    key: str          # url-safe identifier, e.g. "mucositis"
    label: str        # sidebar section label, e.g. "Mucositis"
    final_dir: str    # dir name under output/final/<lang>/ and output/translations/<lang>/
    out_dir: str      # dir name under output/ holding dubbed per-language videos
    vids_dir: str     # dir holding the source *_multisub.mp4 files
    parts: list[Part] = field(default_factory=list)


def _numbered(prefix_video: str, final_prefix: str, count: int) -> list[Part]:
    """Intro, Part 1..count, Summary — the regular module shape."""
    parts = [Part(f"{prefix_video}_introduction", f"01 {final_prefix}_Intro", "Intro")]
    for i in range(1, count + 1):
        parts.append(
            Part(f"{prefix_video}_part{i}", f"{i + 1:02d} {final_prefix}_Part {i}", f"Part {i}")
        )
    parts.append(
        Part(f"{prefix_video}_summary", f"{count + 2:02d} {final_prefix}_Summary", "Summary")
    )
    return parts


_GEN_INTRO_PARTS = [
    Part("gen_intro_v1", "01 Gen Intro_Intro", "Intro"),
    Part("gen_intro_v2", "02 Gen Intro_Part 1", "Part 1"),
    Part("gen_intro_v3", "03 Gen Intro_Part 2", "Part 2"),
    Part("gen_intro_v4", "04 Gen Intro_Part 3", "Part 3"),
    Part("gen_intro_v5", "05 Gen Intro_Part 4", "Part 4"),
    Part("gen_intro_v6", "06 Gen Intro_Part 5", "Part 5"),
    Part("gen_intro_v7", "07 Gen Intro_Part 6", "Part 6"),
    Part("gen_intro_v8", "08 Gen Intro_Part 7", "Part 7"),
    Part("gen_intro_v9", "09 Gen Intro_Part 8", "Part 8"),
    Part("gen_intro_v10", "10 Gen Intro_Summary", "Summary"),
]

# Pain Management is irregular: source videos are introduction/part2/part3, but
# the assembled stems are Intro/Part 1/Part 2 (and carry a "Paint" typo in the
# Intro stem). Confirmed mapping with the user.
_PAIN_PARTS = [
    Part("painmgmt_introduction", "01 Paint Management_Intro", "Intro"),
    Part("painmgmt_part2", "02 Pain Management_Part 1", "Part 1"),
    Part("painmgmt_part3", "03 Pain Management_Part 2", "Part 2"),
]

MODULES: dict[str, Module] = {
    "gen-intro": Module(
        key="gen-intro", label="Gen Intro", final_dir="Gen Intro",
        out_dir="gen_intro_dubbed", vids_dir="gen_intro_vids", parts=_GEN_INTRO_PARTS,
    ),
    "mucositis": Module(
        key="mucositis", label="Mucositis", final_dir="Mucositis",
        out_dir="mucositis_dubbed", vids_dir="mucositis_vids",
        parts=_numbered("mucositis", "Mucositis", 5),
    ),
    "nutrition": Module(
        key="nutrition", label="Nutrition", final_dir="Nutrition",
        out_dir="nutrition_dubbed", vids_dir="nutrition_vids",
        parts=_numbered("nutrition", "Nutrition", 5),
    ),
    "pain-management": Module(
        key="pain-management", label="Pain Management", final_dir="Pain Management",
        out_dir="pain_management_dubbed", vids_dir="pain_management_vids", parts=_PAIN_PARTS,
    ),
    "skincare": Module(
        key="skincare", label="Skin Care Management", final_dir="Skin Care Management",
        out_dir="skincare_dubbed", vids_dir="skincare_vids",
        parts=[
            Part("skincare_introduction", "01 Skin Care Management_Intro", "Intro"),
            Part("skincare_part1", "02 Skin Care Management_Part 1", "Part 1"),
            Part("skincare_part2", "03 Skin Care Management_Part 2", "Part 2"),
            Part("skincare_part3", "04 Skin Care Management_Part 3", "Part 3"),
        ],
    ),
}
