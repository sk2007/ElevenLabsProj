from dataclasses import dataclass
from pathlib import Path


@dataclass
class Segment:
    index: int
    start: str
    end: str
    text: str


def parse_srt(path: Path) -> list[Segment]:
    raw = path.read_text(encoding="utf-8-sig")
    blocks = [b.strip() for b in raw.strip().split("\n\n") if b.strip()]
    segments = []
    for block in blocks:
        lines = block.splitlines()
        if len(lines) < 3:
            continue
        index = int(lines[0].strip())
        start, end = [t.strip() for t in lines[1].split("-->")]
        text = " ".join(line.strip() for line in lines[2:] if line.strip())
        segments.append(Segment(index=index, start=start, end=end, text=text))
    return segments


def write_srt(segments: list[Segment], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for s in segments:
        lines.append(str(s.index))
        lines.append(f"{s.start} --> {s.end}")
        lines.append(s.text)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
